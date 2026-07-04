"""Tests for backend_spawn: MCP's discover-or-spawn of the project backend.

Deliberately NOT in tests/ — that directory's conftest brings up a single,
session-scoped backend (autouse) for the whole suite, whereas these tests need
to spawn and kill their *own* backends per test (to exercise discovery,
respawn, idle timeout, and concurrent spawners) against throwaway temp project
folders. Both suites spawn the real backend via backend/.venv; neither needs
Docker.

Run from mcp/:  .venv/bin/pytest tests_spawn/ -q
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backend_spawn


def _port_of(folder: Path) -> int | None:
    return backend_spawn._read_port(folder)


def _kill_port(port: int) -> None:
    out = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True)
    for pid in out.stdout.split():
        try:
            os.kill(int(pid), signal.SIGKILL)
        except ProcessLookupError:
            pass


@pytest.fixture
def project(tmp_path: Path):
    """A throwaway project folder with an empty (valid) SQLite db; backend
    _bootstrap() creates tables and seeds swimlanes on startup."""
    state = tmp_path / ".trackeroo"
    state.mkdir()
    (state / "trackeroo.db").touch()
    yield tmp_path
    port = _port_of(tmp_path)
    if port:
        _kill_port(port)


def test_missing_project_raises_instead_of_creating(tmp_path: Path):
    with pytest.raises(RuntimeError, match="No Trackeroo project found"):
        backend_spawn.ensure_backend_running(tmp_path)
    # and it didn't shadow-create a database
    assert not (tmp_path / ".trackeroo" / "trackeroo.db").exists()


def test_spawns_when_no_backend(project: Path):
    url = backend_spawn.ensure_backend_running(project)
    resp = httpx.get(f"{url}/api/project", timeout=5.0)
    assert resp.status_code == 200
    assert (project / ".trackeroo" / ".env").read_text().startswith("TRACKEROO_PORT=")


def test_reuses_healthy_backend(project: Path):
    first = backend_spawn.ensure_backend_running(project)
    second = backend_spawn.ensure_backend_running(project)
    assert first == second  # same port — no second spawn


def test_respawns_when_env_points_at_dead_port(project: Path):
    dead_port = backend_spawn._pick_free_port()
    (project / ".trackeroo" / ".env").write_text(f"TRACKEROO_PORT={dead_port}\n")
    url = backend_spawn.ensure_backend_running(project)
    assert url != f"http://localhost:{dead_port}"
    assert httpx.get(f"{url}/api/health", timeout=5.0).status_code == 200


def test_concurrent_callers_spawn_exactly_once(project: Path):
    results: list[str] = []
    errors: list[Exception] = []

    def call() -> None:
        try:
            results.append(backend_spawn.ensure_backend_running(project))
        except Exception as exc:  # surface failures instead of hanging the assert
            errors.append(exc)

    threads = [threading.Thread(target=call) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert not errors
    assert len(set(results)) == 1  # everyone agreed on one backend
    port = int(results[0].rsplit(":", 1)[1])
    listeners = subprocess.run(
        ["lsof", "-ti", f":{port}", "-sTCP:LISTEN"], capture_output=True, text=True
    ).stdout.split()
    assert len(listeners) == 1


def test_migrates_legacy_layout_before_spawn(tmp_path: Path):
    (tmp_path / "trackeroo.db").touch()  # pre-.trackeroo layout
    url = backend_spawn.ensure_backend_running(tmp_path)
    try:
        assert (tmp_path / ".trackeroo" / "trackeroo.db").exists()
        assert not (tmp_path / "trackeroo.db").exists()
        assert httpx.get(f"{url}/api/health", timeout=5.0).status_code == 200
    finally:
        port = _port_of(tmp_path)
        if port:
            _kill_port(port)


def test_idle_timeout_shuts_backend_down(project: Path, monkeypatch):
    monkeypatch.setenv("TRACKEROO_IDLE_TIMEOUT_MINUTES", "0.05")  # 3s idle window
    url = backend_spawn.ensure_backend_running(project)
    assert httpx.get(f"{url}/api/health", timeout=5.0).status_code == 200
    # Don't poll while waiting — every health request counts as activity and
    # resets the idle timer. Sleep silently past timeout+watchdog-interval,
    # then check exactly once.
    time.sleep(10)
    assert not backend_spawn._health_ok(int(url.rsplit(":", 1)[1]))
