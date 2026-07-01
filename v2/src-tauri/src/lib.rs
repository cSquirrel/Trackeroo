use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::{Mutex, OnceLock};
use std::time::Duration;

#[cfg(unix)]
use std::os::unix::process::CommandExt;

use tauri::{Manager, RunEvent};

const BACKEND_PORT: u16 = 8787;

/// The spawned backend process, held in a global so both the Tauri exit handler
/// (GUI quit / window close) and the OS-signal handler (SIGINT/SIGTERM/SIGHUP)
/// can reap it. Without the signal path, a `kill` of the app would orphan the
/// uvicorn child, leaving port 8787 held after the app is gone.
static BACKEND: OnceLock<Mutex<Option<Child>>> = OnceLock::new();

fn backend_slot() -> &'static Mutex<Option<Child>> {
    BACKEND.get_or_init(|| Mutex::new(None))
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
}

/// Dev loop: run the backend from its own venv (v2/backend/.venv), resolved
/// relative to this crate at compile time. No bundled binary needed, so a fresh
/// checkout can `tauri dev` after just creating the venv.
#[cfg(debug_assertions)]
fn spawn_backend() -> std::io::Result<Child> {
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
        &BACKEND_PORT.to_string(),
    ])
    .current_dir(&dir);
    #[cfg(unix)]
    cmd.process_group(0);
    cmd.spawn()
}

/// Release build: run the PyInstaller sidecar bundled next to the app binary
/// (Tauri externalBin places it in the same dir as the executable). The DB
/// lives under the user's Application Support dir so the app bundle stays
/// read-only.
#[cfg(not(debug_assertions))]
fn spawn_backend() -> std::io::Result<Child> {
    let sidecar = std::env::current_exe()?
        .parent()
        .unwrap()
        .join("trackeroo-backend");

    let data_dir = PathBuf::from(std::env::var("HOME").unwrap_or_else(|_| ".".into()))
        .join("Library/Application Support/com.trackeroo.desktop");
    let _ = std::fs::create_dir_all(&data_dir);
    let db_url = format!("sqlite:///{}/trackeroo.db", data_dir.display());

    let mut cmd = Command::new(sidecar);
    cmd.env("TRACKEROO_PORT", BACKEND_PORT.to_string())
        .env("DATABASE_URL", db_url);
    #[cfg(unix)]
    cmd.process_group(0);
    cmd.spawn()
}

/// Poll the backend health endpoint until it responds or we give up.
fn wait_for_health() -> bool {
    let url = format!("http://127.0.0.1:{BACKEND_PORT}/api/health");
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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let child = spawn_backend().expect("failed to spawn Trackeroo backend");
    *backend_slot().lock().unwrap() = Some(child);

    // Reap the backend on Ctrl-C / SIGTERM / SIGHUP (terminal or `kill`), then
    // exit. GUI quits are handled by RunEvent::Exit below.
    let _ = ctrlc::set_handler(|| {
        kill_backend();
        std::process::exit(0);
    });

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let handle = app.handle().clone();
            std::thread::spawn(move || {
                if wait_for_health() {
                    if let Some(win) = handle.get_webview_window("main") {
                        let _ = win.show();
                        let _ = win.set_focus();
                    }
                } else {
                    eprintln!("Trackeroo backend did not become healthy in time");
                }
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Trackeroo")
        .run(|_app, event| {
            if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
                kill_backend();
            }
        });
}
