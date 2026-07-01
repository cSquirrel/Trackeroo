from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Project
from ..schemas import ProjectOut, ProjectUpdate

router = APIRouter(prefix="/api", tags=["project"])


def _get_project(db: Session) -> Project:
    project = db.scalar(select(Project))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/project", response_model=ProjectOut)
def get_project(db: Session = Depends(get_db)) -> Project:
    return _get_project(db)


@router.patch("/project", response_model=ProjectOut)
def update_project(
    payload: ProjectUpdate, db: Session = Depends(get_db)
) -> Project:
    project = _get_project(db)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project
