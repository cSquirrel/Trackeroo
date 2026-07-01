# Trackeroo

A lightweight, self-hosted project/task tracker: one instance manages one project, with epics → tasks, dependencies, blockers, comments/annotations, and links to PRs/Slack threads. Ships as a single Docker image. An MCP server lets AI agents CRUD tasks directly.

## Project Layout

```
backend/    FastAPI + SQLAlchemy + SQLite REST API
frontend/   Svelte + Vite kanban web UI
mcp/        Python MCP server (stdio), thin HTTP client of the backend API
docs/       api-contract.md — the source-of-truth REST contract all three above build against
```

## Stack

- **Backend**: Python, FastAPI, SQLAlchemy 2.0 (typed models), Pydantic v2, SQLite. Routers live in `backend/app/routers/`, one file per resource (project, swimlanes, epics, tasks). Tests in `backend/tests/` via pytest + FastAPI `TestClient`.
- **Frontend**: Svelte + TypeScript + Vite. API client lives in `frontend/src/lib/api.ts`, typed against `docs/api-contract.md`. Kanban drag-and-drop via a lightweight DnD library — no heavyweight state management framework, keep it small.
- **MCP server**: `mcp/server.py`, built on the `mcp` SDK's `FastMCP`, talks to the backend over HTTP via `httpx`. Reads `TRACKEROO_API_URL` (default `http://localhost:8000`). Never touches the database directly.

## Conventions

- `docs/api-contract.md` is the ground truth for every HTTP endpoint (method, path, request/response shape, status codes). If backend, frontend, or MCP behavior needs to diverge from it, update the contract file in the same change and call it out — don't let the three drift silently.
- Data model (Project, SwimLane, Epic, Task, TaskDependency, TaskLink, Comment) is defined once in `backend/app/models.py`; the contract's "Data model" section mirrors it. Check both stay in sync when adding fields.
- `POST` returns `201`, `PATCH` is partial-update (all fields optional), `DELETE` returns `204`, unknown ids return `404`, validation errors return `422`.
- Task dependencies are advisory, not enforced: moving a task into a done-column swimlane while it has open dependencies returns `200` with a `warnings[]` array rather than blocking the move.
- Keep dependencies minimal in every subproject — this is meant to stay a lightweight, easy-to-self-host tool, not a framework showcase.
- Static frontend build (`frontend/dist`) is served by the backend at `/` in the packaged Docker image (`backend/static/`); `/api/*` is the only other route surface.

## Testing

- Backend: `cd backend && pytest --cov=app --cov-report=term-missing`
- Frontend: `cd frontend && npm run test` (Vitest + @testing-library/svelte)
- E2E: Playwright suite (see `docs/` once Phase 3 lands) drives the built Docker stack end-to-end; a `@smoke` subset gates PRs, the full suite gates releases.
- MCP: integration suite exercises all MCP tools against a live backend instance.

## Running Locally

See root `README.md` for the Docker quickstart. For local dev without Docker: run `backend` with `uvicorn app.main:app --reload` (from `backend/`, with its venv active) and `frontend` with `npm run dev` (from `frontend/`, pointing `VITE_API_BASE_URL` at the backend).
