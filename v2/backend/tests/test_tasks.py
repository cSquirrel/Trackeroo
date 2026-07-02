from __future__ import annotations

from conftest import make_task


def test_task_crud_and_detail(client, todo_lane):
    lane_id = todo_lane["id"]
    task = make_task(client, lane_id, title="Login form")
    assert task["is_blocked"] is False

    detail = client.get(f"/api/tasks/{task['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["comments"] == []
    assert body["links"] == []
    assert body["dependencies"] == []

    patched = client.patch(f"/api/tasks/{task['id']}", json={"title": "Login v2"})
    assert patched.status_code == 200
    assert patched.json()["title"] == "Login v2"

    assert client.delete(f"/api/tasks/{task['id']}").status_code == 204
    assert client.get(f"/api/tasks/{task['id']}").status_code == 404


def test_task_type_is_open_and_optional(client, todo_lane):
    lane_id = todo_lane["id"]

    untyped = make_task(client, lane_id, title="No type set")
    assert untyped["type"] is None

    chore = make_task(client, lane_id, title="Tidy up", type="chore")
    assert chore["type"] == "chore"

    # Deliberately not an enum: any string is accepted, including one not in
    # the usual chore/fix/feature suggestions.
    custom = make_task(client, lane_id, title="Something else", type="spike")
    assert custom["type"] == "spike"

    patched = client.patch(f"/api/tasks/{untyped['id']}", json={"type": "fix"})
    assert patched.status_code == 200
    assert patched.json()["type"] == "fix"

    cleared = client.patch(f"/api/tasks/{untyped['id']}", json={"type": None})
    assert cleared.status_code == 200
    assert cleared.json()["type"] is None


def test_task_missing_404(client):
    assert client.get("/api/tasks/999").status_code == 404


def test_task_create_bad_swimlane_404(client):
    resp = client.post("/api/tasks", json={"title": "T", "swimlane_id": 999})
    assert resp.status_code == 404


def test_list_tasks_filters(client, swimlanes):
    lane_a, lane_b = swimlanes[0]["id"], swimlanes[1]["id"]
    epic = client.post("/api/epics", json={"title": "E"}).json()
    make_task(client, lane_a, epic_id=epic["id"])
    make_task(client, lane_b)

    by_lane = client.get("/api/tasks", params={"swimlane_id": lane_a}).json()
    assert len(by_lane) == 1 and by_lane[0]["swimlane_id"] == lane_a

    by_epic = client.get("/api/tasks", params={"epic_id": epic["id"]}).json()
    assert len(by_epic) == 1 and by_epic[0]["epic_id"] == epic["id"]

    assert len(client.get("/api/tasks").json()) == 2


def test_block_unblock(client, todo_lane):
    task = make_task(client, todo_lane["id"])
    blocked = client.post(
        f"/api/tasks/{task['id']}/block", json={"reason": "waiting on design"}
    )
    assert blocked.status_code == 200
    assert blocked.json()["is_blocked"] is True
    assert blocked.json()["blocked_reason"] == "waiting on design"

    unblocked = client.post(f"/api/tasks/{task['id']}/unblock")
    assert unblocked.status_code == 200
    assert unblocked.json()["is_blocked"] is False
    assert unblocked.json()["blocked_reason"] is None


def test_move_reorders_positions(client, todo_lane, done_lane):
    lane = todo_lane["id"]
    t0 = make_task(client, lane, title="a")
    t1 = make_task(client, lane, title="b")
    t2 = make_task(client, lane, title="c")

    # move t2 to the done lane at position 0, no deps -> no warnings
    resp = client.post(
        f"/api/tasks/{t2['id']}/move",
        json={"swimlane_id": done_lane["id"], "position": 0},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["swimlane_id"] == done_lane["id"]
    assert body["position"] == 0
    assert body["warnings"] == []

    # source lane compacted to 0,1
    remaining = client.get("/api/tasks", params={"swimlane_id": lane}).json()
    assert [t["position"] for t in remaining] == [0, 1]
    assert {t["id"] for t in remaining} == {t0["id"], t1["id"]}


def test_move_into_done_with_open_dependency_warns(client, todo_lane, done_lane):
    dep = make_task(client, todo_lane["id"], title="OAuth setup")
    task = make_task(client, todo_lane["id"], title="Login")
    client.post(
        f"/api/tasks/{task['id']}/dependencies",
        json={"depends_on_task_id": dep["id"]},
    )
    resp = client.post(
        f"/api/tasks/{task['id']}/move",
        json={"swimlane_id": done_lane["id"], "position": 0},
    )
    assert resp.status_code == 200
    warnings = resp.json()["warnings"]
    assert len(warnings) == 1
    assert f"#{dep['id']}" in warnings[0]
    assert "OAuth setup" in warnings[0]


def test_move_into_done_with_satisfied_dependency_no_warn(
    client, todo_lane, done_lane
):
    dep = make_task(client, todo_lane["id"], title="Done dep")
    client.post(
        f"/api/tasks/{dep['id']}/move",
        json={"swimlane_id": done_lane["id"], "position": 0},
    )
    task = make_task(client, todo_lane["id"], title="Login")
    client.post(
        f"/api/tasks/{task['id']}/dependencies",
        json={"depends_on_task_id": dep["id"]},
    )
    resp = client.post(
        f"/api/tasks/{task['id']}/move",
        json={"swimlane_id": done_lane["id"], "position": 0},
    )
    assert resp.status_code == 200
    assert resp.json()["warnings"] == []


def test_move_missing_swimlane_404(client, todo_lane):
    task = make_task(client, todo_lane["id"])
    resp = client.post(
        f"/api/tasks/{task['id']}/move", json={"swimlane_id": 999, "position": 0}
    )
    assert resp.status_code == 404


def test_dependency_lifecycle_and_detail(client, todo_lane):
    a = make_task(client, todo_lane["id"], title="a")
    b = make_task(client, todo_lane["id"], title="b")
    resp = client.post(
        f"/api/tasks/{a['id']}/dependencies", json={"depends_on_task_id": b["id"]}
    )
    assert resp.status_code == 201
    dep_row = resp.json()
    assert dep_row["task_id"] == a["id"]
    assert dep_row["depends_on_task_id"] == b["id"]

    detail = client.get(f"/api/tasks/{a['id']}").json()
    assert detail["dependencies"] == [dep_row]

    removed = client.delete(f"/api/tasks/{a['id']}/dependencies/{dep_row['id']}")
    assert removed.status_code == 204
    assert client.get(f"/api/tasks/{a['id']}").json()["dependencies"] == []


def test_self_dependency_rejected(client, todo_lane):
    a = make_task(client, todo_lane["id"])
    resp = client.post(
        f"/api/tasks/{a['id']}/dependencies", json={"depends_on_task_id": a["id"]}
    )
    assert resp.status_code == 400


def test_immediate_cycle_rejected(client, todo_lane):
    a = make_task(client, todo_lane["id"], title="a")
    b = make_task(client, todo_lane["id"], title="b")
    assert client.post(
        f"/api/tasks/{a['id']}/dependencies", json={"depends_on_task_id": b["id"]}
    ).status_code == 201
    # b depends on a would be an immediate cycle
    resp = client.post(
        f"/api/tasks/{b['id']}/dependencies", json={"depends_on_task_id": a["id"]}
    )
    assert resp.status_code == 422


def test_duplicate_dependency_conflict(client, todo_lane):
    a = make_task(client, todo_lane["id"], title="a")
    b = make_task(client, todo_lane["id"], title="b")
    payload = {"depends_on_task_id": b["id"]}
    assert client.post(f"/api/tasks/{a['id']}/dependencies", json=payload).status_code == 201
    assert client.post(f"/api/tasks/{a['id']}/dependencies", json=payload).status_code == 409


def test_dependency_missing_target_404(client, todo_lane):
    a = make_task(client, todo_lane["id"])
    resp = client.post(
        f"/api/tasks/{a['id']}/dependencies", json={"depends_on_task_id": 999}
    )
    assert resp.status_code == 404


def test_link_lifecycle(client, todo_lane):
    task = make_task(client, todo_lane["id"])
    resp = client.post(
        f"/api/tasks/{task['id']}/links",
        json={"url": "https://github.com/x/y/pull/1", "label": "PR #1", "link_type": "pr"},
    )
    assert resp.status_code == 201
    link = resp.json()
    assert link["link_type"] == "pr"

    detail = client.get(f"/api/tasks/{task['id']}").json()
    assert len(detail["links"]) == 1

    assert client.delete(f"/api/tasks/{task['id']}/links/{link['id']}").status_code == 204
    assert client.get(f"/api/tasks/{task['id']}").json()["links"] == []


def test_link_default_type(client, todo_lane):
    task = make_task(client, todo_lane["id"])
    link = client.post(
        f"/api/tasks/{task['id']}/links", json={"url": "https://example.com"}
    ).json()
    assert link["link_type"] == "other"


def test_comment_lifecycle(client, todo_lane):
    task = make_task(client, todo_lane["id"])
    resp = client.post(
        f"/api/tasks/{task['id']}/comments",
        json={"author": "marcin", "body": "looks good", "kind": "comment"},
    )
    assert resp.status_code == 201

    listed = client.get(f"/api/tasks/{task['id']}/comments")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    comment_id = listed.json()[0]["id"]

    assert client.delete(
        f"/api/tasks/{task['id']}/comments/{comment_id}"
    ).status_code == 204
    assert client.get(f"/api/tasks/{task['id']}/comments").json() == []


def test_cascade_delete_removes_children(client, todo_lane):
    a = make_task(client, todo_lane["id"], title="a")
    b = make_task(client, todo_lane["id"], title="b")
    dep = client.post(
        f"/api/tasks/{a['id']}/dependencies", json={"depends_on_task_id": b["id"]}
    ).json()
    link = client.post(
        f"/api/tasks/{a['id']}/links", json={"url": "https://example.com"}
    ).json()
    comment = client.post(
        f"/api/tasks/{a['id']}/comments", json={"author": "m", "body": "hi"}
    ).json()

    assert client.delete(f"/api/tasks/{a['id']}").status_code == 204

    # child rows gone: deleting them again 404, and b's detail has no dependents left
    assert client.delete(
        f"/api/tasks/{a['id']}/dependencies/{dep['id']}"
    ).status_code == 404
    # b still exists and can be deleted cleanly (its dependent row was cascaded)
    assert client.delete(f"/api/tasks/{b['id']}").status_code == 204
    _ = (link, comment)
