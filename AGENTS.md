# AGENTS.md

Repo-wide conventions live in `CLAUDE.md` and `README.md`; the app implementation
lives under `v2/` (see `v2/README.md` and `v2/CLAUDE.md`). Read those first.

## Cursor Cloud specific instructions

Trackeroo is packaged as a **native macOS Tauri desktop app**, but on the Linux
cloud VM the full dev stack (Rust Tauri shell + Python FastAPI backend + Svelte
webview) does run — the Rust code is `cfg(unix)`, not macOS-only. All commands
below assume `cd v2` first; standard commands are documented in `v2/README.md`
and `v2/CLAUDE.md` — this section only records the non-obvious cloud gotchas.

### Services / how to run

- **Backend** (`v2/backend`, FastAPI + SQLite): the Tauri shell spawns it from
  `backend/.venv/bin/uvicorn`. To run it standalone, point it at a DB and port:
  `DATABASE_URL=sqlite:////abs/path/trackeroo.db TRACKEROO_PORT=8787 .venv/bin/python run_sidecar.py`
  (or `.venv/bin/uvicorn app.main:app --port 8787`). It has no fixed port in the app.
- **Frontend** (`v2/frontend`, Svelte + Vite): `npm run dev` serves on the fixed
  port `1420` (Tauri requires it). `npm run test` (vitest), `npm run check`
  (svelte-check), `npm run build`.
- **Full app**: `cd v2 && npm run dev` runs `tauri dev` — compiles the Rust shell
  and opens a native GTK/WebKit window. A display is available at `DISPLAY=:1`, so
  run it with `export DISPLAY=:1`. First Rust build downloads/compiles ~500 crates
  (minutes); later builds are fast.
- **MCP** (`v2/mcp`, Python): stdio MCP server; `backend_spawn.py` spawns the
  backend from `backend/.venv` on demand.

### Non-obvious gotchas (these will bite you otherwise)

- **Rust toolchain must be recent.** Some transitive crates need `edition2024`
  (Rust ≥ 1.85). The VM's Rust is updated to current stable via `rustup update
  stable`; if `tauri dev` fails with "feature `edition2024` is required", run that.
- **Tauri build needs sidecar placeholders.** `src-tauri/tauri.conf.json`'s
  `bundle.externalBin` lists `binaries/trackeroo-backend` and
  `binaries/trackeroo-mcp`, so the build script fails unless
  `src-tauri/binaries/trackeroo-backend-x86_64-unknown-linux-gnu` and
  `...-mcp-...` exist. These are the PyInstaller sidecars (macOS-only, gitignored).
  In **dev** they are never executed (the shell spawns the backend from
  `backend/.venv`), so creating empty executable placeholder files at those two
  paths is enough to let `tauri dev` build. Create them if missing.
- **Skip the native picker** by launching with a project folder path directly:
  `DISPLAY=:1 src-tauri/target/debug/trackeroo /some/folder` opens straight to the
  board (a fresh folder becomes a new project). Handy for driving the board in
  tests without the GTK folder dialog.
- **Backend pytest**: run as `.venv/bin/python -m pytest` from `v2/backend` (plain
  `.venv/bin/pytest` fails with `ModuleNotFoundError: app` — the package dir must
  be on `sys.path`). It also needs `v2/backend/data/` to exist first: the test
  fixture opens `sqlite:///./data/test.db` before the app auto-creates that dir, so
  run `mkdir -p v2/backend/data` once.
- **MCP tests**: both suites spawn the real backend from `backend/.venv` (no
  Docker). `pytest` from `v2/mcp` runs everything; `tests/` is the tool-level
  integration suite (session-scoped backend) and `tests_spawn/` covers
  `backend_spawn.py` (per-test backends; needs `lsof`). Create `backend/.venv`
  first (the update script does this). `pytest` itself is a test-only dep in
  `mcp/tests/requirements.txt` (not `mcp/requirements.txt`), so the `mcp/.venv`
  must have both installed — the update script does this.
- **`npm ci` works at the `v2/` root but NOT in `frontend/`.** The committed
  `frontend/package-lock.json` was generated on macOS and omits Linux-only
  optional deps (e.g. `@emnapi/runtime`), so `npm ci` there fails with "Missing:
  ... from lock file". Use `npm install` for the frontend; the update script runs
  `npm install --no-package-lock` so the platform resolution doesn't dirty the
  committed lockfile.
- **libEGL / DRI3 warnings** when launching the app are harmless (software GL
  fallback); the WebKit window still renders.
