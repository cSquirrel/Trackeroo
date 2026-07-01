"""Fixtures for the MCP integration suite.

Boots the *real* Trackeroo Docker Compose stack on an isolated port + named
volume, waits for it to be healthy, and exposes a helper that drives the MCP
server exactly as a client would (via the SDK's in-memory client session), so
the tests exercise tool registration, argument schemas, and error propagation
rather than calling the plain Python functions behind the `@mcp.tool()`
decorators.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import anyio
import httpx
import pytest

# Must be set before `server` is imported anywhere, since server.py binds its
# httpx client to TRACKEROO_API_URL at import time.
TEST_PORT = 8100
TEST_API_URL = f"http://localhost:{TEST_PORT}"
os.environ["TRACKEROO_API_URL"] = TEST_API_URL

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parents[1]

# Make server.py (in mcp/) importable regardless of the cwd pytest runs from.
sys.path.insert(0, str(TESTS_DIR.parent))
PROJECT_NAME = "trackeroo-mcp-test"

_COMPOSE_BASE = [
    "docker",
    "compose",
    "-p",
    PROJECT_NAME,
    "-f",
    str(REPO_ROOT / "docker-compose.yml"),
    "-f",
    str(TESTS_DIR / "docker-compose.test.yml"),
]


def _compose(*args: str) -> None:
    subprocess.run([*_COMPOSE_BASE, *args], check=True)


def _wait_for_health(timeout: float = 180.0) -> None:
    deadline = time.monotonic() + timeout
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(f"{TEST_API_URL}/api/health", timeout=3.0)
            if resp.status_code == 200:
                return
        except httpx.HTTPError as exc:  # not up yet
            last_err = exc
        time.sleep(2.0)
    raise RuntimeError(
        f"Trackeroo stack did not become healthy at {TEST_API_URL} within "
        f"{timeout}s (last error: {last_err})"
    )


@pytest.fixture(scope="session", autouse=True)
def docker_stack() -> Any:
    """Bring the stack up for the whole session, tearing it down unconditionally."""
    _compose("up", "--build", "-d")
    try:
        _wait_for_health()
        yield
    finally:
        # down -v removes the isolated named volume too, so no test data leaks.
        _compose("down", "-v")


@pytest.fixture(scope="session")
def mcp_call():
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
