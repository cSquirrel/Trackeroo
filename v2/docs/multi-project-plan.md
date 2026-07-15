# TRA-6 — Multi-project single-instance: implementation plan

## Vision

The **backend is the centerpiece.** One long-running Trackeroo service manages
all your projects. Any number of MCP clients connect to it — each scoped to a
different project — and any number of browser/desktop UI clients connect to it
and can switch between projects freely.

```
                    ┌──────────────────────────────────────┐
                    │   trackeroo-backend  (system service) │
                    │                                      │
                    │  Project registry                    │
                    │  ┌────┬──────────────┬─────────────┐ │
                    │  │ id │ name         │ folder       │ │
                    │  │  1 │ "api-server" │ ~/repos/api  │ │
                    │  │  2 │ "mobile-app" │ ~/repos/mob  │ │
                    │  │  3 │ "infra"      │ ~/repos/infra│ │
                    │  └────┴──────────────┴─────────────┘ │
                    │                                      │
                    │  Per-project SQLite DB (existing      │
                    │  .trackeroo/ layout, no migration)    │
                    └──────────────────────────────────────┘
                         ▲            ▲            ▲
           ┌─────────────┤            │            ├─────────────┐
           │             │            │            │             │
    MCP client     MCP client     Browser UI   Desktop app  MCP client
  (Claude Code,  (Claude Code,   (project     (Tauri,       (any IDE,
   project 1)     project 2)      switcher)    project 3)    project N)
```

The desktop Tauri app stays fully functional and is just one of many clients —
it uses the backend exactly as it does today (spawning its own per-project
instance when running standalone).

---

## Goals

1. A single FastAPI backend process manages N projects, each in its own SQLite
   database.
2. MCP clients target a project by ID on the shared service — no per-project
   backend processes needed.
3. The web UI lists all registered projects and lets you switch between boards
   without spawning new processes.
4. Registering a project is a single API call (give the service a folder path).
5. The service is self-contained: optionally serves the built frontend itself,
   so there is nothing to deploy beyond the backend process.
6. Existing single-project and desktop-app deployments continue to work
   unchanged.

---

## Non-goals (out of scope for now)

- Authentication / multi-user access control.
- Breaking changes to the existing single-project REST API.
- Forcing per-project database migration or merging databases.

---

## Architecture

### Data layer: per-project SQLite, dynamic engine cache

Each project's data lives in `<folder>/.trackeroo/trackeroo.db` — exactly the
existing layout. Nothing moves. A new `engine_for(db_path)` function
maintains a cached `dict[str, Engine]` so the service keeps open connections to
each project's DB without recreating engines on every request.

### Project registry

A lightweight JSON file (`~/.trackeroo/registry.json` by default; configurable
via `TRACKEROO_REGISTRY_PATH`) stores the list of registered projects:

```json
[
  { "id": 1, "name": "api-server", "folder": "/home/alice/repos/api-server" },
  { "id": 2, "name": "mobile-app", "folder": "/home/alice/repos/mobile-app" }
]
```

On startup, if `TRACKEROO_PROJECTS_DIR` is set, the service also auto-scans
that directory for project folders and registers any new ones.

### API routing: project-scoped prefix

Every existing route (`/api/tasks`, `/api/epics`, etc.) is also available under
`/api/projects/{id}/tasks`, `/api/projects/{id}/epics`, etc. A FastAPI
dependency resolves the project ID → DB session transparently. The old flat
routes continue to work for single-project deployments pointing at `DATABASE_URL`.

### MCP: service-first configuration

The primary MCP config for the service scenario is two env vars:

```
TRACKEROO_API_URL=http://localhost:8787   # URL of the central service
TRACKEROO_PROJECT_ID=2                    # which project this client targets
```

The existing `TRACKEROO_PROJECT_PATH` auto-spawn mode continues to work for
people who don't run the service.

### UI: project list is the home screen

When the frontend connects to a multi-project service (detected via the
presence of the `GET /api/projects` endpoint returning multiple entries, or via
a `window.__TAURI__` absence check), it shows a project-list home screen
instead of the single-project picker. Clicking a project loads that project's
board. A "← Projects" button in the board top-bar returns to the list.

---

## Phased implementation plan

---

### Phase 1 — Backend: multi-project API

This phase makes the backend service-ready. The frontend and MCP are unchanged.

#### 1.1  Dynamic engine factory — `app/database.py`

```python
_engine_cache: dict[str, Engine] = {}

def engine_for(db_path: str) -> Engine:
    key = str(Path(db_path).resolve())
    if key not in _engine_cache:
        eng = create_engine(
            f"sqlite:///{key}",
            connect_args={"check_same_thread": False},
        )
        _attach_sqlite_pragmas(eng)   # same WAL + busy_timeout as today
        _engine_cache[key] = eng
    return _engine_cache[key]

def get_db_for(db_path: str) -> Generator[Session, None, None]:
    factory = sessionmaker(bind=engine_for(db_path), ...)
    db = factory()
    try:
        yield db
    finally:
        db.close()
```

#### 1.2  Project registry — `app/project_registry.py` (new)

```python
@dataclass
class RegisteredProject:
    id: int
    name: str
    folder: str          # absolute path
    db_path: str         # folder/.trackeroo/trackeroo.db
```

Functions:
- `load(path)` / `save(path)` — JSON round-trip
- `list_projects()`, `get_project(id)`, `get_project_by_folder(folder)`
- `add_project(folder, name=None)` — validates DB exists; auto-names from folder
- `remove_project(id)` — unregisters only; does not touch data
- `scan_dir(root)` — auto-registers all sub-folders that contain a project DB

Startup sequence in `app/main.py` lifespan:
1. Load registry from `TRACKEROO_REGISTRY_PATH`
2. If `TRACKEROO_PROJECTS_DIR` set → `scan_dir()` and merge
3. For each registered project: run bootstrap (idempotent `create_all` +
   schema migrations) so the service is ready to serve without any warm-up
   call

#### 1.3  Registry router — `app/routers/registry.py` (new)

```
GET  /api/projects              → list[RegisteredProjectOut]
POST /api/projects              → RegisteredProjectOut
     body: { folder, name? }
DELETE /api/projects/{id}       → 204
```

`POST /api/projects` validates that `.trackeroo/trackeroo.db` exists (or creates
it with `create=true` query param) before registering.

#### 1.4  Project-scoped sub-routes — `app/main.py`

```python
def get_project_session(
    project_id: int = Path(...),
    registry: ProjectRegistry = Depends(get_registry),
) -> Generator[Session, None, None]:
    proj = registry.get_project(project_id)
    if not proj:
        raise HTTPException(404, f"Project {project_id} not registered")
    yield from get_db_for(proj.db_path)

scoped = APIRouter(prefix="/api/projects/{project_id}")
scoped.include_router(project.router)
scoped.include_router(swimlanes.router)
scoped.include_router(epics.router)
scoped.include_router(tasks.router)
# Inject the project-scoped DB dependency for all routes in this router:
app.include_router(scoped, dependencies=[Depends(get_project_session)])
```

Each existing router already accepts `db: Session = Depends(get_db)`.  The
`get_project_session` dependency *overrides* `get_db` for the scoped router,
so no router internals change.

**Test additions:**
- `test_project_registry.py` — unit tests for all registry operations
- `test_registry_router.py` — integration tests for `GET/POST/DELETE /api/projects`
- `test_multi_project_routes.py` — integration tests confirming data isolation
  (project 1 tasks invisible to project 2 routes and vice versa)

---

### Phase 2 — MCP: service-mode connection

#### 2.1  `TRACKEROO_PROJECT_ID` — `mcp/server.py`

```python
_PROJECT_ID = os.environ.get("TRACKEROO_PROJECT_ID")

def _api_path(path: str) -> str:
    """Prefix with /projects/{id} when connecting to a central service."""
    if _PROJECT_ID:
        return f"/projects/{_PROJECT_ID}{path}"
    return path
```

`_request()` calls `_api_path(path)` before building the URL.  All 15 existing
tools require no other changes.

Priority / override table:

| Env vars set | Behaviour |
|---|---|
| `TRACKEROO_API_URL` + `TRACKEROO_PROJECT_ID` | Hit central service, project-scoped |
| `TRACKEROO_API_URL` only | Hit that URL directly (existing override mode) |
| `TRACKEROO_PROJECT_PATH` only | Discover-or-spawn per-project backend (existing) |
| Neither | Fall back to `http://localhost:8000` (existing default) |

#### 2.2  `list_projects` tool

```python
@mcp.tool()
def list_projects() -> str:
    """List all projects registered on this Trackeroo service.

    Use this to discover available project IDs before setting
    TRACKEROO_PROJECT_ID in your MCP config, or to check what projects
    an agent can see.
    """
    return _fmt(_request("GET", "/api/projects"))
```

#### 2.3  `mcp/README.md` — new "Service mode" section

Shows both config patterns side-by-side:

```json
// Option A — per-folder (existing; spawns backend on demand):
{
  "trackeroo": {
    "command": "…/trackeroo-mcp",
    "env": { "TRACKEROO_PROJECT_PATH": "/path/to/my-project" }
  }
}

// Option B — central service (new; no per-project processes):
{
  "trackeroo-api": {
    "command": "…/trackeroo-mcp",
    "env": {
      "TRACKEROO_API_URL": "http://localhost:8787",
      "TRACKEROO_PROJECT_ID": "1"
    }
  }
}
```

Multiple MCP servers in one config, each with a different `TRACKEROO_PROJECT_ID`,
is the recommended pattern for multi-repo setups.

**Test additions:**
- Unit test for `_api_path` with and without `_PROJECT_ID`
- Integration test for `list_projects` against a two-project fixture

---

### Phase 3 — Frontend: project list and switcher

#### 3.1  Project-scoped API — `frontend/src/lib/api.ts`

```typescript
let _projectId: number | null = null;

export function setProjectId(id: number | null) { _projectId = id; }

function projectPath(p: string) {
  return _projectId !== null ? `/projects/${_projectId}${p}` : p;
}
// request() wraps every path through projectPath() — all existing callers unchanged
```

New export:
```typescript
export const listRegisteredProjects = () =>
  request<RegisteredProject[]>("GET", "/projects");
```

#### 3.2  Store — `src/lib/store.svelte.ts`

Add `currentProjectId: number | null`.  `switchProject(id)` updates it, calls
`setProjectId(id)`, and triggers `loadAll()`.  `clearProject()` resets state
and returns to the project list.

#### 3.3  `ProjectList.svelte` (new component)

- Calls `listRegisteredProjects()` on mount
- Renders each project as a card: name, folder path, "Open board →" action
- "Register project" form: folder path input → calls `POST /api/projects`
- Refreshes list on registration

#### 3.4  Mode detection and routing — `src/App.svelte`

```typescript
// Tauri injects window.__TAURI_INTERNALS__; its absence means plain browser
const isTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
```

- **Tauri (desktop app):** existing startup path — resolve CLI arg, picker,
  board.  Zero change.
- **Browser (service mode):** skip picker; mount `ProjectList`. User picks a
  project → `store.switchProject(id)` → board loads.  Board top-bar shows "←
  Projects" instead of "Open project…"; clicking it calls `store.clearProject()`
  and returns to `ProjectList`.

#### 3.5  `BoardApp.svelte`

Accept `serviceMode: boolean` prop (false by default for Tauri compat).  In
service mode, replace the "Open project…" button with "← Projects".

**Test additions:**
- Unit tests for `projectPath()` with / without project ID
- `ProjectList` component test: renders names, calls `switchProject` on click,
  POST on register

---

### Phase 4 — Service packaging and docs

#### 4.1  Built-in frontend serving — `app/main.py`

```python
if dist := os.environ.get("TRACKEROO_SERVE_FRONTEND"):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=dist, html=True))
```

Set `TRACKEROO_SERVE_FRONTEND=/path/to/frontend/dist` and the single backend
process serves both the API and the UI at the same port.

#### 4.2  `docs/service-mode.md` (new)

End-to-end guide:
1. Start the service (`uvicorn` / `run_sidecar.py` + env vars)
2. Register projects (`curl -X POST /api/projects`)
3. Configure MCP clients (Option A vs Option B patterns)
4. Open the web UI in a browser
5. Systemd deployment

#### 4.3  `docs/service/trackeroo.service` (new)

```ini
[Unit]
Description=Trackeroo task-board service
After=network.target

[Service]
Type=simple
User=%i
Environment=TRACKEROO_REGISTRY_PATH=%h/.trackeroo/registry.json
Environment=TRACKEROO_PROJECTS_DIR=%h/repos
Environment=TRACKEROO_PORT=8787
Environment=TRACKEROO_SERVE_FRONTEND=/opt/trackeroo/frontend/dist
ExecStart=/opt/trackeroo/.venv/bin/python /opt/trackeroo/run_sidecar.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

---

## Design decisions

| Decision point | Choice | Why |
|---|---|---|
| One DB vs per-project DBs | Per-project SQLite files | Portable projects; no forced migration |
| Registry storage | JSON file | Zero extra dependency; human-readable and vcs-friendly |
| API compat | New `/api/projects/{id}/...` prefix; old `/api/...` unchanged | Zero breakage |
| MCP primary config | `TRACKEROO_API_URL` + `TRACKEROO_PROJECT_ID` | Clean; one env var per project per MCP client |
| Frontend mode switch | `window.__TAURI_INTERNALS__` presence | Desktop app unchanged; no feature flag needed |
| Frontend serving | Optional via `TRACKEROO_SERVE_FRONTEND` | No nginx required for simple deployments |

---

## Files touched (summary)

### `v2/backend/`
| File | Change |
|---|---|
| `app/database.py` | + `engine_for()`, `get_db_for()` |
| `app/main.py` | + registry startup, project-scoped router, optional static files |
| `app/project_registry.py` | **new** |
| `app/routers/registry.py` | **new** — `/api/projects` CRUD |
| `app/dependencies.py` | **new** — `get_project_session` dependency |
| `tests/test_project_registry.py` | **new** |
| `tests/test_registry_router.py` | **new** |
| `tests/test_multi_project_routes.py` | **new** |

### `v2/mcp/`
| File | Change |
|---|---|
| `server.py` | + `TRACKEROO_PROJECT_ID`, `_api_path()`, `list_projects` tool |
| `README.md` | + service-mode config section |
| `tests/test_service_mode.py` | **new** |

### `v2/frontend/`
| File | Change |
|---|---|
| `src/lib/api.ts` | + `setProjectId()`, `projectPath()`, `listRegisteredProjects()` |
| `src/lib/store.svelte.ts` | + `currentProjectId`, `switchProject()`, `clearProject()` |
| `src/App.svelte` | + service-mode branch |
| `src/lib/BoardApp.svelte` | + `serviceMode` prop, "← Projects" button |
| `src/lib/ProjectList.svelte` | **new** |

### `v2/docs/`
| File | Change |
|---|---|
| `service-mode.md` | **new** |
| `service/trackeroo.service` | **new** |

---

## Open questions

1. **New-project creation via service:** Should `POST /api/projects` accept a
   `create: true` flag to initialise a fresh DB in a new folder (mirroring the
   desktop picker's "New project" action)?  Or is registration-of-existing-folders-only
   the right scope for now?

2. **Registry path default:** `~/.trackeroo/registry.json` works fine on a
   developer machine.  For a system-wide service, something under `/var/lib`
   or relative to the install path may be more appropriate — should the default
   be configurable via the systemd unit without env var gymnastics?

3. **Auto-scan at runtime:** `TRACKEROO_PROJECTS_DIR` scan runs only at
   startup today.  Should the service watch for new sub-folders (inotify) so a
   newly cloned repo is auto-registered without a service restart?

4. **`TRACKEROO_PROJECT_ID` as a path alias:** Should the MCP server also
   accept a folder path as a project identifier (resolved via `GET
   /api/projects?folder=...`) so users don't need to know the numeric ID?
