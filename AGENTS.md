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
  first (the update script does this).
- **libEGL / DRI3 warnings** when launching the app are harmless (software GL
  fallback); the WebKit window still renders.
- **Testing the auto-updater on Linux needs a tmpfs.** The updater
  (`tauri-plugin-updater`) check/download/verify path works fine on the VM, but
  Tauri's **Linux AppImage installer** aborts with `temp directory is not on the
  same mount point as the AppImage`: it compares `st_dev` of the running app
  against the temp dir, and this container's **overlayfs/FUSE** does not report a
  consistent `st_dev` (the AppImage FUSE mount also runs in its own mount
  namespace, so in-process device IDs never match a writable temp dir). This is a
  Linux-path/container artifact only — the **macOS target uses a different
  install path with no such check**, so it doesn't affect the product. To drive a
  full detect→download→install→relaunch E2E locally: build a release with a
  **local** updater endpoint (`plugins.updater.endpoints` →
  `http://localhost:<port>/latest.json`, plus `"dangerousInsecureTransportProtocol":
  true` — revert both before committing), then run the **raw release binary**
  (`src-tauri/target/release/trackeroo`, not the AppImage) from a real **tmpfs**
  with `TMPDIR` pointing into it, so `st_dev` is consistent:
  `sudo mount -t tmpfs tmpfs /tmp/tfs && cp src-tauri/target/release/trackeroo /tmp/tfs/ && TMPDIR=/tmp/tfs DISPLAY=:1 /tmp/tfs/trackeroo`.
  Build a higher-version bundle, sign it (`TAURI_SIGNING_PRIVATE_KEY[_PASSWORD]`),
  and serve its `.AppImage` + a hand-written `latest.json` (platform key
  `linux-x86_64`, `signature` = contents of the `.AppImage.sig`) with
  `python3 -m http.server <port>`. See `v2/README.md` → "Releases & auto-updates".
