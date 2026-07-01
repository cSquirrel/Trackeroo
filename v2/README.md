# Trackeroo (v2 — Tauri desktop app)

> **v2 implementation.** This is the Tauri desktop-app implementation of Trackeroo. Treat `v2/` as your working directory when working on it. See the repo-root `README.md` for how versions are organized.

A lightweight, self-hosted task tracker for a single project: epics → tasks, configurable kanban swim lanes, dependencies, blockers, comments/annotations, and links to PRs or Slack threads — plus an MCP server so AI agents can create and update tasks directly. v2 packages this as a native macOS desktop app instead of a self-hosted web service, since the target use case is a single user on a single machine with no remote access ever needed.

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

This compiles the Rust shell, spawns the backend from its venv on a fixed port (`8787`, distinct from v1's `8000` so both can run at once), and opens a native window once the backend's `/api/health` responds.

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

## What you get

- **Native kanban board** — configurable swim lanes (default: Backlog / To Do / In Progress / Review / Done), draggable task cards, epic filtering and color-tagging.
- **Task detail** — description, comments and annotations, block/unblock with a reason, dependency links to other tasks, and links out to PRs or Slack threads.
- **Epics** — group related tasks; manage epics from their own view.
- **Swim lane config** — add, rename, reorder, or remove columns; mark one as the "done" column (used for dependency warnings).
- **MCP server** — see [`mcp/README.md`](mcp/README.md) for the Claude Code/Desktop registration snippet. Same 15 tools as v1, pointed at port `8787`.

## Where your data lives

- **Dev mode**: `backend/data/trackeroo.db`, relative to `backend/` (created automatically on first run).
- **Release app**: `~/Library/Application Support/com.trackeroo.desktop/trackeroo.db` — kept outside the (read-only) app bundle.

## Data model

v2's backend is a copy of v1's — the REST contract is identical, just served on port `8787` instead of `8000`. Full field-level detail lives in [`../v1/docs/api-contract.md`](../v1/docs/api-contract.md) and [`../v1/docs/openapi.json`](../v1/docs/openapi.json) rather than being duplicated here.

## Repo layout

```
backend/     FastAPI + SQLite REST API — a copy of v1/backend, fixed port 8787
frontend/    Svelte + Vite UI — a copy of v1/frontend, adapted for the Tauri webview
mcp/         MCP server — point TRACKEROO_API_URL at http://localhost:8787
src-tauri/   Rust shell: spawns/health-checks/kills the backend sidecar, hosts the webview
```

## Known gotchas

- **Cold-start delay**: the webview starts fetching before the sidecar is guaranteed to be listening. The release build's PyInstaller sidecar has real self-extraction overhead (~9s measured on this machine), so the app briefly shows a loading state before the board appears — this is expected, not a bug (see `CLAUDE.md` for the fix if you're modifying the frontend).
- **Unsigned build**: the `.app`/`.dmg` are ad-hoc signed only (no Apple Developer signing identity configured). macOS Gatekeeper will warn on first launch — right-click → Open, or allow via System Settings → Privacy & Security.
- **Sidecar binary naming**: must exactly match Tauri's `<name>-<target-triple>` convention — currently `trackeroo-backend-aarch64-apple-darwin` for Apple Silicon. See `src-tauri/tauri.conf.json`'s `bundle.externalBin`.

## Versioning

Same as v1 — see the repo-root `README.md`.
