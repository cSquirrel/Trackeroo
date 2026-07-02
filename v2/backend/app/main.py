from __future__ import annotations

import os
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, select, text

from .database import DATABASE_URL, Base, SessionLocal, engine
from .models import Project, SwimLane
from .routers import epics, project, swimlanes, tasks

DEFAULT_SWIMLANES = [
    ("Backlog", False),
    ("To Do", False),
    ("In Progress", False),
    ("Review", False),
    ("Done", True),
]


def _ensure_sqlite_dir() -> None:
    """Make sure the SQLite parent directory exists before create_all."""
    prefix = "sqlite:///"
    if DATABASE_URL.startswith(prefix):
        path = DATABASE_URL[len(prefix):]
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)


def _migrate_add_task_type() -> None:
    """`create_all` only creates missing tables, not missing columns on
    existing ones — add `tasks.type` for databases created before this field
    existed. Cheap and idempotent; safe to run on every startup."""
    columns = {c["name"] for c in inspect(engine).get_columns("tasks")}
    if "type" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN type VARCHAR(50)"))


def _bootstrap() -> None:
    _ensure_sqlite_dir()
    Base.metadata.create_all(engine)
    _migrate_add_task_type()

    with SessionLocal() as db:
        existing = db.scalar(select(Project))
        if existing is None:
            project = Project(
                name="Trackeroo", description="A lightweight self-hosted task board."
            )
            db.add(project)
            db.flush()
            for position, (name, is_done) in enumerate(DEFAULT_SWIMLANES):
                db.add(
                    SwimLane(
                        project_id=project.id,
                        name=name,
                        position=position,
                        is_done_column=is_done,
                    )
                )
            db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _bootstrap()
    yield


app = FastAPI(
    title="Trackeroo API",
    version="0.1.0",
    description="Lightweight self-hosted task tracker: epics, tasks, swimlanes, "
    "dependencies, blockers, comments, and links. This spec is the canonical "
    "REST contract — regenerate docs/openapi.json via "
    "`python -m app.export_openapi` after any route/schema change.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(project.router)
app.include_router(swimlanes.router)
app.include_router(epics.router)
app.include_router(tasks.router)

# Serve the built frontend (copied to backend/static/ in the Docker image) at /.
# Mounted after the API routers so /api/* keeps priority; skipped silently when
# the directory is absent (local dev without a frontend build).
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
