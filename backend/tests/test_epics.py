from __future__ import annotations


def test_epic_crud(client):
    resp = client.post(
        "/api/epics", json={"title": "Auth", "color": "#4f46e5"}
    )
    assert resp.status_code == 201
    epic = resp.json()
    assert epic["title"] == "Auth"
    assert epic["description"] is None
    assert "created_at" in epic

    listed = client.get("/api/epics")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    got = client.get(f"/api/epics/{epic['id']}")
    assert got.status_code == 200

    patched = client.patch(
        f"/api/epics/{epic['id']}", json={"description": "auth work"}
    )
    assert patched.status_code == 200
    assert patched.json()["description"] == "auth work"
    assert patched.json()["title"] == "Auth"

    assert client.delete(f"/api/epics/{epic['id']}").status_code == 204
    assert client.get(f"/api/epics/{epic['id']}").status_code == 404


def test_get_missing_epic_404(client):
    assert client.get("/api/epics/999").status_code == 404


def test_delete_epic_nulls_task_epic_id(client, swimlanes):
    lane_id = swimlanes[0]["id"]
    epic = client.post("/api/epics", json={"title": "E"}).json()
    task = client.post(
        "/api/tasks",
        json={"title": "T", "swimlane_id": lane_id, "epic_id": epic["id"]},
    ).json()
    assert client.delete(f"/api/epics/{epic['id']}").status_code == 204
    refetched = client.get(f"/api/tasks/{task['id']}").json()
    assert refetched["epic_id"] is None
