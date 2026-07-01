# Trackeroo (v2 — Tauri desktop app)

> **v2 implementation.** This file covers the Tauri desktop-app implementation. All paths below are relative to `v2/` — `cd` into `v2/` before running any commands here.

A lightweight, self-hosted project/task tracker: one instance manages one project, with epics → tasks, dependencies, blockers, comments/annotations, and links to PRs/Slack threads. v2 packages this as a native macOS desktop app (Tauri) instead of a Docker-hosted web service — the confirmed use case is single-user, single-machine, no remote access ever, which fits a native app better than a self-hosted server.

## Project Layout

```
backend/     FastAPI + SQLite REST API — a copy of v1/backend, fixed port 8787
frontend/    Svelte + Vite UI — a copy of v1/frontend, adapted for the Tauri webview
mcp/         MCP server — point TRACKEROO_API_URL at http://localhost:8787
src-tauri/   Rust shell: spawns/health-checks/kills the backend sidecar, hosts the webview
```

## Stack

- **Shell**: Tauri v2 (Rust), `src-tauri/src/lib.rs`. Spawns the backend on startup, polls `/api/health`, shows the window once healthy (starts with `visible: false` in `tauri.conf.json`), and kills the backend on exit — handles both GUI quit (`RunEvent::Exit`/`RunEvent::ExitRequested`) and POSIX signals (SIGINT/SIGTERM/SIGHUP via a `ctrlc` handler), since a bare `kill` of the app process wouldn't otherwise reap the backend child.
- **Backend**: identical to v1's (FastAPI + SQLAlchemy + SQLite) — a **copy**, not shared code. Fixed port `8787` (vs v1's `8000`) so both versions can run simultaneously without colliding. Dev mode spawns it from `backend/.venv/bin/uvicorn` directly (`cfg(debug_assertions)` path in `lib.rs`); release mode spawns a PyInstaller-bundled binary next to the app executable (`cfg(not(debug_assertions))` path). `backend/run_sidecar.py` is the PyInstaller entry point (kept separate from `app/` so PyInstaller has a concrete script target).
- **Frontend**: same Svelte app as v1, adapted: API base URL defaults to the absolute `http://localhost:8787/api` in `frontend/src/lib/api.ts` (not same-origin — the webview loads via Tauri's own asset scheme, not from the backend's origin, so a relative `/api` path would not resolve). Vite dev server is pinned to port `1420` (`strictPort: true`) since Tauri's `devUrl` in `tauri.conf.json` expects a fixed port.
- **MCP server**: identical to v1's, just pointed at port `8787` via `TRACKEROO_API_URL`.

## Conventions

- `backend/`, `frontend/`, and `mcp/` here are **copies** of v1's, not shared code. If you fix a bug in v1 that also applies here (or vice versa), port the fix manually — nothing propagates automatically.
- Data model / REST contract is identical to v1's — see `../v1/docs/api-contract.md` and `../v1/docs/openapi.json`. Don't duplicate or fork them here; if the contract changes, it changes in v1's backend/schemas first, and the change gets ported into `v2/backend` deliberately.
- The fixed backend port is `8787`, chosen specifically to differ from v1's `8000` so both versions can run at once during development without conflict.
- **Cold-start retry is load-bearing, not defensive boilerplate.** `frontend/src/lib/store.svelte.ts`'s initial `loadAll()` retries the first fetch for up to 30s (60 attempts × 500ms). This fixes a real, verified bug: the webview starts fetching before the sidecar is guaranteed to be listening, and the release build's PyInstaller sidecar has real self-extraction overhead (~9s measured). Removing or shortening this without understanding why it's there will reintroduce a "Load failed" banner on cold launch.
- **Backend kill logic must target the whole process group.** The release sidecar binary is a PyInstaller bootloader that forks the real Python server as a child process — killing only the direct child (the bootloader) orphans the server and leaves port `8787` held. `kill_backend()` in `lib.rs` sends `SIGKILL` to the negated PID (the process group) for exactly this reason; the backend is spawned with `process_group(0)` to make itself a group leader.
- Sidecar binary naming must exactly match Tauri's `<name>-<target-triple>` convention (currently `trackeroo-backend-aarch64-apple-darwin`) — see `bundle.externalBin` in `src-tauri/tauri.conf.json`. The compiled binary and PyInstaller build artifacts are gitignored; rebuild them after a fresh clone or backend change (see `README.md`).

## Testing

- Backend/frontend: same commands as v1 since the code is a copy (`cd backend && pytest --cov=app --cov-report=term-missing`, `cd frontend && npm run test`).
- No dedicated v2 E2E suite or CI wiring exists yet — v1's `e2e/` and `.github/workflows/ci.yml` do not cover v2 at all. Verify changes manually via `npm run dev`, or by rebuilding and launching the `.app` (a cold-start launch, not just `tauri dev`, is the more representative test — see the cold-start gotcha above).

## Running locally

`npm run dev` for hot-reload dev mode, or `npm run build` then open the produced `.app` for a release-mode check — see `README.md` for the full setup including the one-time backend venv and PyInstaller steps.
