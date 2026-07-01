from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .database import DATABASE_URL, Base, SessionLocal, engine
from .models import Project, SwimLane

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


def _bootstrap() -> None:
    _ensure_sqlite_dir()
    Base.metadata.create_all(engine)

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


app = FastAPI(title="Trackeroo API", version="0.1.0", lifespan=lifespan)

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


# TODO: routers mounted here by Phase 1B (project, swimlanes, epics, tasks, ...)

# TODO: mount StaticFiles at backend/static once frontend is built (Phase 2)
