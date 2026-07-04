"""Fixtures for the MCP integration suite.

Spawns the *real* Trackeroo backend — the same `run_sidecar.py` entry point the
app's Rust shell and MCP's `backend_spawn` use — against a throwaway SQLite DB
on an isolated port, waits for it to be healthy, and exposes a helper that
drives the MCP server exactly as a client would (via the SDK's in-memory client
session), so the tests exercise tool registration, argument schemas, and error
propagation rather than calling the plain Python functions behind the
`@mcp.tool()` decorators.

No Docker needed: it runs the backend from `backend/.venv` (create it first with
`python3 -m venv backend/.venv && backend/.venv/bin/pip install -r
backend/requirements.txt`).
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import anyio
import httpx
import pytest

TESTS_DIR = Path(__file__).resolve().parent
MCP_DIR = TESTS_DIR.parent
BACKEND_DIR = MCP_DIR.parent / "backend"

# Make server.py (in mcp/) importable regardless of the cwd pytest runs from.
sys.path.insert(0, str(MCP_DIR))


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_health(base_url: str, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(f"{base_url}/api/health", timeout=3.0)
            if resp.status_code == 200:
                return
        except httpx.HTTPError as exc:  # not up yet
            last_err = exc
        time.sleep(0.25)
    raise RuntimeError(
        f"Trackeroo backend did not become healthy at {base_url} within "
        f"{timeout}s (last error: {last_err})"
    )


@pytest.fixture(scope="session", autouse=True)
def backend_server(tmp_path_factory) -> Any:
    """Run the backend against a throwaway DB for the whole session.

    Autouse + session-scoped so it comes up once, before any test imports
    `server` — that binds its httpx client to TRACKEROO_API_URL at import time,
    so the env var must be set here first.
    """
    port = _pick_free_port()
    base_url = f"http://localhost:{port}"
    os.environ["TRACKEROO_API_URL"] = base_url

    db_path = tmp_path_factory.mktemp("mcp-test-data") / "trackeroo.db"
    python = BACKEND_DIR / ".venv" / "bin" / "python"
    if not python.exists():
        raise RuntimeError(
            f"backend venv not found at {python}. Create it with:\n"
            f"  python3 -m venv {BACKEND_DIR}/.venv && "
            f"{BACKEND_DIR}/.venv/bin/pip install -r {BACKEND_DIR}/requirements.txt"
        )

    env = {
        **os.environ,
        "TRACKEROO_PORT": str(port),
        "DATABASE_URL": f"sqlite:///{db_path}",
    }
    # start_new_session so we can signal the whole process group on teardown.
    proc = subprocess.Popen(
        [str(python), "run_sidecar.py"],
        cwd=str(BACKEND_DIR),
        env=env,
        start_new_session=True,
    )
    try:
        _wait_for_health(base_url)
        yield
    finally:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass


@pytest.fixture(scope="session")
def mcp_call(backend_server):
    """Return a helper that invokes an MCP tool via the SDK's in-memory client.

    The helper returns the CallToolResult so tests can inspect both the text
    payload and the `isError` flag (error paths surface the backend's detail as
    an errored tool result, matching what a real MCP client would receive).
    """
    import server  # imported here so TRACKEROO_API_URL is already set
    from mcp.shared.memory import create_connected_server_and_client_session as connect

    def call(name: str, arguments: dict[str, Any] | None = None):
        async def _run():
            async with connect(server.mcp._mcp_server) as session:
                return await session.call_tool(name, arguments or {})

        return anyio.run(_run)

    return call
