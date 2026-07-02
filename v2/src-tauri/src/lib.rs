use std::fs;
use std::net::TcpListener;
use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::sync::{Mutex, OnceLock};
use std::time::Duration;

#[cfg(unix)]
use std::os::unix::process::CommandExt;

use serde::{Deserialize, Serialize};
use tauri::{Manager, RunEvent};

/// The backend spawned for the project this process is showing, held in a global
/// so both the Tauri exit handler (GUI quit / window close) and the OS-signal
/// handler (SIGINT/SIGTERM/SIGHUP) can reap it. One backend per process — one
/// project per window; a different project means a whole new OS process, so this
/// process never manages more than one backend at a time.
static BACKEND: OnceLock<Mutex<Option<Child>>> = OnceLock::new();

/// The port the current backend is listening on, chosen dynamically at spawn
/// time (no fixed port — every process picks its own free port so siblings never
/// collide). The frontend reads this via `get_backend_port` to build its API URL.
static BACKEND_PORT: OnceLock<Mutex<Option<u16>>> = OnceLock::new();

/// A project path passed on the command line at launch (external launch only —
/// terminal, `open --args`, Finder "Open With"). Computed once at startup and
/// read by the frontend via `get_launch_target` so it can skip the picker and
/// open that project directly. The in-window "open a different project" button
/// spawns a bare instance with no args, so it never populates this.
static LAUNCH_TARGET: OnceLock<LaunchTarget> = OnceLock::new();

/// The folder of the project this process currently has open, so `kill_backend`
/// knows where to remove the port file it wrote in `open_project`.
static PROJECT_FOLDER: OnceLock<Mutex<Option<PathBuf>>> = OnceLock::new();

fn backend_slot() -> &'static Mutex<Option<Child>> {
    BACKEND.get_or_init(|| Mutex::new(None))
}

fn port_slot() -> &'static Mutex<Option<u16>> {
    BACKEND_PORT.get_or_init(|| Mutex::new(None))
}

fn project_folder_slot() -> &'static Mutex<Option<PathBuf>> {
    PROJECT_FOLDER.get_or_init(|| Mutex::new(None))
}

/// Where `open_project` publishes the current backend's connection info for
/// this project, so the MCP server can discover it by project folder instead
/// of needing a hardcoded port in its config (which goes stale the moment the
/// port changes on the next launch). A KEY=VALUE .env file rather than a bare
/// port number so more fields can be added later without a format change.
fn env_file_path(folder: &Path) -> PathBuf {
    state_dir(folder).join(".env")
}

fn kill_backend() {
    if let Ok(mut guard) = backend_slot().lock() {
        if let Some(mut child) = guard.take() {
            // The backend is spawned as its own process-group leader. Kill the
            // whole group, not just the leader: the PyInstaller release binary
            // is a bootloader that forks the real Python server as a child, so
            // killing only the leader would orphan the server (and keep the
            // port held).
            #[cfg(unix)]
            unsafe {
                libc::kill(-(child.id() as i32), libc::SIGKILL);
            }
            let _ = child.kill();
            let _ = child.wait();
        }
    }
    if let Ok(mut guard) = port_slot().lock() {
        *guard = None;
    }
    if let Ok(mut guard) = project_folder_slot().lock() {
        if let Some(folder) = guard.take() {
            let _ = fs::remove_file(env_file_path(&folder));
        }
    }
}

/// Ask the OS for a free TCP port: bind to port 0, read back the assigned port,
/// then drop the listener so the backend can bind it. There is an inherent tiny
/// race between drop and re-bind, but in practice the OS does not immediately
/// hand the same ephemeral port to another process.
fn pick_free_port() -> std::io::Result<u16> {
    let listener = TcpListener::bind(("127.0.0.1", 0))?;
    let port = listener.local_addr()?.port();
    drop(listener);
    Ok(port)
}

/// Dev loop: run the backend from its own venv (v2/backend/.venv), resolved
/// relative to this crate at compile time, pointed at the chosen project's DB
/// file on the chosen port.
#[cfg(debug_assertions)]
fn spawn_backend(db_path: &Path, port: u16) -> std::io::Result<Child> {
    let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("backend");
    let uvicorn = dir.join(".venv").join("bin").join("uvicorn");
    let mut cmd = Command::new(uvicorn);
    cmd.args([
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        &port.to_string(),
    ])
    .env("DATABASE_URL", db_url_for(db_path))
    .current_dir(&dir);
    #[cfg(unix)]
    cmd.process_group(0);
    cmd.spawn()
}

/// Release build: run the PyInstaller sidecar bundled next to the app binary
/// (Tauri externalBin places it in the same dir as the executable), pointed at
/// the chosen project's DB file on the chosen port.
#[cfg(not(debug_assertions))]
fn spawn_backend(db_path: &Path, port: u16) -> std::io::Result<Child> {
    let sidecar = std::env::current_exe()?
        .parent()
        .unwrap()
        .join("trackeroo-backend");

    let mut cmd = Command::new(sidecar);
    cmd.env("TRACKEROO_PORT", port.to_string())
        .env("DATABASE_URL", db_url_for(db_path));
    #[cfg(unix)]
    cmd.process_group(0);
    cmd.spawn()
}

/// Build the SQLite URL the backend expects for an absolute DB path. The backend
/// strips the `sqlite:///` prefix and treats the remainder as the path, so an
/// absolute path yields four leading slashes (`sqlite:////Users/...`).
fn db_url_for(db_path: &Path) -> String {
    format!("sqlite:///{}", db_path.display())
}

/// Poll the backend health endpoint on `port` until it responds or we give up.
fn wait_for_health(port: u16) -> bool {
    let url = format!("http://127.0.0.1:{port}/api/health");
    for _ in 0..60 {
        if let Ok(resp) = ureq::get(&url).timeout(Duration::from_millis(400)).call() {
            if resp.status() == 200 {
                return true;
            }
        }
        std::thread::sleep(Duration::from_millis(400));
    }
    false
}

/// An entry in the persisted recent-projects list. `path` is the project folder
/// (which contains `trackeroo.db`); `name` is a display label.
#[derive(Serialize, Deserialize, Clone)]
struct RecentProject {
    path: String,
    name: String,
}

fn recent_file(app: &tauri::AppHandle) -> Option<PathBuf> {
    app.path()
        .app_config_dir()
        .ok()
        .map(|dir| dir.join("recent_projects.json"))
}

fn read_recent(app: &tauri::AppHandle) -> Vec<RecentProject> {
    recent_file(app)
        .and_then(|p| fs::read_to_string(p).ok())
        .and_then(|txt| serde_json::from_str::<Vec<RecentProject>>(&txt).ok())
        .unwrap_or_default()
}

/// Move `path` to the front of the recent list (most-recent-first), de-duped,
/// capped at 10, and persist as JSON under the app config dir.
fn record_recent(app: &tauri::AppHandle, path: &str, name: &str) {
    let mut list = read_recent(app);
    list.retain(|r| r.path != path);
    list.insert(
        0,
        RecentProject {
            path: path.to_string(),
            name: name.to_string(),
        },
    );
    list.truncate(10);

    if let Some(file) = recent_file(app) {
        if let Some(dir) = file.parent() {
            let _ = fs::create_dir_all(dir);
        }
        if let Ok(txt) = serde_json::to_string_pretty(&list) {
            let _ = fs::write(file, txt);
        }
    }
}

/// Recent projects, filtered to those whose database still exists (folders
/// can be moved or deleted out from under us). Checks both the current
/// `.trackeroo/trackeroo.db` layout and the pre-migration flat layout, since
/// a recent entry might not have been reopened (and thus migrated) yet.
#[tauri::command]
fn list_recent_projects(app: tauri::AppHandle) -> Vec<RecentProject> {
    read_recent(&app)
        .into_iter()
        .filter(|r| {
            let folder = PathBuf::from(&r.path);
            db_path_for(&folder).exists() || folder.join("trackeroo.db").exists()
        })
        .collect()
}

/// The port the current backend is listening on, or `None` if no project has
/// been opened in this process yet.
#[tauri::command]
fn get_backend_port() -> Option<u16> {
    *port_slot().lock().unwrap()
}

/// What (if anything) the CLI told us to open at launch. `path` set = open this
/// project directly and skip the picker; `error` set = the given arg was invalid,
/// show the picker with this message; both `None` = no arg, show the picker.
#[derive(Serialize, Clone, Default)]
struct LaunchTarget {
    path: Option<String>,
    error: Option<String>,
}

/// Interpret the process args as an optional project path. The first non-flag
/// positional argument is treated as a project folder; it must exist and be a
/// directory (it need not already contain a `trackeroo.db` — a fresh folder is a
/// new project). Relative paths are resolved against the launch cwd. Flag-like
/// args (e.g. macOS's legacy `-psn_...`) are ignored.
fn compute_launch_target() -> LaunchTarget {
    let arg = std::env::args()
        .skip(1)
        .find(|a| !a.starts_with('-'));
    let Some(arg) = arg else {
        return LaunchTarget::default();
    };
    match std::fs::canonicalize(&arg) {
        Ok(p) if p.is_dir() => LaunchTarget {
            path: Some(p.to_string_lossy().to_string()),
            error: None,
        },
        Ok(_) => LaunchTarget {
            path: None,
            error: Some(format!("Launch path is not a folder: {arg}")),
        },
        Err(_) => LaunchTarget {
            path: None,
            error: Some(format!("Launch path does not exist: {arg}")),
        },
    }
}

/// The launch directive computed from the CLI at startup (see `LaunchTarget`).
#[tauri::command]
fn get_launch_target() -> LaunchTarget {
    LAUNCH_TARGET.get().cloned().unwrap_or_default()
}

/// All Trackeroo state for a project (database, port file, and anything
/// added later) lives under this subfolder, not loose in the project root —
/// keeps a project folder tidy and easy to `.gitignore` as one entry if the
/// user versions the folder themselves.
const STATE_DIR_NAME: &str = ".trackeroo";

fn state_dir(folder: &Path) -> PathBuf {
    folder.join(STATE_DIR_NAME)
}

fn db_path_for(folder: &Path) -> PathBuf {
    state_dir(folder).join("trackeroo.db")
}

/// Projects created before the `.trackeroo/` subfolder existed have their
/// database loose at `<folder>/trackeroo.db`. Move it into the subfolder the
/// first time such a project is opened post-update; a no-op for anything
/// already migrated (including brand-new projects, which never had the old
/// layout). Best-effort: a failed migration falls through to the normal
/// missing-database handling in `open_project` rather than panicking.
fn migrate_legacy_layout(folder: &Path) {
    let new_path = db_path_for(folder);
    if new_path.exists() {
        return;
    }
    let legacy_path = folder.join("trackeroo.db");
    if !legacy_path.exists() {
        return;
    }
    if fs::create_dir_all(state_dir(folder)).is_ok() {
        let _ = fs::rename(&legacy_path, &new_path);
    }
}

/// Open (or create) the project whose folder is `path`, spawn a backend for its
/// `.trackeroo/trackeroo.db` on a freshly chosen free port, wait for health,
/// record it in the recent list, and return the port so the frontend can point
/// its API client at it.
///
/// - `create`: when true, the folder is created if missing (New Project); when
///   false, an existing database is required (Open Project) and its absence
///   is an error.
/// - `name`: display label for the recent list; falls back to the folder name.
///
/// Runs on a separate thread (`command(async)`): spawning the backend and
/// polling `wait_for_health` blocks for the sidecar's cold-start (~9s in
/// release). A plain sync command would run on the main thread and freeze the
/// webview UI, so the picker's "opening…" spinner couldn't animate.
#[tauri::command(async)]
fn open_project(
    app: tauri::AppHandle,
    path: String,
    create: bool,
    name: Option<String>,
) -> Result<u16, String> {
    let folder = PathBuf::from(&path);
    migrate_legacy_layout(&folder);
    let db_path = db_path_for(&folder);

    if create {
        fs::create_dir_all(state_dir(&folder))
            .map_err(|e| format!("Could not create project folder: {e}"))?;
    } else if !db_path.exists() {
        return Err(format!(
            "No Trackeroo project found in {} (missing trackeroo.db).",
            folder.display()
        ));
    }

    // Reap any backend previously spawned in this process before starting a new
    // one. In normal use the picker opens exactly one project per process, but
    // this keeps us correct if a project is ever opened more than once.
    kill_backend();

    let port = pick_free_port().map_err(|e| format!("Could not allocate a port: {e}"))?;
    let child =
        spawn_backend(&db_path, port).map_err(|e| format!("Failed to start backend: {e}"))?;
    *backend_slot().lock().unwrap() = Some(child);

    if !wait_for_health(port) {
        kill_backend();
        return Err("Backend did not become healthy in time.".into());
    }
    *port_slot().lock().unwrap() = Some(port);
    // Best-effort: an MCP server pointed at this project folder reads this file
    // to find the live port instead of relying on a hardcoded, quickly-stale one.
    // KEY=VALUE .env format so more fields can be added later.
    let _ = fs::write(env_file_path(&folder), format!("TRACKEROO_PORT={port}\n"));
    *project_folder_slot().lock().unwrap() = Some(folder.clone());

    let display_name = name
        .map(|n| n.trim().to_string())
        .filter(|n| !n.is_empty())
        .unwrap_or_else(|| {
            folder
                .file_name()
                .and_then(|s| s.to_str())
                .unwrap_or("Project")
                .to_string()
        });
    record_recent(&app, &path, &display_name);

    Ok(port)
}

/// Launch a brand-new, fully independent OS process of this same app binary. The
/// new process starts from scratch and shows its own picker — there is no handoff
/// of which project was chosen (that is the whole point: separate process per
/// project). Uses direct execution of the current binary rather than `open`,
/// because `open` refocuses an already-running instance instead of launching a
/// new one; direct exec bypasses LaunchServices single-instance activation.
#[tauri::command]
fn open_new_window() -> Result<(), String> {
    let exe = std::env::current_exe().map_err(|e| e.to_string())?;
    Command::new(exe)
        .spawn()
        .map(|_| ())
        .map_err(|e| format!("Failed to launch a new window: {e}"))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // The backend is no longer spawned at startup: the project picker shows
    // first and needs no backend. A per-project backend is spawned only once the
    // user picks a project (via the open_project command) — or automatically, if
    // a project path was passed on the command line (see LAUNCH_TARGET).
    let _ = LAUNCH_TARGET.set(compute_launch_target());

    // Reap the backend on Ctrl-C / SIGTERM / SIGHUP (terminal or `kill`), then
    // exit. GUI quits are handled by RunEvent::Exit below.
    let _ = ctrlc::set_handler(|| {
        kill_backend();
        std::process::exit(0);
    });

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            get_backend_port,
            get_launch_target,
            open_project,
            list_recent_projects,
            open_new_window,
        ])
        .build(tauri::generate_context!())
        .expect("error while building Trackeroo")
        .run(|_app, event| {
            if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
                kill_backend();
            }
        });
}
