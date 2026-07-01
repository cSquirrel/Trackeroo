# Trackeroo (v2 — Tauri desktop app)

> **v2 implementation.** This is the Tauri desktop-app implementation of Trackeroo. Treat `v2/` as your working directory when working on it. See the repo-root `README.md` for how versions are organized.

A lightweight task tracker: epics → tasks, configurable kanban swim lanes, dependencies, blockers, comments/annotations, and links to PRs or Slack threads — plus an MCP server so AI agents can create and update tasks directly. v2 packages this as a native macOS desktop app instead of a self-hosted web service, since the target use case is a single user on a single machine with no remote access ever needed.

**Multiple projects, vault-style.** Each project is just a folder that contains a `trackeroo.db` file (one SQLite database = one project). You pick projects the way Obsidian picks vaults: the app opens a **project picker** on every launch, and you can have several projects open at once — each in its own window and its own OS process. Projects are ordinary folders, so you can move, copy, back up, or sync them however you like.

## Quickstart

### Run the already-built app
If a release build exists, just launch it — no toolchain required:

```bash
open src-tauri/target/release/bundle/macos/Trackeroo.app
```

Or install via the `.dmg` at `src-tauri/target/release/bundle/dmg/Trackeroo_0.1.0_aarch64.dmg` (unsigned — see "Known gotchas" below).

### Dev mode (hot reload)

One-time setup — a Python venv for the backend:

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd ..
```

Then, from `v2/`:

```bash
npm install
npm run dev
```

This compiles the Rust shell and opens a native window showing the project picker. No backend runs until you pick a project; choosing one spawns the backend (from `backend/.venv` in dev) on a free port picked at runtime, pointed at that project's `trackeroo.db`.

### Building a release bundle

Two steps, because the backend is bundled as a PyInstaller-compiled binary that `npm run build` does not rebuild automatically:

```bash
# 1. Build the sidecar binary (repeat after any backend code change)
cd backend
.venv/bin/pip install pyinstaller
.venv/bin/pyinstaller --onefile --name trackeroo-backend-aarch64-apple-darwin \
  --collect-submodules uvicorn --hidden-import uvloop --hidden-import httptools \
  --hidden-import websockets --paths . run_sidecar.py
mkdir -p ../src-tauri/binaries
cp dist/trackeroo-backend-aarch64-apple-darwin ../src-tauri/binaries/
cd ..

# 2. Build the app
npm run build
```

Produces `src-tauri/target/release/bundle/macos/Trackeroo.app` and a `.dmg` alongside it. Both the compiled sidecar and the build output are gitignored — rebuild after a fresh clone.

## The project picker

Every launched window shows the picker first (no board until you choose a project):

- **New project** — type a name, then pick (via a native folder dialog) *where* to put it. The app creates a `<location>/<name>/` folder containing a fresh `trackeroo.db`, seeded with the default swim lanes, and titles the board with the name you typed.
- **Open project** — pick an existing project folder (one that already contains a `trackeroo.db`) via the native folder dialog. If the folder has no `trackeroo.db`, the picker shows an error instead of proceeding.
- **Recent projects** — a one-click list of folders you've opened before. Entries whose folder no longer has a `trackeroo.db` (moved or deleted) are hidden automatically.

Once a project is open, the board's top bar has an **"Open project…"** button. It launches a brand-new, fully independent copy of the app (a separate OS process) that shows its own picker from scratch. Your current window keeps running its own project, untouched — there is no in-window project switching, and no "which project" is handed to the new process. Close a window to quit that project's process (its backend is shut down with it).

## Launching a project from the command line

You can skip the picker and open a project folder directly by passing its path when launching the app externally (terminal, a script, or Finder "Open With"):

```bash
# Direct binary launch (reliable — always a new, independent instance):
/Applications/Trackeroo.app/Contents/MacOS/trackeroo /path/to/my-project

# Via `open` (use -n to force a new instance, since a bare `open` refocuses an
# already-running window instead of launching a fresh one):
open -n /Applications/Trackeroo.app --args /path/to/my-project
```

The path must be an existing folder. It does **not** need to already contain a `trackeroo.db` — a fresh, empty folder becomes a new project; a folder that already has a `trackeroo.db` opens with its existing data. If the argument is missing or points at something that isn't a folder, the app just shows the normal picker (with an inline error if the path was invalid, so a typo isn't swallowed silently).

This is only for external launches. The in-window "Open project…" button always opens a fresh picker (it never carries a path), exactly as described above.

## What you get

- **Native kanban board** — configurable swim lanes (default: Backlog / To Do / In Progress / Review / Done), draggable task cards, epic filtering and color-tagging.
- **Task detail** — description, comments and annotations, block/unblock with a reason, dependency links to other tasks, and links out to PRs or Slack threads.
- **Epics** — group related tasks; manage epics from their own view.
- **Swim lane config** — add, rename, reorder, or remove columns; mark one as the "done" column (used for dependency warnings).
- **MCP server** — see [`mcp/README.md`](mcp/README.md) for the Claude Code/Desktop registration snippet. Same 15 tools as v1. Note: the MCP server talks to a project's backend over HTTP via `TRACKEROO_API_URL`, but v2's backend port is now chosen dynamically per project (see below), so point the MCP server at the port of the specific project process you want it to drive.

## Where your data lives

- **Your projects**: wherever you chose to create or open them. Each project folder holds a single `trackeroo.db`. In dev mode, if you haven't picked a project, nothing is created — the picker just waits.
- **Recent-projects list**: `~/Library/Application Support/com.trackeroo.desktop/recent_projects.json` — a small JSON array of `{ "path", "name" }` entries, most-recent-first. Deleting it just clears the "Recent" list; your projects are unaffected.

## Data model

v2's backend is a copy of v1's — the REST contract is identical. Full field-level detail lives in [`../v1/docs/api-contract.md`](../v1/docs/api-contract.md) and [`../v1/docs/openapi.json`](../v1/docs/openapi.json) rather than being duplicated here.

## Repo layout

```
backend/     FastAPI + SQLite REST API — a copy of v1/backend; DB path + port come from env vars per project
frontend/    Svelte + Vite UI — a copy of v1/frontend, adapted for the Tauri webview; project picker + board
mcp/         MCP server — point TRACKEROO_API_URL at the running project's http://localhost:<port>
src-tauri/   Rust shell: shows the picker, spawns/health-checks/kills a per-project backend, hosts the webview
```

## Known gotchas

- **Cold-start delay after picking a project**: the webview starts fetching as soon as a project is chosen, before the freshly-spawned sidecar is guaranteed to be listening. The release build's PyInstaller sidecar has real self-extraction overhead (~9s measured on this machine), so the board briefly shows a loading state before it appears — this is expected, not a bug (see `CLAUDE.md`).
- **Same project open in two windows**: nothing stops you opening the same project folder in two processes. SQLite's own locking handles low-rate concurrent access; heavy simultaneous writes from both could surface a transient "database is locked" error. This is an accepted edge case, not a supported workflow.
- **Unsigned build**: the `.app`/`.dmg` are ad-hoc signed only (no Apple Developer signing identity configured). macOS Gatekeeper will warn on first launch — right-click → Open, or allow via System Settings → Privacy & Security.
- **Sidecar binary naming**: must exactly match Tauri's `<name>-<target-triple>` convention — currently `trackeroo-backend-aarch64-apple-darwin` for Apple Silicon. See `src-tauri/tauri.conf.json`'s `bundle.externalBin`.

## Versioning

Same as v1 — see the repo-root `README.md`.
