# Trackeroo

> **v1 implementation.** This file covers conventions specific to the current (v1) implementation — not the product overview, quickstart, or command reference, which live in `README.md`. All paths below are relative to `v1/` — `cd` into `v1/` before running any commands here.

## Stack

- **Backend**: Python, FastAPI, SQLAlchemy 2.0 (typed models), Pydantic v2, SQLite. Routers live in `backend/app/routers/`, one file per resource (project, swimlanes, epics, tasks). Tests in `backend/tests/` via pytest + FastAPI `TestClient`.
- **Frontend**: Svelte + TypeScript + Vite. API client lives in `frontend/src/lib/api.ts`, typed against `docs/openapi.json`. Kanban drag-and-drop via a lightweight DnD library — no heavyweight state management framework, keep it small.
- **MCP server**: `mcp/server.py`, built on the `mcp` SDK's `FastMCP`, talks to the backend over HTTP via `httpx`. Reads `TRACKEROO_API_URL` (default `http://localhost:8000`). Never touches the database directly.

## Conventions

- `docs/openapi.json` is the ground truth for every HTTP endpoint (method, path, request/response shape, status codes) — it's generated from the FastAPI app, never hand-edited. After any route/schema change, regenerate it: `cd backend && python -m app.export_openapi`, and commit the diff alongside the code change. `docs/api-contract.md` holds only the conventions and business rules OpenAPI can't express (soft-warning semantics, cascade behavior, seed data).
- Data model (Project, SwimLane, Epic, Task, TaskDependency, TaskLink, Comment) is defined once in `backend/app/models.py`; regenerating `docs/openapi.json` keeps the contract in sync automatically.
- `POST` returns `201`, `PATCH` is partial-update (all fields optional), `DELETE` returns `204`, unknown ids return `404`, validation errors return `422`.
- Task dependencies are advisory, not enforced: moving a task into a done-column swimlane while it has open dependencies returns `200` with a `warnings[]` array rather than blocking the move.
- Keep dependencies minimal in every subproject — this is meant to stay a lightweight, easy-to-self-host tool, not a framework showcase.
- Static frontend build (`frontend/dist`) is served by the backend at `/` in the packaged Docker image (`backend/static/`); `/api/*` is the only other route surface.

## Testing & running locally

See `README.md`'s "Testing", "Local development", and "CI" sections for exact commands — this file covers conventions only, not command reference.
