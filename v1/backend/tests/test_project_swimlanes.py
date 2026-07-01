from __future__ import annotations


def test_get_project_includes_ordered_swimlanes(client):
    resp = client.get("/api/project")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Trackeroo"
    positions = [s["position"] for s in data["swimlanes"]]
    assert positions == sorted(positions)
    assert any(s["is_done_column"] for s in data["swimlanes"])


def test_patch_project(client):
    resp = client.patch("/api/project", json={"name": "My Board"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "My Board"
    # description untouched
    assert resp.json()["description"] == "A lightweight self-hosted task board."


def test_swimlane_crud(client):
    resp = client.post(
        "/api/swimlanes", json={"name": "QA", "position": 3, "is_done_column": False}
    )
    assert resp.status_code == 201
    lane = resp.json()
    assert lane["name"] == "QA"
    assert lane["project_id"] == 1

    patched = client.patch(f"/api/swimlanes/{lane['id']}", json={"name": "QA2"})
    assert patched.status_code == 200
    assert patched.json()["name"] == "QA2"

    deleted = client.delete(f"/api/swimlanes/{lane['id']}")
    assert deleted.status_code == 204
    assert client.patch(f"/api/swimlanes/{lane['id']}", json={"name": "x"}).status_code == 404


def test_swimlane_delete_cascades_tasks(client, swimlanes):
    lane_id = swimlanes[0]["id"]
    task = client.post(
        "/api/tasks", json={"title": "T", "swimlane_id": lane_id}
    ).json()
    assert client.delete(f"/api/swimlanes/{lane_id}").status_code == 204
    assert client.get(f"/api/tasks/{task['id']}").status_code == 404


def test_swimlane_reorder(client, swimlanes):
    ids = [s["id"] for s in swimlanes]
    reversed_ids = list(reversed(ids))
    resp = client.post("/api/swimlanes/reorder", json={"ordered_ids": reversed_ids})
    assert resp.status_code == 200
    result = resp.json()
    assert [s["id"] for s in result] == reversed_ids
    assert [s["position"] for s in result] == list(range(len(ids)))


def test_swimlane_reorder_bad_ids(client, swimlanes):
    ids = [s["id"] for s in swimlanes]
    resp = client.post("/api/swimlanes/reorder", json={"ordered_ids": ids[:-1]})
    assert resp.status_code == 400
