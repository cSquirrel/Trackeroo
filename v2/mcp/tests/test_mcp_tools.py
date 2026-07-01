"""End-to-end MCP tool tests against the live Trackeroo Docker stack.

Every call goes through the MCP in-memory client session (see conftest), so the
assertions reflect what a real MCP client receives: tool results are text
payloads (the tools return JSON strings) and failures come back as errored tool
results carrying the backend's error detail.
"""

from __future__ import annotations

import json
from uuid import uuid4

DEFAULT_SWIMLANES = ["Backlog", "To Do", "In Progress", "Review", "Done"]


def _uniq(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _text(result) -> str:
    assert result.content, "tool result had no content"
    return result.content[0].text


def _ok_json(result):
    assert result.isError is False, f"expected success, got error: {_text(result)}"
    return json.loads(_text(result))


def _swimlane_id(mcp_call, name: str) -> int:
    project = _ok_json(mcp_call("get_project"))
    for lane in project["swimlanes"]:
        if lane["name"] == name:
            return lane["id"]
    raise AssertionError(f"swimlane {name!r} not found in {project['swimlanes']}")


def _make_task(mcp_call, swimlane_name: str = "Backlog") -> dict:
    return _ok_json(
        mcp_call(
            "create_task",
            {"title": _uniq("task"), "swimlane_id": _swimlane_id(mcp_call, swimlane_name)},
        )
    )


# --- Project ----------------------------------------------------------------


def test_get_project_seeds_five_swimlanes(mcp_call):
    project = _ok_json(mcp_call("get_project"))
    lanes = project["swimlanes"]
    assert [lane["name"] for lane in lanes] == DEFAULT_SWIMLANES
    done = next(lane for lane in lanes if lane["name"] == "Done")
    assert done["is_done_column"] is True
    assert all(
        lane["is_done_column"] is False for lane in lanes if lane["name"] != "Done"
    )


# --- Epics ------------------------------------------------------------------


def test_create_epic_then_list(mcp_call):
    title = _uniq("epic")
    created = _ok_json(
        mcp_call("create_epic", {"title": title, "description": "d", "color": "#4f46e5"})
    )
    assert created["title"] == title
    assert created["color"] == "#4f46e5"

    epics = _ok_json(mcp_call("list_epics"))
    match = next(e for e in epics if e["id"] == created["id"])
    assert match["title"] == title


# --- Tasks ------------------------------------------------------------------


def test_create_task_roundtrip_has_empty_nested_arrays(mcp_call):
    created = _make_task(mcp_call)
    detail = _ok_json(mcp_call("get_task", {"task_id": created["id"]}))
    assert detail["id"] == created["id"]
    assert detail["title"] == created["title"]
    assert detail["comments"] == []
    assert detail["links"] == []
    assert detail["dependencies"] == []
    assert detail["is_blocked"] is False


def test_update_task_reflected_in_get_task(mcp_call):
    task = _make_task(mcp_call)
    new_title = _uniq("renamed")
    _ok_json(
        mcp_call(
            "update_task",
            {"task_id": task["id"], "title": new_title, "description": "updated body"},
        )
    )
    detail = _ok_json(mcp_call("get_task", {"task_id": task["id"]}))
    assert detail["title"] == new_title
    assert detail["description"] == "updated body"


def test_add_comment_reflected_in_get_task(mcp_call):
    task = _make_task(mcp_call)
    _ok_json(
        mcp_call(
            "add_comment",
            {"task_id": task["id"], "author": "alice", "body": "looks good"},
        )
    )
    detail = _ok_json(mcp_call("get_task", {"task_id": task["id"]}))
    assert len(detail["comments"]) == 1
    assert detail["comments"][0]["author"] == "alice"
    assert detail["comments"][0]["body"] == "looks good"


def test_add_link_reflected_in_get_task(mcp_call):
    task = _make_task(mcp_call)
    url = "https://example.com/pr/1"
    _ok_json(
        mcp_call(
            "add_link",
            {"task_id": task["id"], "url": url, "label": "PR #1", "link_type": "pr"},
        )
    )
    detail = _ok_json(mcp_call("get_task", {"task_id": task["id"]}))
    assert len(detail["links"]) == 1
    assert detail["links"][0]["url"] == url
    assert detail["links"][0]["label"] == "PR #1"


def test_block_then_unblock_roundtrip(mcp_call):
    task = _make_task(mcp_call)

    _ok_json(mcp_call("block_task", {"task_id": task["id"], "reason": "waiting on infra"}))
    blocked = _ok_json(mcp_call("get_task", {"task_id": task["id"]}))
    assert blocked["is_blocked"] is True
    assert blocked["blocked_reason"] == "waiting on infra"

    _ok_json(mcp_call("unblock_task", {"task_id": task["id"]}))
    unblocked = _ok_json(mcp_call("get_task", {"task_id": task["id"]}))
    assert unblocked["is_blocked"] is False


# --- Dependencies + move warnings -------------------------------------------


def test_move_into_done_warns_on_open_dependency_then_clears(mcp_call):
    done_id = _swimlane_id(mcp_call, "Done")

    upstream = _make_task(mcp_call)  # stays in Backlog (not done)
    dependent = _make_task(mcp_call)

    dep = _ok_json(
        mcp_call(
            "add_dependency",
            {"task_id": dependent["id"], "depends_on_task_id": upstream["id"]},
        )
    )

    # Move the dependent task into Done while its dependency is still open.
    warned = mcp_call(
        "move_task", {"task_id": dependent["id"], "swimlane_id": done_id, "position": 0}
    )
    warned_text = _text(warned)
    assert warned.isError is False
    assert "Move succeeded with warnings" in warned_text
    assert str(upstream["id"]) in warned_text
    assert "not in a done column" in warned_text

    # Remove the dependency, then re-move: no warnings this time.
    _text(
        mcp_call(
            "remove_dependency",
            {"task_id": dependent["id"], "dependency_id": dep["id"]},
        )
    )
    cleared = mcp_call(
        "move_task", {"task_id": dependent["id"], "swimlane_id": done_id, "position": 0}
    )
    cleared_text = _text(cleared)
    assert cleared.isError is False
    # No warning banner is prepended, and the move result carries an empty list.
    assert "Move succeeded with warnings" not in cleared_text
    assert json.loads(cleared_text)["warnings"] == []


# --- Error path -------------------------------------------------------------


def test_create_task_with_bogus_swimlane_returns_clear_error(mcp_call):
    result = mcp_call(
        "create_task", {"title": _uniq("orphan"), "swimlane_id": 999999}
    )
    assert result.isError is True
    text = _text(result)
    assert "404" in text
    assert "SwimLane not found" in text
    assert "Traceback" not in text
