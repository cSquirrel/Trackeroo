# Trackeroo (Tauri desktop app)

Treat `v2/` as your working directory when working on it. See the repo-root `README.md` for repo layout notes.

A lightweight task tracker: epics → tasks, configurable kanban swim lanes, dependencies, blockers, comments/annotations, and links to PRs or Slack threads — plus an MCP server so AI agents can create and update tasks directly. Packaged as a native macOS desktop app, since the target use case is a single user on a single machine with no remote access ever needed.

**Multiple projects, vault-style.** Each project is just a folder — Trackeroo keeps all of its own state (database, the port its backend is currently running on, anything added later) inside a `.trackeroo/` subfolder within it, so the rest of the folder stays yours. One project = one folder. You pick projects the way Obsidian picks vaults: the app opens a **project picker** on every launch, and you can have several projects open at once — each in its own window and its own OS process. Projects are ordinary folders, so you can move, copy, back up, or sync them however you like — `.gitignore` the single `.trackeroo/` entry if you version the folder yourself and don't want the database tracked.

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

This compiles the Rust shell and opens a native window showing the project picker. No backend runs until you pick a project; choosing one spawns the backend (from `backend/.venv` in dev) on a free port picked at runtime, pointed at that project's `.trackeroo/trackeroo.db`.

### Building a release bundle

Three steps — the backend and MCP server are both bundled as PyInstaller-compiled binaries that `npm run build` does not rebuild automatically:

```bash
# 1. Build the backend sidecar (repeat after any backend code change)
cd backend
.venv/bin/pip install pyinstaller
.venv/bin/pyinstaller --onefile --name trackeroo-backend-aarch64-apple-darwin \
  --collect-submodules uvicorn --hidden-import uvloop --hidden-import httptools \
  --hidden-import websockets --paths . run_sidecar.py
mkdir -p ../src-tauri/binaries
cp dist/trackeroo-backend-aarch64-apple-darwin ../src-tauri/binaries/
cd ..

# 2. Build the MCP server sidecar (repeat after any mcp/ code change)
cd mcp
.venv/bin/pip install pyinstaller
.venv/bin/pyinstaller --onefile --name trackeroo-mcp-aarch64-apple-darwin \
  --collect-submodules mcp.server --paths . server.py
cp dist/trackeroo-mcp-aarch64-apple-darwin ../src-tauri/binaries/
cd ..

# 3. Build the app
npm run build
```

Produces `src-tauri/target/release/bundle/macos/Trackeroo.app` and a `.dmg` alongside it, both containing the MCP server as a real executable (`Contents/MacOS/trackeroo-mcp`) — the app is fully self-contained, installable on a fresh machine with no Python/pip/venv needed for either the backend or MCP. Both compiled sidecars and the build output are gitignored — rebuild after a fresh clone.

Note: `--collect-submodules mcp.server` (not the whole `mcp` package) — the package's optional `mcp.cli` submodule depends on `typer`, which isn't installed and isn't needed (we only use `mcp.server.fastmcp`).

## The project picker

Every launched window shows the picker first (no board until you choose a project):

- **New project** — type a name, then pick (via a native folder dialog) *where* to put it. The app creates a `<location>/<name>/` folder with a `.trackeroo/trackeroo.db` inside, seeded with the default swim lanes, and titles the board with the name you typed.
- **Open project** — pick an existing project folder (one that already contains a `.trackeroo/trackeroo.db`) via the native folder dialog. If the folder has no database, the picker shows an error instead of proceeding.
- **Recent projects** — a one-click list of folders you've opened before. Entries whose folder no longer has a database (moved or deleted) are hidden automatically.

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

The path must be an existing folder. It does **not** need to already contain a `.trackeroo/` subfolder — a fresh, empty folder becomes a new project; a folder that already has one opens with its existing data. If the argument is missing or points at something that isn't a folder, the app just shows the normal picker (with an inline error if the path was invalid, so a typo isn't swallowed silently).

This is only for external launches. The in-window "Open project…" button always opens a fresh picker (it never carries a path), exactly as described above.

## What you get

- **Native kanban board** — configurable swim lanes (default: Backlog / To Do / In Progress / Review / Done), draggable task cards, epic filtering and color-tagging.
- **Task detail** — description, comments and annotations, block/unblock with a reason, dependency links to other tasks, and links out to PRs or Slack threads.
- **Epics** — group related tasks; manage epics from their own view.
- **Swim lane config** — add, rename, reorder, or remove columns; mark one as the "done" column (used for dependency warnings).
- **MCP server** — bundled into the app as `Contents/MacOS/trackeroo-mcp`, a real executable (no Python/pip/venv needed to use it), exposing 15 tools. Point it at a project by folder, not port — `TRACKEROO_PROJECT_PATH=/path/to/project` — it discovers the live port automatically and keeps working across app restarts. See [`mcp/README.md`](mcp/README.md) for the Claude Code/Desktop registration snippet.

## Where your data lives

- **Your projects**: wherever you chose to create or open them. Each project folder holds a `.trackeroo/` subfolder containing `trackeroo.db` (and, while the app has it open, a `port` file). Projects created before this layout existed are migrated automatically the next time they're opened — the old loose `trackeroo.db` is moved into `.trackeroo/`, no data lost. In dev mode, if you haven't picked a project, nothing is created — the picker just waits.
- **Recent-projects list**: `~/Library/Application Support/com.trackeroo.desktop/recent_projects.json` — a small JSON array of `{ "path", "name" }` entries, most-recent-first. Deleting it just clears the "Recent" list; your projects are unaffected.

## Data model

Full field-level detail lives in [`docs/api-contract.md`](docs/api-contract.md) and [`docs/openapi.json`](docs/openapi.json) (generated from the backend — regenerate with `cd backend && .venv/bin/python -m app.export_openapi` after any schema change).

## Repo layout

```
backend/     FastAPI + SQLite REST API; DB path + port come from env vars per project
frontend/    Svelte + Vite UI, adapted for the Tauri webview; project picker + board
mcp/         MCP server — bundled into the app; point TRACKEROO_PROJECT_PATH at a project folder
src-tauri/   Rust shell: shows the picker, spawns/health-checks/kills a per-project backend, hosts the webview
docs/        openapi.json (generated, canonical REST contract) + api-contract.md (conventions/business rules)
```

## Known gotchas

- **Cold-start delay after picking a project**: the webview starts fetching as soon as a project is chosen, before the freshly-spawned sidecar is guaranteed to be listening. The release build's PyInstaller sidecar has real self-extraction overhead (~9s measured on this machine), so the board briefly shows a loading state before it appears — this is expected, not a bug (see `CLAUDE.md`).
- **Same project open in two windows**: nothing stops you opening the same project folder in two processes. SQLite's own locking handles low-rate concurrent access; heavy simultaneous writes from both could surface a transient "database is locked" error. This is an accepted edge case, not a supported workflow.
- **Unsigned build**: the `.app`/`.dmg` are ad-hoc signed only (no Apple Developer signing identity configured). macOS Gatekeeper will warn on first launch — right-click → Open, or allow via System Settings → Privacy & Security.
- **Sidecar binary naming**: must exactly match Tauri's `<name>-<target-triple>` convention — currently `trackeroo-backend-aarch64-apple-darwin` and `trackeroo-mcp-aarch64-apple-darwin` for Apple Silicon. See `src-tauri/tauri.conf.json`'s `bundle.externalBin`.

## Releases & auto-updates

The app updates itself in place using the [Tauri updater plugin](https://v2.tauri.app/plugin/updater/). Stable releases are cut from `main` and published as GitHub Releases; installed apps check that channel, download the new signed bundle, install it, and relaunch.

### How it works at runtime

- On launch (and via a manual **"Check for updates"** button in the picker footer and the board top bar) the app fetches the manifest at `https://github.com/cSquirrel/Trackeroo/releases/latest/download/latest.json`. `/latest/download/` always resolves to the newest *published, non-prerelease* Release.
- If a newer version is offered, a banner appears. Accepting downloads the `.app.tar.gz`, verifies its **minisign** signature against the `pubkey` baked into `tauri.conf.json` (`plugins.updater`), swaps the app bundle, and relaunches (via the `process` plugin). On macOS the whole `.app` is replaced, so the bundled `trackeroo-backend`/`trackeroo-mcp` sidecars update atomically with the shell.
- Updates are inert under `tauri dev` (there is no installed bundle to replace) — the frontend detects a dev build and skips silently.

### Publishing a release

1. Bump the version in lockstep: `src-tauri/tauri.conf.json`, `src-tauri/Cargo.toml`, and `package.json` (the root `v2/package.json`). `tauri.conf.json` is the source of truth the tag/manifest derive from.
2. Merge `develop` → `main` and push a tag `vX.Y.Z` on `main`.
3. `.github/workflows/release.yml` runs on an Apple-Silicon runner: it builds the two PyInstaller sidecars, then runs `tauri-action`, which builds + signs the bundle, generates `latest.json`, and attaches everything to a **draft** GitHub Release.
4. Review the draft, then **publish** it — publishing is what makes `/latest/download/` (and therefore the updater) point at the new version.

### One-time signing-key setup (required for CI)

Updater artifacts are signed with a minisign key. The **public** key is committed in `tauri.conf.json` (`plugins.updater.pubkey`); the **private** key must be provided to CI as repository secrets, or the `tauri-action` build fails to sign:

- `TAURI_SIGNING_PRIVATE_KEY` — the private key contents (generate with `npm run tauri signer generate`).
- `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` — its password (empty string if the key has none).

Set these under **GitHub → Settings → Secrets and variables → Actions**. Keep the private key out of the repo. If you rotate the key, regenerate it, update `pubkey` in `tauri.conf.json`, and re-set the secrets — apps signed with the old key can only update once you ship a build carrying the new `pubkey`.

### Bootstrap caveat

Builds before `0.2.0` have no `pubkey` baked in and cannot auto-update. Users on such a build (e.g. the original `0.1.0`) must install `0.2.0`+ **manually once** (download the `.dmg`); auto-update works for every release after that. Apple Developer ID signing + notarization is not yet configured (see the "Unsigned build" gotcha) — the updater mechanism works regardless, but a notarized build is a recommended follow-up so macOS Gatekeeper doesn't warn on the updated app.

## Versioning

See the repo-root `README.md` for the branch model (`develop` for active work, `main` for stable releases).
