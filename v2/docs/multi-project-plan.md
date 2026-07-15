# TRA-6 — Multi-project single-instance support: implementation plan

## Background

Today Trackeroo is a desktop app where every project window is its own OS process
running its own backend instance. This is the right model for the "vault-style"
macOS app, but it makes a second use case awkward: running Trackeroo as a headless
system service (e.g. systemd) on a developer workstation or server, where a single
long-running API process should serve several projects simultaneously, multiple MCP
clients (one per code repo) connect to the same service each targeting different
projects, and a browser tab lets you switch between project boards without spawning
new processes.

This document is the design and implementation plan for that second mode.  The
desktop app model is entirely unchanged — no regressions, no forced migrations.

---

## Goals

1. A single FastAPI backend process can serve N project databases.
2. MCP clients can target a specific project on a shared server via
   `TRACKEROO_PROJECT_ID`.
3. The browser-based UI can list registered projects and switch between them.
4. The service is deployable as a systemd unit with zero extra dependencies.
5. The existing per-process desktop app workflow continues to work exactly as
   before.

---

## Non-goals (out of scope for this feature)

- Authentication / authorization (single-user local service only for now).
- A GUI or TUI for managing the service process itself.
- Breaking changes to the existing REST API.
- Merging project databases (projects stay in separate SQLite files).

---

## Architecture overview

```
┌────────────────────────────────────────────────────────────────┐
│  trackeroo-backend  (single long-running process)              │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Project registry  (~/.trackeroo/registry.json)          │ │
│  │  id │ name        │ folder_path                          │ │
│  │  1  │ "api-server"│ /home/alice/projects/api-server      │ │
│  │  2  │ "mobile"    │ /home/alice/projects/mobile-app      │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  Engine cache  { db_path → SQLAlchemy Engine }                 │
│                                                                │
│  Routes                                                        │
│    Legacy (single-project, backward-compat):                   │
│      GET  /api/project        → default DATABASE_URL project   │
│      GET  /api/tasks          → same                           │
│      ...                                                       │
│    New (multi-project):                                        │
│      GET  /api/projects                → list registry         │
│      POST /api/projects                → register a project    │
│      DELETE /api/projects/{id}         → unregister            │
│      GET  /api/projects/{id}/project   → project config        │
│      GET  /api/projects/{id}/tasks     → tasks for project id  │
│      ...  (all existing sub-routes mirrored)                   │
└────────────────────────────────────────────────────────────────┘
         ▲                     ▲                    ▲
  MCP (project 1)       MCP (project 2)       Browser UI
  TRACKEROO_PROJECT_ID=1  TRACKEROO_PROJECT_ID=2   (project switcher)
```

---

## Phased implementation plan

---

### Phase 1 — Backend: multi-project session factory + project registry API

**Goal:** A single backend process can serve any number of registered projects.
All existing routes are unchanged.

#### 1.1  Dynamic engine factory — `app/database.py`

Add `engine_for(db_path: str) -> Engine` next to the existing module-level
`engine`.  It maintains an LRU-bounded `dict[str, Engine]` (cap: 64 entries —
more than enough for local use).  Each entry is created lazily on first access
and reuses all existing `connect_args` / pragma hooks.

```python
_engine_cache: dict[str, Engine] = {}

def engine_for(db_path: str) -> Engine:
    """Return (or create-and-cache) an Engine for an absolute SQLite path."""
    key = str(Path(db_path).resolve())
    if key not in _engine_cache:
        url = f"sqlite:///{key}"
        eng = create_engine(url, connect_args={"check_same_thread": False})
        # attach same WAL + busy_timeout pragmas as the default engine
        _attach_sqlite_pragmas(eng)
        _engine_cache[key] = eng
    return _engine_cache[key]

def session_for(db_path: str) -> Generator[Session, None, None]:
    """FastAPI dependency: open a session against a specific project DB."""
    factory = sessionmaker(bind=engine_for(db_path), ...)
    db = factory()
    try:
        yield db
    finally:
        db.close()
```

#### 1.2  Project registry — `app/project_registry.py` (new file)

An in-memory + JSON-persisted list of registered projects.

```python
@dataclass
class RegisteredProject:
    id: int
    name: str
    folder: str   # absolute path to the project folder
```

Public API:
- `load_registry(path: Path)` — read from JSON; called at startup
- `save_registry(path: Path)` — write to JSON; called on every mutation
- `list_projects() -> list[RegisteredProject]`
- `add_project(folder: str, name: str | None) -> RegisteredProject` — raises if
  `.trackeroo/trackeroo.db` does not exist in `folder`
- `remove_project(id: int)` — unregisters (does NOT delete data)
- `get_project(id: int) -> RegisteredProject | None`

Registry location: `TRACKEROO_REGISTRY_PATH` env var (default:
`~/.trackeroo/registry.json`).  If `TRACKEROO_PROJECTS_DIR` is set, the
backend also auto-scans that directory for subfolders containing
`.trackeroo/trackeroo.db` and registers any not already in the registry.

#### 1.3  Project registry router — `app/routers/registry.py` (new file)

```
GET  /api/projects           → list[RegisteredProjectOut]
POST /api/projects           → RegisteredProjectOut
     body: { folder: str, name?: str }
DELETE /api/projects/{id}    → 204 No Content
```

#### 1.4  Per-project route prefix — `app/main.py`

Mount a second copy of the existing routers under
`/api/projects/{project_id}` using a dependency that:

1. Looks up `project_id` in the registry → gets `db_path`
2. Bootstraps the DB if not yet bootstrapped (idempotent `create_all` +
   migrations)
3. Returns a `Session` for that DB via `session_for(db_path)`

```python
# In main.py
from fastapi import APIRouter, Depends, Path, HTTPException

def get_project_db(project_id: int = Path(...)) -> Generator[Session, None, None]:
    proj = registry.get_project(project_id)
    if proj is None:
        raise HTTPException(404, f"Project {project_id} not found")
    ensure_bootstrapped(proj.db_path)
    yield from session_for(proj.db_path)

project_router = APIRouter(prefix="/api/projects/{project_id}")
project_router.include_router(project.router,    dependencies=[Depends(get_project_db)])
project_router.include_router(swimlanes.router,  dependencies=[Depends(get_project_db)])
project_router.include_router(epics.router,      dependencies=[Depends(get_project_db)])
project_router.include_router(tasks.router,      dependencies=[Depends(get_project_db)])

app.include_router(project_router)
```

> **Backward-compat note:** The existing module-level `get_db` (used by the
> existing `/api/...` routes) continues to reference the `DATABASE_URL`
> engine.  None of those routes change.

**Test coverage:**
- Unit tests for `engine_for` (same path → same object, different paths →
  different objects)
- Unit tests for `project_registry` (add, list, remove, auto-scan)
- Integration tests for `GET /api/projects`, `POST /api/projects`,
  `DELETE /api/projects/{id}`
- Integration tests for `GET /api/projects/1/tasks`, etc. (duplicate of
  existing task tests but via the new prefix)

---

### Phase 2 — MCP: project-aware tools

**Goal:** MCP clients can connect to a central server and operate on a specific
project by ID, without needing `TRACKEROO_PROJECT_PATH` at all.

#### 2.1  `TRACKEROO_PROJECT_ID` env var — `mcp/server.py`

```python
_PROJECT_ID = os.environ.get("TRACKEROO_PROJECT_ID")
```

When `_PROJECT_ID` is set (and `_EXPLICIT_API_URL` is also set — pointing at
the central server), all request paths are prefixed with
`/projects/{_PROJECT_ID}`:

```python
def _api_path(path: str) -> str:
    if _PROJECT_ID:
        return f"/projects/{_PROJECT_ID}{path}"
    return path
```

`_request(method, path, ...)` calls `_api_path(path)` before building the URL.

#### 2.2  `list_projects` tool — `mcp/server.py`

Available when no `TRACKEROO_PROJECT_ID` is set (discovery mode):

```python
@mcp.tool()
def list_projects() -> str:
    """List all projects registered on this Trackeroo server.

    Use this when TRACKEROO_PROJECT_ID is not set to discover which project IDs
    are available, then set TRACKEROO_PROJECT_ID in your MCP config to target
    one.
    """
    return _fmt(_request("GET", "/api/projects"))
```

#### 2.3  Documentation update — `mcp/README.md`

Add a "Central server mode" section explaining:
- How to start a central server
- How to register projects (`POST /api/projects`)
- The two MCP config patterns:
  ```json
  // Per-folder (existing, spawns its own backend):
  { "env": { "TRACKEROO_PROJECT_PATH": "/path/to/project" } }

  // Central server (new):
  { "env": { "TRACKEROO_API_URL": "http://localhost:8787",
             "TRACKEROO_PROJECT_ID": "1" } }
  ```

**Test coverage:**
- Unit test for `_api_path` with and without `_PROJECT_ID`
- Integration test exercising `list_projects` tool against a multi-project
  backend fixture

---

### Phase 3 — Frontend: project switcher

**Goal:** A browser can open the Trackeroo UI, see a list of projects, switch
between them without spawning new windows.

#### 3.1  Project-scoped API client — `frontend/src/lib/api.ts`

Add:
```typescript
let currentProjectId: number | null = null;

export function setProjectId(id: number | null): void {
  currentProjectId = id;
}

function projectPath(path: string): string {
  return currentProjectId !== null
    ? `/projects/${currentProjectId}${path}`
    : path;
}
```

The `request()` function calls `projectPath(path)` before constructing the URL.

Existing call-sites (`getProject()`, `listTasks()`, etc.) require no changes —
they still pass relative paths like `/tasks`; the prefix is injected
transparently.

Add new function:
```typescript
export const listRegisteredProjects = () =>
  request<RegisteredProject[]>("GET", "/projects");
```

#### 3.2  Store — `frontend/src/lib/store.svelte.ts`

Add `currentProjectId: number | null` to the store state.  `setCurrentProject(id)`
updates it, calls `setProjectId(id)` on the API client, and calls `loadAll()`.

#### 3.3  `ProjectList.svelte` (new component)

Displays the list from `GET /api/projects`.  Each entry shows project name and
folder.  Clicking one calls `store.setCurrentProject(id)` → board loads.
Includes a "Register new project" mini-form (folder path + optional name).

#### 3.4  Service-mode detection — `frontend/src/App.svelte`

Tauri injects `window.__TAURI__` into the webview.  In a plain browser it is
absent.  Use this to choose the right startup path:

```typescript
const isTauri = !!window.__TAURI__;
```

- **Tauri (desktop app):** existing path unchanged — resolve CLI launch target,
  show picker, open project, show board.
- **Browser (service mode):** skip the picker; show `ProjectList.svelte`.
  Once a project is chosen, show `BoardApp.svelte` with a "← Projects" button
  that returns to the list.

#### 3.5  `BoardApp.svelte`

In service mode, show a "← Projects" button in the top-bar that calls
`store.clearProject()` (resets `currentProjectId`, unloads the board, shows
`ProjectList` again).  In Tauri mode the button is unchanged (it spawns a new
window as before).

**Test coverage:**
- Unit tests for `projectPath()` with and without a project ID set
- Component test for `ProjectList` (renders project names, calls
  `setCurrentProject` on click)

---

### Phase 4 — Service mode: deployment and docs

**Goal:** Someone can set up Trackeroo as a persistent system service in under
10 minutes.

#### 4.1  `docs/service-mode.md` (new file)

Covers:
1. Starting the backend manually (the same `uvicorn` / `run_sidecar.py` command)
2. Registering projects via `curl` / `POST /api/projects`
3. Pointing MCP clients at the service
4. Accessing the web UI (serve `frontend/dist/` with any static file server, or
   add a static-files mount to the FastAPI app)
5. Systemd deployment

#### 4.2  `docs/service/trackeroo.service` (new file)

Example systemd unit:
```ini
[Unit]
Description=Trackeroo task-board backend
After=network.target

[Service]
Type=simple
User=alice
Environment="DATABASE_URL=sqlite:////home/alice/.trackeroo/default.db"
Environment="TRACKEROO_REGISTRY_PATH=/home/alice/.trackeroo/registry.json"
Environment="TRACKEROO_PORT=8787"
ExecStart=/home/alice/.venv/bin/python /home/alice/trackeroo/v2/backend/run_sidecar.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

#### 4.3  Optional: static frontend serving — `backend/app/main.py`

If `TRACKEROO_SERVE_FRONTEND` env var is set to a directory path, mount the
built frontend as a static site at `/`:

```python
from fastapi.staticfiles import StaticFiles
if frontend_dir := os.environ.get("TRACKEROO_SERVE_FRONTEND"):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
```

This lets the single backend process serve both the API and the UI.

---

## Key design decisions

| Question | Decision | Rationale |
|---|---|---|
| Per-project DB or merged DB? | Separate files (existing layout) | Projects stay portable; no DB migration |
| Registry storage | `~/.trackeroo/registry.json` | Zero extra dependency; human-readable |
| New API prefix | `/api/projects/{id}/...` alongside existing `/api/...` | Existing deployments untouched |
| MCP routing | `TRACKEROO_PROJECT_ID` + `TRACKEROO_API_URL` | One env var change per MCP client |
| Frontend mode switch | `window.__TAURI__` detection | Desktop app entirely unchanged |
| Auth | None (out of scope) | Local single-user service |

---

## Files changed (summary)

### Backend (`v2/backend/`)
| File | Change |
|---|---|
| `app/database.py` | Add `engine_for()`, `session_for()` |
| `app/main.py` | Mount project-scoped router; load registry; optional static files |
| `app/project_registry.py` | **New** — registry dataclass + JSON persistence |
| `app/routers/registry.py` | **New** — `GET/POST/DELETE /api/projects` |
| `app/dependencies.py` | **New** — `get_project_db` FastAPI dependency |
| `tests/` | New tests for registry + multi-project routes |

### MCP (`v2/mcp/`)
| File | Change |
|---|---|
| `server.py` | `TRACKEROO_PROJECT_ID` support; `list_projects` tool |
| `README.md` | Central server mode docs |
| `tests/` | Multi-project integration test |

### Frontend (`v2/frontend/`)
| File | Change |
|---|---|
| `src/lib/api.ts` | `setProjectId()`; `projectPath()`; `listRegisteredProjects()` |
| `src/lib/store.svelte.ts` | `currentProjectId`; `setCurrentProject()` |
| `src/App.svelte` | Service-mode branch |
| `src/lib/BoardApp.svelte` | "← Projects" button in service mode |
| `src/lib/ProjectList.svelte` | **New** — project list + switcher |

### Docs (`v2/docs/`)
| File | Change |
|---|---|
| `service-mode.md` | **New** — deployment guide |
| `service/trackeroo.service` | **New** — systemd example |

---

## Open questions before implementation begins

1. **Static frontend serving:** Is bundling frontend serving into the backend
   the right approach, or should we document a separate nginx/caddy setup?
2. **Registry path default:** `~/.trackeroo/registry.json` assumes a user-home
   path on the service host.  Should it default to a path relative to the
   backend's working directory instead?
3. **Auto-scan scope:** If `TRACKEROO_PROJECTS_DIR` is set, should the backend
   auto-register new projects that appear while running (inotify watch), or
   only on startup?
4. **Frontend build:** The `tauri dev` flow builds the frontend inside the
   Tauri context.  For service mode, `npm run build` in `frontend/` produces
   a standalone `dist/`.  Should the README document this explicitly?
