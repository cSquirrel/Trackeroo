# Trackeroo REST API Contract

Definitive contract for Phase 1B (backend), 1C (frontend), and 1D (MCP server).
All endpoints are prefixed with `/api`. Request and response bodies are JSON.
Timestamps are ISO 8601 strings (UTC, e.g. `"2026-07-01T12:34:56Z"`).

## Conventions

- `POST` creating a resource returns `201 Created` with the created resource.
- `PATCH` is partial update: every field optional; omitted fields are unchanged.
- `DELETE` returns `204 No Content` with an empty body.
- Unknown id in a path returns `404 Not Found`: `{"detail": "..."}`.
- Validation errors return `422 Unprocessable Entity` (FastAPI default shape).

---

## Data model

Field names/types match `backend/app/models.py` exactly.

### Project (singleton config row)
| field | type | notes |
|---|---|---|
| id | int | PK |
| name | string | required |
| description | string \| null | |

### SwimLane (kanban column)
| field | type | notes |
|---|---|---|
| id | int | PK |
| project_id | int | FK -> projects.id |
| name | string | required |
| position | int | ordering, ascending |
| is_done_column | bool | default false |

### Epic
| field | type | notes |
|---|---|---|
| id | int | PK |
| title | string | required |
| description | string \| null | |
| color | string \| null | hex, e.g. `#4f46e5` |
| created_at | datetime | set on create |

### Task
| field | type | notes |
|---|---|---|
| id | int | PK |
| epic_id | int \| null | FK -> epics.id, nullable |
| swimlane_id | int | FK -> swimlanes.id, required |
| title | string | required |
| description | string \| null | |
| position | int | ordering within swimlane, ascending |
| is_blocked | bool | default false |
| blocked_reason | string \| null | |
| created_at | datetime | set on create |
| updated_at | datetime | set on create, bumped on update |

### TaskDependency
| field | type | notes |
|---|---|---|
| id | int | PK |
| task_id | int | FK -> tasks.id |
| depends_on_task_id | int | FK -> tasks.id; must differ from task_id |

### TaskLink
| field | type | notes |
|---|---|---|
| id | int | PK |
| task_id | int | FK -> tasks.id |
| url | string | required |
| label | string \| null | |
| link_type | enum | `"pr"` \| `"slack"` \| `"other"` |

### Comment
| field | type | notes |
|---|---|---|
| id | int | PK |
| task_id | int | FK -> tasks.id |
| author | string | required |
| body | string | required |
| kind | enum | `"comment"` \| `"annotation"` |
| created_at | datetime | set on create |

---

## Project

### GET /api/project
Returns the singleton project config including its swimlanes ordered by `position` ascending.

Response `200`:
```json
{
  "id": 1,
  "name": "Trackeroo",
  "description": "A lightweight self-hosted task board.",
  "swimlanes": [
    {"id": 1, "project_id": 1, "name": "Backlog", "position": 0, "is_done_column": false},
    {"id": 5, "project_id": 1, "name": "Done", "position": 4, "is_done_column": true}
  ]
}
```

### PATCH /api/project
Update name and/or description.

Request:
```json
{"name": "My Board", "description": "optional new text"}
```
Both fields optional. Response `200`: the updated Project object (same shape as GET).

---

## SwimLanes

### POST /api/swimlanes
Create a new swimlane. `position` defaults to the end if omitted; server may assign.

Request:
```json
{"name": "QA", "position": 3, "is_done_column": false}
```
- `name`: string (required)
- `position`: int (optional)
- `is_done_column`: bool (optional, default false)

Response `201`:
```json
{"id": 6, "project_id": 1, "name": "QA", "position": 3, "is_done_column": false}
```

### PATCH /api/swimlanes/{id}
Request (all optional):
```json
{"name": "QA", "position": 2, "is_done_column": true}
```
Response `200`: updated SwimLane. `404` if not found.

### DELETE /api/swimlanes/{id}
Deletes the swimlane and cascades to its tasks.
Response `204`. `404` if not found.

### POST /api/swimlanes/reorder
Set the ordering of swimlanes. Body is the ordered list of ids; server assigns `position` by array index.

Request:
```json
{"ordered_ids": [3, 1, 2, 5, 4]}
```
Response `200`: the full list of swimlanes in new order.
```json
[
  {"id": 3, "project_id": 1, "name": "In Progress", "position": 0, "is_done_column": false}
]
```
`400` if `ordered_ids` does not match the existing swimlane id set.

---

## Epics

### GET /api/epics
Response `200`: array of Epic objects.
```json
[
  {"id": 1, "title": "Auth", "description": null, "color": "#4f46e5", "created_at": "2026-07-01T12:00:00Z"}
]
```

### POST /api/epics
Request:
```json
{"title": "Auth", "description": "optional", "color": "#4f46e5"}
```
- `title`: string (required)
- `description`: string (optional)
- `color`: string hex (optional)

Response `201`: created Epic.

### GET /api/epics/{id}
Response `200`: single Epic. `404` if not found.

### PATCH /api/epics/{id}
Request (all optional): `{"title": "...", "description": "...", "color": "#..."}`
Response `200`: updated Epic. `404` if not found.

### DELETE /api/epics/{id}
Deletes the epic. Tasks referencing it have `epic_id` set to null.
Response `204`. `404` if not found.

---

## Tasks

### GET /api/tasks
Query params (both optional, combinable):
- `epic_id`: int — filter to tasks in this epic
- `swimlane_id`: int — filter to tasks in this swimlane

Response `200`: array of Task summary objects (no nested comments/links/deps), ordered by `swimlane_id` then `position`.
```json
[
  {
    "id": 10, "epic_id": 1, "swimlane_id": 2, "title": "Login form",
    "description": null, "position": 0, "is_blocked": false, "blocked_reason": null,
    "created_at": "2026-07-01T12:00:00Z", "updated_at": "2026-07-01T12:00:00Z"
  }
]
```

### POST /api/tasks
Request:
```json
{
  "title": "Login form",
  "description": "optional",
  "epic_id": 1,
  "swimlane_id": 2,
  "position": 0
}
```
- `title`: string (required)
- `swimlane_id`: int (required)
- `epic_id`: int \| null (optional)
- `description`: string (optional)
- `position`: int (optional, default 0 / end of lane)

Response `201`: created Task summary object.

### GET /api/tasks/{id}
Full detail: task fields plus nested `comments`, `links`, and `dependencies`.

Response `200`:
```json
{
  "id": 10, "epic_id": 1, "swimlane_id": 2, "title": "Login form",
  "description": null, "position": 0, "is_blocked": false, "blocked_reason": null,
  "created_at": "2026-07-01T12:00:00Z", "updated_at": "2026-07-01T12:00:00Z",
  "comments": [
    {"id": 3, "task_id": 10, "author": "marcin", "body": "looks good", "kind": "comment", "created_at": "2026-07-01T13:00:00Z"}
  ],
  "links": [
    {"id": 2, "task_id": 10, "url": "https://github.com/x/y/pull/1", "label": "PR #1", "link_type": "pr"}
  ],
  "dependencies": [
    {"id": 4, "task_id": 10, "depends_on_task_id": 7},
    {"id": 5, "task_id": 10, "depends_on_task_id": 8}
  ]
}
```
`dependencies` is the full list of `TaskDependency` rows for this task (each with its own `id`, needed to call `DELETE /api/tasks/{id}/dependencies/{dependency_id}`) — not just the `depends_on_task_id` values.
`404` if not found.

### PATCH /api/tasks/{id}
Partial update. Any Task field editable except id/created_at/updated_at.
Request (all optional):
```json
{
  "title": "...", "description": "...", "epic_id": 2,
  "swimlane_id": 3, "position": 1,
  "is_blocked": true, "blocked_reason": "..."
}
```
Response `200`: updated Task summary object. `404` if not found.

### DELETE /api/tasks/{id}
Deletes the task and cascades to its comments, links, and dependency rows.
Response `204`. `404` if not found.

### POST /api/tasks/{id}/move
Move/reorder a task into a swimlane at a position. Shifts sibling positions as needed.

Request:
```json
{"swimlane_id": 5, "position": 0}
```
Response `200`: Task summary object plus a `warnings` array.
```json
{
  "id": 10, "epic_id": 1, "swimlane_id": 5, "title": "Login form",
  "description": null, "position": 0, "is_blocked": false, "blocked_reason": null,
  "created_at": "2026-07-01T12:00:00Z", "updated_at": "2026-07-01T14:00:00Z",
  "warnings": [
    "Task #7 'OAuth setup' is not in a done column",
    "Task #8 'DB schema' is not in a done column"
  ]
}
```
If the target swimlane is a done-column (`is_done_column = true`) and this task has
dependencies whose `depends_on_task_id` tasks are NOT in a done-column, the move still
succeeds (`200`) but `warnings` lists each open dependency. If there are no such deps,
`warnings` is `[]`. This is a soft warning — the move is never hard-blocked.
`404` if the task or target swimlane is not found.

### POST /api/tasks/{id}/block
Request:
```json
{"reason": "waiting on design"}
```
Sets `is_blocked = true` and `blocked_reason = reason`.
Response `200`: updated Task summary object. `404` if not found.

### POST /api/tasks/{id}/unblock
No body. Sets `is_blocked = false` and `blocked_reason = null`.
Response `200`: updated Task summary object. `404` if not found.

---

## Dependencies

### POST /api/tasks/{id}/dependencies
Add a dependency: task `{id}` depends on `depends_on_task_id`.

Request:
```json
{"depends_on_task_id": 7}
```
Response `201`:
```json
{"id": 4, "task_id": 10, "depends_on_task_id": 7}
```
- `400` if `depends_on_task_id == id` (self-dependency not allowed).
- `404` if either task does not exist.
- `409` if the dependency already exists (deduped — same `task_id`/`depends_on_task_id` pair).
- `422` if adding this dependency would create an immediate cycle (task `B` already depends on task `A`, and this request is `A` depends on `B`). Only the direct/immediate cycle is checked — full transitive-cycle detection is out of scope.

### DELETE /api/tasks/{id}/dependencies/{dependency_id}
`{dependency_id}` is the `TaskDependency.id`.
Response `204`. `404` if the dependency row is not found or does not belong to task `{id}`.

---

## Links

### POST /api/tasks/{id}/links
Request:
```json
{"url": "https://github.com/x/y/pull/1", "label": "PR #1", "link_type": "pr"}
```
- `url`: string (required)
- `label`: string (optional)
- `link_type`: `"pr"` \| `"slack"` \| `"other"` (optional, default `"other"`)

Response `201`:
```json
{"id": 2, "task_id": 10, "url": "https://github.com/x/y/pull/1", "label": "PR #1", "link_type": "pr"}
```
`404` if task not found.

### DELETE /api/tasks/{id}/links/{link_id}
Response `204`. `404` if the link is not found or does not belong to task `{id}`.

---

## Comments

### POST /api/tasks/{id}/comments
Request:
```json
{"author": "marcin", "body": "looks good", "kind": "comment"}
```
- `author`: string (required)
- `body`: string (required)
- `kind`: `"comment"` \| `"annotation"` (optional, default `"comment"`)

Response `201`:
```json
{"id": 3, "task_id": 10, "author": "marcin", "body": "looks good", "kind": "comment", "created_at": "2026-07-01T13:00:00Z"}
```
`404` if task not found.

### GET /api/tasks/{id}/comments
Response `200`: array of Comment objects ordered by `created_at` ascending.
`404` if task not found.

### DELETE /api/tasks/{id}/comments/{comment_id}
Response `204`. `404` if the comment is not found or does not belong to task `{id}`.

---

## Health

### GET /api/health
Response `200`: `{"status": "ok"}`
