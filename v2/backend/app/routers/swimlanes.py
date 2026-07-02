from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Project, SwimLane
from ..schemas import SwimLaneCreate, SwimLaneOut, SwimLaneReorder, SwimLaneUpdate

router = APIRouter(prefix="/api/swimlanes", tags=["swimlanes"])


def _get_swimlane(db: Session, swimlane_id: int) -> SwimLane:
    swimlane = db.get(SwimLane, swimlane_id)
    if swimlane is None:
        raise HTTPException(status_code=404, detail="SwimLane not found")
    return swimlane


@router.post("", response_model=SwimLaneOut, status_code=201)
def create_swimlane(
    payload: SwimLaneCreate, db: Session = Depends(get_db)
) -> SwimLane:
    project = db.scalar(select(Project))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    swimlane = SwimLane(
        project_id=project.id,
        name=payload.name,
        position=payload.position,
        is_done_column=payload.is_done_column,
    )
    db.add(swimlane)
    db.commit()
    db.refresh(swimlane)
    return swimlane


@router.patch("/{swimlane_id}", response_model=SwimLaneOut)
def update_swimlane(
    swimlane_id: int, payload: SwimLaneUpdate, db: Session = Depends(get_db)
) -> SwimLane:
    swimlane = _get_swimlane(db, swimlane_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(swimlane, field, value)
    db.commit()
    db.refresh(swimlane)
    return swimlane


@router.delete("/{swimlane_id}", status_code=204)
def delete_swimlane(swimlane_id: int, db: Session = Depends(get_db)) -> None:
    swimlane = _get_swimlane(db, swimlane_id)
    if db.query(SwimLane).count() <= 1:
        raise HTTPException(
            status_code=400, detail="At least one swimlane must exist"
        )
    db.delete(swimlane)
    db.commit()


@router.post("/reorder", response_model=list[SwimLaneOut])
def reorder_swimlanes(
    payload: SwimLaneReorder, db: Session = Depends(get_db)
) -> list[SwimLane]:
    swimlanes = list(db.scalars(select(SwimLane)))
    existing_ids = {s.id for s in swimlanes}
    if set(payload.ordered_ids) != existing_ids or len(payload.ordered_ids) != len(
        existing_ids
    ):
        raise HTTPException(
            status_code=400,
            detail="ordered_ids must match the existing swimlane id set",
        )
    by_id = {s.id: s for s in swimlanes}
    for position, swimlane_id in enumerate(payload.ordered_ids):
        by_id[swimlane_id].position = position
    db.commit()
    return list(db.scalars(select(SwimLane).order_by(SwimLane.position)))
