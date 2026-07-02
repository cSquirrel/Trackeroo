# Trackeroo REST API Contract

The canonical, machine-readable contract is [`docs/openapi.json`](openapi.json) —
an OpenAPI 3.1 spec generated directly from the FastAPI app (routes + Pydantic
schemas), so it can never drift from the actual request/response shapes the
way a hand-written doc can.

- **Browse interactively**: run the backend and open `http://localhost:8000/docs`
  (Swagger UI) or `/redoc`.
- **Regenerate after any route/schema change**:
  ```bash
  cd backend && .venv/bin/python -m app.export_openapi
  ```
  Commit the updated `docs/openapi.json` in the same change as the code that
  produced it. Do not hand-edit `openapi.json`.
- **Client generation**: any OpenAPI-compatible tool can generate a typed
  client from this file (e.g. `openapi-typescript` for the frontend).

All endpoints are prefixed with `/api`. Request and response bodies are JSON.
Timestamps are ISO 8601 strings (UTC).

## Conventions (not fully expressible in the OpenAPI schema)

- `POST` creating a resource returns `201 Created` with the created resource.
- `PATCH` is a partial update: every field optional; omitted fields are unchanged.
- `DELETE` returns `204 No Content` with an empty body.
- Unknown id in a path returns `404 Not Found`: `{"detail": "..."}`.
- Validation errors return `422 Unprocessable Entity` (FastAPI default shape).

## Business rules worth calling out

- **Dependencies are advisory, not enforced.** `POST /api/tasks/{id}/move` into
  a done-column swimlane never hard-blocks on open dependencies — it succeeds
  (`200`) and returns a `warnings: string[]` array describing which
  dependencies are still open.
- **Dependency validation on `POST /api/tasks/{id}/dependencies`:** `400` for a
  self-dependency, `409` for a duplicate (same task_id/depends_on_task_id
  pair), `422` for an immediate cycle (A depends on B, B already depends on
  A). Only the direct/immediate cycle is checked — full transitive-cycle
  detection is out of scope for this lightweight tool.
- **`GET /api/tasks/{id}` returns full `TaskDependency` rows** (with their own
  `id`) under `dependencies`, not bare `depends_on_task_id` values — the `id`
  is required to call `DELETE /api/tasks/{id}/dependencies/{dependency_id}`.
- **Cascades**: deleting a task removes its comments, links, and dependency
  rows. Deleting an epic sets `task.epic_id` to `null` on its tasks. Deleting
  a swimlane cascades to its tasks — callers that want to preserve those tasks
  must move them to another swimlane first (`PATCH` each task's
  `swimlane_id`) before deleting. `DELETE /api/swimlanes/{id}` returns `400`
  if it's the project's last remaining swimlane — at least one must always
  exist.
- **Default seed data**: on first boot with no `Project` row, the backend
  creates one default project and seeds five swimlanes — Backlog, To Do, In
  Progress, Review, Done (Done has `is_done_column = true`).
