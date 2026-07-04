"""Discover-or-spawn the Trackeroo backend for a project folder.

Lets MCP work without the desktop app open: if `.trackeroo/.env` points at a
live backend, reuse it; otherwise spawn the backend ourselves (the same
`run_sidecar.py` entry point the app's Rust shell uses), health-check it, and
write `.env` exactly the way the app does — so the app, other MCP processes,
and this one all discover each other through the same file.

The `.env` file stores ``TRACKEROO_API_URL=<full-origin>`` (e.g.
``http://localhost:8787``).  Carrying full URLs through the whole chain — env
file, health-check, return value — means a future remote API only needs the
URL to change; nothing else in the MCP needs to know whether the backend is
local or remote.

Concurrent spawners (parallel tool calls, multiple MCP clients on one project)
are serialized with an exclusive `flock` on `.trackeroo/.spawn.lock`; whoever
loses the race finds the fresh `.env` inside the lock and reuses it. `flock`
is released by the OS if the holder dies, so there's no stale-lock cleanup.

MCP-spawned backends set TRACKEROO_IDLE_TIMEOUT_MINUTES so they shut
themselves down after a period of no HTTP traffic (see run_sidecar.py) —
GUI-spawned backends never get that variable and behave exactly as before.
"""

from __future__ import annotations

import fcntl
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

_DEFAULT_IDLE_MINUTES = "30"
_HEALTH_ATTEMPTS = 60
_HEALTH_INTERVAL_S = 0.4


def _state_dir(folder: Path) -> Path:
    return folder / ".trackeroo"


def _env_file(folder: Path) -> Path:
    return _state_dir(folder) / ".env"


def _db_path(folder: Path) -> Path:
    return _state_dir(folder) / "trackeroo.db"


def _lock_file(folder: Path) -> Path:
    return _state_dir(folder) / ".spawn.lock"


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


def _read_url(folder: Path) -> str | None:
    """Read the backend URL from the project's ``.env`` file.

    Returns ``None`` when the file is missing or contains no
    ``TRACKEROO_API_URL`` entry.  Raises if the value is present but
    malformed so callers don't silently ignore a bad configuration.
    """
    try:
        env = _parse_env_file(_env_file(folder).read_text())
    except FileNotFoundError:
        return None
    url = env.get("TRACKEROO_API_URL")
    if not url:
        return None
    url = url.rstrip("/")
    if not url.startswith(("http://", "https://")):
        raise RuntimeError(
            f"TRACKEROO_API_URL in {_env_file(folder)} is not a valid HTTP URL: {url!r}"
        )
    return url


def _health_ok(base_url: str) -> bool:
    try:
        return httpx.get(f"{base_url}/api/health", timeout=1.0).is_success
    except httpx.HTTPError:
        return False


def _pick_free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _migrate_legacy_layout(folder: Path) -> None:
    """Mirror of the Rust shell's migrate_legacy_layout: projects created
    before `.trackeroo/` existed keep their db loose at `<folder>/trackeroo.db`."""
    new_path = _db_path(folder)
    if new_path.exists():
        return
    legacy_path = folder / "trackeroo.db"
    if not legacy_path.exists():
        return
    _state_dir(folder).mkdir(parents=True, exist_ok=True)
    legacy_path.rename(new_path)


def _spawn_backend(folder: Path, port: int) -> subprocess.Popen:
    env = {
        **os.environ,
        "TRACKEROO_PORT": str(port),
        "DATABASE_URL": f"sqlite:///{_db_path(folder)}",
        "TRACKEROO_IDLE_TIMEOUT_MINUTES": os.environ.get(
            "TRACKEROO_IDLE_TIMEOUT_MINUTES", _DEFAULT_IDLE_MINUTES
        ),
    }
    if getattr(sys, "frozen", False):
        # Installed app: trackeroo-backend is a sibling binary in Contents/MacOS/.
        cmd = [str(Path(sys.executable).resolve().parent / "trackeroo-backend")]
        cwd = None
    else:
        backend_dir = Path(__file__).resolve().parent.parent / "backend"
        cmd = [str(backend_dir / ".venv" / "bin" / "python"), str(backend_dir / "run_sidecar.py")]
        cwd = backend_dir
    # start_new_session so the backend survives this MCP process's exit/SIGHUP;
    # it cleans itself up via the idle timeout instead of dying with us.
    return subprocess.Popen(
        cmd,
        env=env,
        cwd=cwd,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _wait_for_health(base_url: str) -> bool:
    for _ in range(_HEALTH_ATTEMPTS):
        if _health_ok(base_url):
            return True
        time.sleep(_HEALTH_INTERVAL_S)
    return False


def ensure_backend_running(folder: Path) -> str:
    """Return the base URL of a healthy backend for *folder*, spawning one if needed.

    The returned URL is a full origin (e.g. ``http://localhost:9123``) — callers
    append ``/api/…`` paths to it directly.
    """
    folder = Path(folder).resolve()

    url = _read_url(folder)
    if url is not None and _health_ok(url):
        return url

    # Refuse to shadow-create an empty database on a typo'd/foreign path —
    # same rule as the app's project picker.
    if not _db_path(folder).exists() and not (folder / "trackeroo.db").exists():
        raise RuntimeError(
            f"No Trackeroo project found in {folder} (missing trackeroo.db)."
        )

    _state_dir(folder).mkdir(parents=True, exist_ok=True)
    with open(_lock_file(folder), "a+") as lockfile:
        fcntl.flock(lockfile, fcntl.LOCK_EX)
        try:
            # Double-check inside the lock: another caller may have just spawned it.
            url = _read_url(folder)
            if url is not None and _health_ok(url):
                return url

            _migrate_legacy_layout(folder)
            new_port = _pick_free_port()
            new_url = f"http://localhost:{new_port}"
            proc = _spawn_backend(folder, new_port)
            if not _wait_for_health(new_url):
                proc.kill()
                raise RuntimeError(
                    f"Trackeroo backend for '{folder}' did not become healthy in time."
                )
            _env_file(folder).write_text(f"TRACKEROO_API_URL={new_url}\n")
            return new_url
        finally:
            fcntl.flock(lockfile, fcntl.LOCK_UN)
