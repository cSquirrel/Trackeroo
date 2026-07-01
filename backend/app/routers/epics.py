from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Epic
from ..schemas import EpicCreate, EpicOut, EpicUpdate

router = APIRouter(prefix="/api/epics", tags=["epics"])


def _get_epic(db: Session, epic_id: int) -> Epic:
    epic = db.get(Epic, epic_id)
    if epic is None:
        raise HTTPException(status_code=404, detail="Epic not found")
    return epic


@router.get("", response_model=list[EpicOut])
def list_epics(db: Session = Depends(get_db)) -> list[Epic]:
    return list(db.scalars(select(Epic).order_by(Epic.id)))


@router.post("", response_model=EpicOut, status_code=201)
def create_epic(payload: EpicCreate, db: Session = Depends(get_db)) -> Epic:
    epic = Epic(**payload.model_dump())
    db.add(epic)
    db.commit()
    db.refresh(epic)
    return epic


@router.get("/{epic_id}", response_model=EpicOut)
def get_epic(epic_id: int, db: Session = Depends(get_db)) -> Epic:
    return _get_epic(db, epic_id)


@router.patch("/{epic_id}", response_model=EpicOut)
def update_epic(
    epic_id: int, payload: EpicUpdate, db: Session = Depends(get_db)
) -> Epic:
    epic = _get_epic(db, epic_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(epic, field, value)
    db.commit()
    db.refresh(epic)
    return epic


@router.delete("/{epic_id}", status_code=204)
def delete_epic(epic_id: int, db: Session = Depends(get_db)) -> None:
    epic = _get_epic(db, epic_id)
    db.delete(epic)
    db.commit()
