"""End-to-end MCP tool tests against the live Trackeroo Docker stack.

Every call goes through the MCP in-memory client session (see conftest), so the
assertions reflect what a real MCP client receives: tool results are compact
markdown text (`key: value` lines, tables for lists, multi-line text as
trailing blocks — see server._fmt) and failures come back as errored tool
results carrying the backend's error detail.
"""

from __future__ import annotations

from uuid import uuid4

DEFAULT_SWIMLANES = ["Backlog", "To Do", "In Progress", "Review", "Done"]


def _uniq(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _text(result) -> str:
    assert result.content, "tool result had no content"
    return result.content[0].text


def _coerce(value: str):
    if value.isdigit():
        return int(value)
    if value in ("True", "False"):
        return value == "True"
    return value


def _ok_text(result) -> str:
    assert result.isError is False, f"expected success, got error: {_text(result)}"
    return _text(result)


def _kv(text: str) -> dict:
    """Parse the leading `key: value` scalar lines of a _fmt payload (they end
    at the first blank line; multi-line blocks and tables follow after)."""
    out: dict = {}
    for line in text.splitlines():
        if not line.strip():
            break
        key, sep, value = line.partition(": ")
        if sep:
            out[key] = _coerce(value)
    return out


def _ok_kv(result) -> dict:
    return _kv(_ok_text(result))


def _parse_table(lines: list[str]) -> list[dict]:
    header = [c.strip() for c in lines[0].strip("|").split("|")]
    rows = []
    for line in lines[2:]:
        cells = [_coerce(c.strip()) for c in line.strip("|").split("|")]
        rows.append(dict(zip(header, cells)))
    return rows


def _ok_table(result) -> list[dict]:
    """Parse a top-level markdown-table result (list_tasks, list_epics, ...)."""
    lines = [line for line in _ok_text(result).splitlines() if line.strip()]
    return _parse_table(lines)


def _section_rows(text: str, name: str) -> list[dict]:
    """Parse the table under a `<name> (N):` section of a _fmt payload.
    Returns [] if the section is absent (empty lists are omitted entirely)."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(f"{name} ("):
            table = []
            for row_line in lines[i + 1 :]:
                if not row_line.startswith("|"):
                    break
                table.append(row_line)
            return _parse_table(table)
    return []


def _swimlane_id(mcp_call, name: str) -> int:
    lanes = _section_rows(_ok_text(mcp_call("get_project")), "swimlanes")
    for lane in lanes:
        if lane["name"] == name:
            return lane["id"]
    raise AssertionError(f"swimlane {name!r} not found in {lanes}")


def _make_task(mcp_call, swimlane_name: str = "Backlog") -> dict:
    return _ok_kv(
        mcp_call(
            "create_task",
            {"title": _uniq("task"), "swimlane_id": _swimlane_id(mcp_call, swimlane_name)},
        )
    )


# --- Project ----------------------------------------------------------------


def test_get_project_seeds_five_swimlanes(mcp_call):
    lanes = _section_rows(_ok_text(mcp_call("get_project")), "swimlanes")
    assert [lane["name"] for lane in lanes] == DEFAULT_SWIMLANES
    done = next(lane for lane in lanes if lane["name"] == "Done")
    assert done["is_done_column"] is True
    assert all(
        lane["is_done_column"] is False for lane in lanes if lane["name"] != "Done"
    )


# --- Swimlanes ---------------------------------------------------------------


def test_create_swimlane_then_visible_in_project(mcp_call):
    name = _uniq("lane")
    created = _ok_kv(mcp_call("create_swimlane", {"name": name, "position": 99}))
    assert created["name"] == name
    assert created["is_done_column"] is False

    lanes = _section_rows(_ok_text(mcp_call("get_project")), "swimlanes")
    assert any(lane["id"] == created["id"] and lane["name"] == name for lane in lanes)


def test_update_swimlane_reflected_in_project(mcp_call):
    created = _ok_kv(mcp_call("create_swimlane", {"name": _uniq("lane")}))
    new_name = _uniq("renamed")
    updated = _ok_kv(
        mcp_call(
            "update_swimlane",
            {"swimlane_id": created["id"], "name": new_name, "is_done_column": True},
        )
    )
    assert updated["name"] == new_name
    assert updated["is_done_column"] is True

    lanes = _section_rows(_ok_text(mcp_call("get_project")), "swimlanes")
    match = next(lane for lane in lanes if lane["id"] == created["id"])
    assert match["name"] == new_name
    assert match["is_done_column"] is True


def test_delete_swimlane_removes_it(mcp_call):
    created = _ok_kv(mcp_call("create_swimlane", {"name": _uniq("lane")}))
    lanes = _section_rows(_ok_text(mcp_call("get_project")), "swimlanes")
    assert any(lane["id"] == created["id"] for lane in lanes)

    result = mcp_call("delete_swimlane", {"swimlane_id": created["id"]})
    assert result.isError is False

    lanes_after = _section_rows(_ok_text(mcp_call("get_project")), "swimlanes")
    assert not any(lane["id"] == created["id"] for lane in lanes_after)

    # Rejection of deleting the *last* remaining swimlane isn't testable here:
    # this suite runs against a shared, session-scoped stack (many tests rely
    # on the default 5 seeded lanes still existing), so driving the global
    # count down to 1 would corrupt every other test. Covered instead by
    # manual verification against an isolated project copy.


def test_reorder_swimlanes_changes_project_order(mcp_call):
    lanes = _section_rows(_ok_text(mcp_call("get_project")), "swimlanes")
    original_ids = [lane["id"] for lane in lanes]
    assert len(original_ids) >= 2, "need at least 2 swimlanes to test reordering"

    reversed_ids = list(reversed(original_ids))
    reordered = _ok_table(mcp_call("reorder_swimlanes", {"ordered_ids": reversed_ids}))
    assert [lane["id"] for lane in reordered] == reversed_ids

    # Restore original order — this suite's stack is shared/session-scoped, and
    # other tests (e.g. test_get_project_seeds_five_swimlanes) assert exact
    # default ordering.
    restored = _ok_table(mcp_call("reorder_swimlanes", {"ordered_ids": original_ids}))
    assert [lane["id"] for lane in restored] == original_ids


# --- Epics ------------------------------------------------------------------


def test_create_epic_then_list(mcp_call):
    title = _uniq("epic")
    created = _ok_kv(
        mcp_call("create_epic", {"title": title, "description": "d", "color": "#4f46e5"})
    )
    assert created["title"] == title
    assert created["color"] == "#4f46e5"

    epics = _ok_table(mcp_call("list_epics"))
    match = next(e for e in epics if e["id"] == created["id"])
    assert match["title"] == title


def test_epic_status_rolls_up_task_counts_by_swimlane(mcp_call):
    epic = _ok_kv(mcp_call("create_epic", {"title": _uniq("epic"), "priority": "high"}))
    backlog_id = _swimlane_id(mcp_call, "Backlog")
    done_id = _swimlane_id(mcp_call, "Done")

    t1 = _ok_kv(
        mcp_call("create_task", {"title": _uniq("t"), "swimlane_id": backlog_id, "epic_id": epic["id"]})
    )
    _ok_kv(
        mcp_call("create_task", {"title": _uniq("t"), "swimlane_id": backlog_id, "epic_id": epic["id"]})
    )
    _ok_text(mcp_call("move_task", {"task_id": t1["id"], "swimlane_id": done_id, "position": 0}))

    status_text = _ok_text(mcp_call("epic_status", {"epic_id": epic["id"]}))
    status = _kv(status_text)
    # epic and by_swimlane render as inline k=v lines, not nested objects
    assert epic["title"] in str(status["epic"])
    assert "priority=high" in str(status["epic"])
    assert status["total_tasks"] == 2
    assert status["done"] == 1
    assert status["percent_done"] == 50
    assert "Backlog=1" in str(status["by_swimlane"])
    assert "Done=1" in str(status["by_swimlane"])


# --- Tasks ------------------------------------------------------------------


def test_create_task_roundtrip_omits_empty_nested_sections(mcp_call):
    created = _make_task(mcp_call)
    detail_text = _ok_text(mcp_call("get_task", {"task_id": created["id"]}))
    detail = _kv(detail_text)
    assert detail["id"] == created["id"]
    assert detail["title"] == created["title"]
    assert detail["is_blocked"] is False
    # Empty comments/links/dependencies are omitted entirely (absent = none).
    for section in ("comments (", "links (", "dependencies ("):
        assert section not in detail_text


def test_search_tasks_matches_title_and_description(mcp_call):
    needle = _uniq("needle")
    swimlane_id = _swimlane_id(mcp_call, "Backlog")
    _ok_kv(mcp_call("create_task", {"title": needle, "swimlane_id": swimlane_id}))
    _ok_kv(
        mcp_call(
            "create_task",
            {"title": _uniq("other"), "description": needle, "swimlane_id": swimlane_id},
        )
    )

    found = _ok_table(mcp_call("search_tasks", {"query": needle}))
    assert len(found) == 2

    assert _ok_table(mcp_call("search_tasks", {"query": _uniq("no-match")})) == []


def test_list_tasks_priority_filter_and_sort(mcp_call):
    swimlane_id = _swimlane_id(mcp_call, "Review")
    low = _ok_kv(
        mcp_call("create_task", {"title": _uniq("low"), "swimlane_id": swimlane_id, "priority": "low"})
    )
    urgent = _ok_kv(
        mcp_call(
            "create_task",
            {"title": _uniq("urgent"), "swimlane_id": swimlane_id, "priority": "urgent"},
        )
    )

    only_urgent = _ok_table(mcp_call("list_tasks", {"swimlane_id": swimlane_id, "priority": "urgent"}))
    assert {t["id"] for t in only_urgent} == {urgent["id"]}

    sorted_tasks = _ok_table(
        mcp_call("list_tasks", {"swimlane_id": swimlane_id, "sort_by_priority": True})
    )
    ids_in_order = [t["id"] for t in sorted_tasks if t["id"] in {low["id"], urgent["id"]}]
    assert ids_in_order == [urgent["id"], low["id"]]


def test_list_tasks_default_columns_are_lean(mcp_call):
    _make_task(mcp_call)
    header = _text(mcp_call("list_tasks")).splitlines()[0]
    for col in ("created_at", "updated_at", "position", "blocked_reason"):
        assert col not in header
    for col in ("id", "title", "description", "type", "priority", "epic_id", "swimlane_id", "is_blocked"):
        assert col in header


def test_list_tasks_fields_selects_columns(mcp_call):
    swimlane_id = _swimlane_id(mcp_call, "Backlog")
    _make_task(mcp_call, "Backlog")
    raw = _text(mcp_call("list_tasks", {"swimlane_id": swimlane_id, "fields": ["id", "title", "priority"]}))
    assert raw.splitlines()[0] == "| id | title | priority |"


def test_list_tasks_unknown_field_returns_clear_error(mcp_call):
    result = mcp_call("list_tasks", {"fields": ["bogus_field"]})
    assert result.isError is True
    assert "bogus_field" in _text(result)


def test_list_tasks_table_escapes_pipe_in_title(mcp_call):
    swimlane_id = _swimlane_id(mcp_call, "Backlog")
    title = _uniq("weird") + " | pipe"
    _ok_kv(mcp_call("create_task", {"title": title, "swimlane_id": swimlane_id}))
    raw = _text(mcp_call("list_tasks", {"swimlane_id": swimlane_id, "fields": ["id", "title"]}))
    assert title.replace("|", "\\|") in raw


def test_get_task_omits_null_fields(mcp_call):
    task = _make_task(mcp_call)
    raw = _ok_text(mcp_call("get_task", {"task_id": task["id"]}))
    detail = _kv(raw)
    assert detail["id"] == task["id"]
    for absent_key in ("epic_id", "blocked_reason", "type", "priority"):
        assert absent_key not in detail


def test_update_task_reflected_in_get_task(mcp_call):
    task = _make_task(mcp_call)
    new_title = _uniq("renamed")
    _ok_text(
        mcp_call(
            "update_task",
            {"task_id": task["id"], "title": new_title, "description": "updated body"},
        )
    )
    detail = _ok_kv(mcp_call("get_task", {"task_id": task["id"]}))
    assert detail["title"] == new_title
    assert detail["description"] == "updated body"


def test_add_comment_reflected_in_get_task(mcp_call):
    task = _make_task(mcp_call)
    _ok_text(
        mcp_call(
            "add_comment",
            {"task_id": task["id"], "author": "alice", "body": "looks good"},
        )
    )
    comments = _section_rows(_ok_text(mcp_call("get_task", {"task_id": task["id"]})), "comments")
    assert len(comments) == 1
    assert comments[0]["author"] == "alice"
    assert comments[0]["body"] == "looks good"


def test_add_link_reflected_in_get_task(mcp_call):
    task = _make_task(mcp_call)
    url = "https://example.com/pr/1"
    _ok_text(
        mcp_call(
            "add_link",
            {"task_id": task["id"], "url": url, "label": "PR #1", "link_type": "pr"},
        )
    )
    links = _section_rows(_ok_text(mcp_call("get_task", {"task_id": task["id"]})), "links")
    assert len(links) == 1
    assert links[0]["url"] == url
    assert links[0]["label"] == "PR #1"


def test_block_then_unblock_roundtrip(mcp_call):
    task = _make_task(mcp_call)

    _ok_text(mcp_call("block_task", {"task_id": task["id"], "reason": "waiting on infra"}))
    blocked = _ok_kv(mcp_call("get_task", {"task_id": task["id"]}))
    assert blocked["is_blocked"] is True
    assert blocked["blocked_reason"] == "waiting on infra"

    _ok_text(mcp_call("unblock_task", {"task_id": task["id"]}))
    unblocked = _ok_kv(mcp_call("get_task", {"task_id": task["id"]}))
    assert unblocked["is_blocked"] is False


# --- Dependencies + move warnings -------------------------------------------


def test_move_into_done_warns_on_open_dependency_then_clears(mcp_call):
    done_id = _swimlane_id(mcp_call, "Done")

    upstream = _make_task(mcp_call)  # stays in Backlog (not done)
    dependent = _make_task(mcp_call)

    dep = _ok_kv(
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
    # No warning banner, and the empty warnings list is omitted entirely.
    assert "Move succeeded with warnings" not in cleared_text
    assert "warnings" not in cleared_text


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
