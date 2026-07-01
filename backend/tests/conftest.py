from __future__ import annotations

import os

os.environ["DATABASE_URL"] = "sqlite:///./data/test.db"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(engine)


@pytest.fixture
def swimlanes(client):
    return client.get("/api/project").json()["swimlanes"]


@pytest.fixture
def todo_lane(swimlanes):
    return next(s for s in swimlanes if s["name"] == "To Do")


@pytest.fixture
def done_lane(swimlanes):
    return next(s for s in swimlanes if s["is_done_column"])


def make_task(client, swimlane_id, title="Task", **extra):
    body = {"title": title, "swimlane_id": swimlane_id, **extra}
    resp = client.post("/api/tasks", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()
