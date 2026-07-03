"""Entry point for the PyInstaller-bundled backend sidecar.

Runs the FastAPI app under uvicorn on the fixed sidecar port. Kept separate
from app/ so PyInstaller has a concrete script target; the Tauri Rust shell
launches the resulting standalone binary in release builds.

If TRACKEROO_IDLE_TIMEOUT_MINUTES is set (only the MCP server's auto-spawn
path sets it — the app's Rust shell never does), the process exits on its own
after that many minutes with no HTTP requests, so MCP-spawned backends don't
accumulate forever. GUI-spawned backends are unaffected: the app keeps
killing its backend on quit exactly as before.
"""

from __future__ import annotations

import os
import threading
import time

import uvicorn

from app.main import app

_idle_minutes = os.environ.get("TRACKEROO_IDLE_TIMEOUT_MINUTES")
if _idle_minutes:
    _last_activity = {"at": time.monotonic()}

    @app.middleware("http")
    async def _track_activity(request, call_next):
        _last_activity["at"] = time.monotonic()
        return await call_next(request)

    def _idle_watchdog() -> None:
        timeout = float(_idle_minutes) * 60
        # Poll interval scaled down for short timeouts so tests don't wait 30s.
        interval = min(30.0, max(0.5, timeout / 4))
        while True:
            time.sleep(interval)
            if time.monotonic() - _last_activity["at"] > timeout:
                os._exit(0)

    threading.Thread(target=_idle_watchdog, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("TRACKEROO_PORT", "8787"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
