"""Entry point for the PyInstaller-bundled backend sidecar.

Runs the FastAPI app under uvicorn on the fixed sidecar port. Kept separate
from app/ so PyInstaller has a concrete script target; the Tauri Rust shell
launches the resulting standalone binary in release builds.
"""

from __future__ import annotations

import os

import uvicorn

from app.main import app

if __name__ == "__main__":
    port = int(os.environ.get("TRACKEROO_PORT", "8787"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
