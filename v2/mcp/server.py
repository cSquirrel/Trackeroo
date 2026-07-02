"""MCP server exposing Trackeroo task-board CRUD as tools over the REST API.

Thin client of the REST API documented in ../docs/api-contract.md. The backend
binds to a fresh, unpredictable port every time a project is opened (that's
what lets multiple projects run at once), so a hardcoded URL goes stale the
moment the app restarts. Point this at the project folder instead via
TRACKEROO_PROJECT_PATH, and it discovers the live port by reading
"<project>/.trackeroo/.env" (a KEY=VALUE file written by the app on every
backend spawn, currently just TRACKEROO_PORT) before each request.
TRACKEROO_API_URL remains supported as a direct override for cases where a
known, fixed backend URL is genuinely correct (e.g. manual testing against a
backend you started yourself).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

_EXPLICIT_API_URL = os.environ.get("TRACKEROO_API_URL")
_PROJECT_PATH = os.environ.get("TRACKEROO_PROJECT_PATH")
_DEFAULT_API_URL = "http://localhost:8000"

mcp = FastMCP("trackeroo")

_client = httpx.Client(timeout=30.0)


def _parse_env_file(text: str) -> dict[str, str]:
    """Minimal KEY=VALUE parser — one entry per non-blank, non-comment line."""
    env: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def _resolve_base_url() -> str:
    """The API base URL for the next request.

    Re-reads the .env file each call (when configured by project path) so a
    restarted app that picked a different port is picked up automatically,
    without needing to touch the MCP client config.
    """
    if _EXPLICIT_API_URL:
        return _EXPLICIT_API_URL.rstrip("/")
    if _PROJECT_PATH:
        env_file = Path(_PROJECT_PATH) / ".trackeroo" / ".env"
        try:
            env = _parse_env_file(env_file.read_text())
        except FileNotFoundError:
            raise RuntimeError(
                f"No running Trackeroo backend found for project "
                f"'{_PROJECT_PATH}' (missing {env_file}). Open this project "
                f"in the Trackeroo app first."
            ) from None
        port = env.get("TRACKEROO_PORT")
        if not port:
            raise RuntimeError(
                f"{env_file} exists but has no TRACKEROO_PORT entry."
            )
        return f"http://localhost:{port}"
    return _DEFAULT_API_URL


def _request(method: str, path: str, **kwargs: Any) -> Any:
    """Call the REST API and return parsed JSON, raising a clear error on non-2xx."""
    base_url = _resolve_base_url()
    try:
        resp = _client.request(method, f"{base_url}{path}", **kwargs)
    except httpx.RequestError as exc:
        raise RuntimeError(
            f"Could not reach Trackeroo API at {base_url} ({method} {path}): {exc}"
        ) from exc

    if resp.is_success:
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    # Surface the response body so the calling AI gets actionable feedback.
    body = resp.text
    try:
        detail = resp.json()
        body = detail.get("detail", detail) if isinstance(detail, dict) else detail
    except Exception:
        pass
    raise RuntimeError(
        f"Trackeroo API {method} {path} failed: {resp.status_code} {resp.reason_phrase} - {body}"
    )


def _dump(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


# --- Project ---------------------------------------------------------------


@mcp.tool()
def get_project() -> str:
    """Get the project config including its swimlanes (ordered by position).

    Call this first to discover valid swimlane ids/names before creating or
    moving tasks.
    """
    return _dump(_request("GET", "/api/project"))


# --- Swimlanes ---------------------------------------------------------------


@mcp.tool()
def create_swimlane(name: str, position: int = 0, is_done_column: bool = False) -> str:
    """Create a swimlane (kanban column). `position` controls left-to-right order
    (0 = leftmost); `is_done_column` marks it as a "done" lane for dependency-
    warning purposes (see move_task).
    """
    payload = {"name": name, "position": position, "is_done_column": is_done_column}
    return _dump(_request("POST", "/api/swimlanes", json=payload))


@mcp.tool()
def update_swimlane(
    swimlane_id: int,
    name: str | None = None,
    position: int | None = None,
    is_done_column: bool | None = None,
) -> str:
    """Partially update a swimlane. Only provided fields are changed."""
    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if position is not None:
        payload["position"] = position
    if is_done_column is not None:
        payload["is_done_column"] = is_done_column
    return _dump(_request("PATCH", f"/api/swimlanes/{swimlane_id}", json=payload))


@mcp.tool()
def delete_swimlane(swimlane_id: int) -> str:
    """Delete a swimlane. Fails if it's the last remaining one (at least one
    swimlane must always exist) — the backend's error message explains this.
    """
    _request("DELETE", f"/api/swimlanes/{swimlane_id}")
    return f"Deleted swimlane {swimlane_id}."


@mcp.tool()
def reorder_swimlanes(ordered_ids: list[int]) -> str:
    """Reorder all swimlanes at once. `ordered_ids` must contain every existing
    swimlane id exactly once, in the desired left-to-right order — call
    get_project first to see current ids. Returns the reordered list.
    """
    return _dump(_request("POST", "/api/swimlanes/reorder", json={"ordered_ids": ordered_ids}))


# --- Epics -----------------------------------------------------------------


@mcp.tool()
def list_epics() -> str:
    """List all epics."""
    return _dump(_request("GET", "/api/epics"))


@mcp.tool()
def create_epic(
    title: str,
    description: str = "",
    color: str = "#888888",
    priority: str | None = None,
) -> str:
    """Create an epic. `color` is a hex string like #4f46e5.

    `priority` is one of "low", "medium", "high", "urgent" (optional).
    """
    payload: dict[str, Any] = {"title": title, "description": description, "color": color}
    if priority is not None:
        payload["priority"] = priority
    return _dump(_request("POST", "/api/epics", json=payload))


@mcp.tool()
def update_epic(
    epic_id: int,
    title: str | None = None,
    description: str | None = None,
    color: str | None = None,
    priority: str | None = None,
) -> str:
    """Partially update an epic. Only provided fields are changed.

    `priority` is one of "low", "medium", "high", "urgent".
    """
    payload: dict[str, Any] = {}
    if title is not None:
        payload["title"] = title
    if description is not None:
        payload["description"] = description
    if color is not None:
        payload["color"] = color
    if priority is not None:
        payload["priority"] = priority
    return _dump(_request("PATCH", f"/api/epics/{epic_id}", json=payload))


@mcp.tool()
def epic_status(epic_id: int) -> str:
    """Roll up an epic's progress: task counts by swimlane, done count/percent, blocked count.

    Composes get_epic + get_project (for swimlane names) + list_tasks(epic_id) —
    there's no stored progress field, this is computed from current task positions.
    """
    epic = _request("GET", f"/api/epics/{epic_id}")
    swimlanes = _request("GET", "/api/project")["swimlanes"]
    tasks = _request("GET", "/api/tasks", params={"epic_id": epic_id})

    lane_by_id = {lane["id"]: lane for lane in swimlanes}
    by_swimlane: dict[str, int] = {}
    done = 0
    blocked = 0
    for task in tasks:
        lane = lane_by_id.get(task["swimlane_id"])
        name = lane["name"] if lane else f"swimlane {task['swimlane_id']}"
        by_swimlane[name] = by_swimlane.get(name, 0) + 1
        if lane and lane.get("is_done_column"):
            done += 1
        if task.get("is_blocked"):
            blocked += 1

    total = len(tasks)
    return _dump(
        {
            "epic": {"id": epic["id"], "title": epic["title"], "priority": epic.get("priority")},
            "total_tasks": total,
            "done": done,
            "percent_done": round(100 * done / total) if total else 0,
            "blocked": blocked,
            "by_swimlane": by_swimlane,
        }
    )


# --- Tasks -----------------------------------------------------------------


@mcp.tool()
def list_tasks(
    epic_id: int | None = None,
    swimlane_id: int | None = None,
    priority: str | None = None,
    sort_by_priority: bool = False,
) -> str:
    """List task summaries, optionally filtered by epic, swimlane, and/or priority.

    `priority` filters to an exact level ("low", "medium", "high", "urgent").
    Set `sort_by_priority=True` to order results highest-priority-first — use
    this plus `swimlane_id` to answer things like "highest priority tickets in
    review" (call get_project first to find the "Review" swimlane's id).
    """
    params: dict[str, Any] = {}
    if epic_id is not None:
        params["epic_id"] = epic_id
    if swimlane_id is not None:
        params["swimlane_id"] = swimlane_id
    if priority is not None:
        params["priority"] = priority
    if sort_by_priority:
        params["sort"] = "priority"
    return _dump(_request("GET", "/api/tasks", params=params))


@mcp.tool()
def search_tasks(query: str) -> str:
    """Full-text search over task title and description (case-insensitive substring match).

    Use this to answer things like "do we have a ticket covering authentication?".
    """
    return _dump(_request("GET", "/api/tasks", params={"q": query}))


@mcp.tool()
def get_task(task_id: int) -> str:
    """Get full task detail: fields plus comments, links, and dependencies."""
    return _dump(_request("GET", f"/api/tasks/{task_id}"))


@mcp.tool()
def create_task(
    title: str,
    description: str = "",
    type: str | None = None,
    priority: str | None = None,
    epic_id: int | None = None,
    swimlane_id: int | None = None,
) -> str:
    """Create a task.

    `swimlane_id` is required by the API; call get_project first to find valid
    swimlane ids. `epic_id` is optional. `type` is a free-text ticket type
    ("chore", "fix", "feature", or anything else) — not a fixed enum.
    `priority` is one of "low", "medium", "high", "urgent" (optional).
    """
    payload: dict[str, Any] = {"title": title, "description": description}
    if type is not None:
        payload["type"] = type
    if priority is not None:
        payload["priority"] = priority
    if epic_id is not None:
        payload["epic_id"] = epic_id
    if swimlane_id is not None:
        payload["swimlane_id"] = swimlane_id
    return _dump(_request("POST", "/api/tasks", json=payload))


@mcp.tool()
def update_task(
    task_id: int,
    title: str | None = None,
    description: str | None = None,
    type: str | None = None,
    priority: str | None = None,
) -> str:
    """Partially update a task's title, description, type, and/or priority.

    `priority` is one of "low", "medium", "high", "urgent".
    """
    payload: dict[str, Any] = {}
    if title is not None:
        payload["title"] = title
    if description is not None:
        payload["description"] = description
    if type is not None:
        payload["type"] = type
    if priority is not None:
        payload["priority"] = priority
    return _dump(_request("PATCH", f"/api/tasks/{task_id}", json=payload))


@mcp.tool()
def move_task(task_id: int, swimlane_id: int, position: int) -> str:
    """Move/reorder a task into a swimlane at a position.

    Moving into a done-column while the task has unfinished dependencies is a
    soft warning, never blocked; any warnings are surfaced in the result.
    """
    payload = {"swimlane_id": swimlane_id, "position": position}
    result = _request("POST", f"/api/tasks/{task_id}/move", json=payload)
    warnings = result.get("warnings") or [] if isinstance(result, dict) else []
    out = _dump(result)
    if warnings:
        joined = "\n".join(f"- {w}" for w in warnings)
        out = f"Move succeeded with warnings:\n{joined}\n\n{out}"
    return out


@mcp.tool()
def block_task(task_id: int, reason: str) -> str:
    """Mark a task as blocked with a reason."""
    return _dump(_request("POST", f"/api/tasks/{task_id}/block", json={"reason": reason}))


@mcp.tool()
def unblock_task(task_id: int) -> str:
    """Clear a task's blocked state."""
    return _dump(_request("POST", f"/api/tasks/{task_id}/unblock"))


# --- Comments --------------------------------------------------------------


@mcp.tool()
def add_comment(task_id: int, author: str, body: str, kind: str = "comment") -> str:
    """Add a comment to a task. `kind` is "comment" or "annotation"."""
    payload = {"author": author, "body": body, "kind": kind}
    return _dump(_request("POST", f"/api/tasks/{task_id}/comments", json=payload))


# --- Dependencies ----------------------------------------------------------


@mcp.tool()
def add_dependency(task_id: int, depends_on_task_id: int) -> str:
    """Make `task_id` depend on `depends_on_task_id`."""
    payload = {"depends_on_task_id": depends_on_task_id}
    return _dump(_request("POST", f"/api/tasks/{task_id}/dependencies", json=payload))


@mcp.tool()
def remove_dependency(task_id: int, dependency_id: int) -> str:
    """Remove a dependency row (`dependency_id` is the TaskDependency id) from a task."""
    _request("DELETE", f"/api/tasks/{task_id}/dependencies/{dependency_id}")
    return f"Removed dependency {dependency_id} from task {task_id}."


# --- Links -----------------------------------------------------------------


@mcp.tool()
def add_link(task_id: int, url: str, label: str, link_type: str) -> str:
    """Attach a link to a task. `link_type` is "pr", "slack", or "other"."""
    payload = {"url": url, "label": label, "link_type": link_type}
    return _dump(_request("POST", f"/api/tasks/{task_id}/links", json=payload))


if __name__ == "__main__":
    mcp.run()
