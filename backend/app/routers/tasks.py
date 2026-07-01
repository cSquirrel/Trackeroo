from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Comment, SwimLane, Task, TaskDependency, TaskLink
from ..schemas import (
    CommentCreate,
    CommentOut,
    TaskBlock,
    TaskCreate,
    TaskDependencyCreate,
    TaskDependencyOut,
    TaskDetail,
    TaskLinkCreate,
    TaskLinkOut,
    TaskMove,
    TaskMoveResult,
    TaskOut,
    TaskUpdate,
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _get_task(db: Session, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("", response_model=list[TaskOut])
def list_tasks(
    epic_id: int | None = None,
    swimlane_id: int | None = None,
    db: Session = Depends(get_db),
) -> list[Task]:
    stmt = select(Task)
    if epic_id is not None:
        stmt = stmt.where(Task.epic_id == epic_id)
    if swimlane_id is not None:
        stmt = stmt.where(Task.swimlane_id == swimlane_id)
    stmt = stmt.order_by(Task.swimlane_id, Task.position)
    return list(db.scalars(stmt))


@router.post("", response_model=TaskOut, status_code=201)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)) -> Task:
    if db.get(SwimLane, payload.swimlane_id) is None:
        raise HTTPException(status_code=404, detail="SwimLane not found")
    task = Task(**payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/{task_id}", response_model=TaskDetail)
def get_task(task_id: int, db: Session = Depends(get_db)) -> TaskDetail:
    task = _get_task(db, task_id)
    detail = TaskDetail.model_validate(task)
    detail.dependency_ids = [d.depends_on_task_id for d in task.dependencies]
    return detail


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)
) -> Task:
    task = _get_task(db, task_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)) -> None:
    task = _get_task(db, task_id)
    db.delete(task)
    db.commit()


@router.post("/{task_id}/move", response_model=TaskMoveResult)
def move_task(
    task_id: int, payload: TaskMove, db: Session = Depends(get_db)
) -> TaskMoveResult:
    task = _get_task(db, task_id)
    target = db.get(SwimLane, payload.swimlane_id)
    if target is None:
        raise HTTPException(status_code=404, detail="SwimLane not found")

    source_swimlane_id = task.swimlane_id
    siblings = list(
        db.scalars(
            select(Task)
            .where(Task.swimlane_id == target.id, Task.id != task.id)
            .order_by(Task.position)
        )
    )
    index = max(0, min(payload.position, len(siblings)))
    siblings.insert(index, task)
    task.swimlane_id = target.id
    for pos, sibling in enumerate(siblings):
        sibling.position = pos

    if source_swimlane_id != target.id:
        source_tasks = list(
            db.scalars(
                select(Task)
                .where(Task.swimlane_id == source_swimlane_id, Task.id != task.id)
                .order_by(Task.position)
            )
        )
        for pos, sibling in enumerate(source_tasks):
            sibling.position = pos

    warnings: list[str] = []
    if target.is_done_column:
        for dep in task.dependencies:
            dep_task = db.get(Task, dep.depends_on_task_id)
            if dep_task is None:
                continue
            dep_lane = db.get(SwimLane, dep_task.swimlane_id)
            if dep_lane is None or not dep_lane.is_done_column:
                warnings.append(
                    f"Task #{dep_task.id} '{dep_task.title}' is not in a done column"
                )

    db.commit()
    db.refresh(task)
    result = TaskMoveResult.model_validate(task)
    result.warnings = warnings
    return result


@router.post("/{task_id}/block", response_model=TaskOut)
def block_task(
    task_id: int, payload: TaskBlock, db: Session = Depends(get_db)
) -> Task:
    task = _get_task(db, task_id)
    task.is_blocked = True
    task.blocked_reason = payload.reason
    db.commit()
    db.refresh(task)
    return task


@router.post("/{task_id}/unblock", response_model=TaskOut)
def unblock_task(task_id: int, db: Session = Depends(get_db)) -> Task:
    task = _get_task(db, task_id)
    task.is_blocked = False
    task.blocked_reason = None
    db.commit()
    db.refresh(task)
    return task


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


@router.post(
    "/{task_id}/dependencies", response_model=TaskDependencyOut, status_code=201
)
def add_dependency(
    task_id: int, payload: TaskDependencyCreate, db: Session = Depends(get_db)
) -> TaskDependency:
    _get_task(db, task_id)
    depends_on_id = payload.depends_on_task_id
    if depends_on_id == task_id:
        raise HTTPException(
            status_code=400, detail="A task cannot depend on itself"
        )
    if db.get(Task, depends_on_id) is None:
        raise HTTPException(status_code=404, detail="Dependency task not found")

    reverse = db.scalar(
        select(TaskDependency).where(
            TaskDependency.task_id == depends_on_id,
            TaskDependency.depends_on_task_id == task_id,
        )
    )
    if reverse is not None:
        raise HTTPException(
            status_code=422,
            detail="Adding this dependency would create an immediate cycle",
        )

    existing = db.scalar(
        select(TaskDependency).where(
            TaskDependency.task_id == task_id,
            TaskDependency.depends_on_task_id == depends_on_id,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Dependency already exists")

    dependency = TaskDependency(task_id=task_id, depends_on_task_id=depends_on_id)
    db.add(dependency)
    db.commit()
    db.refresh(dependency)
    return dependency


@router.delete("/{task_id}/dependencies/{dependency_id}", status_code=204)
def remove_dependency(
    task_id: int, dependency_id: int, db: Session = Depends(get_db)
) -> None:
    dependency = db.get(TaskDependency, dependency_id)
    if dependency is None or dependency.task_id != task_id:
        raise HTTPException(status_code=404, detail="Dependency not found")
    db.delete(dependency)
    db.commit()


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------


@router.post("/{task_id}/links", response_model=TaskLinkOut, status_code=201)
def add_link(
    task_id: int, payload: TaskLinkCreate, db: Session = Depends(get_db)
) -> TaskLink:
    _get_task(db, task_id)
    link = TaskLink(task_id=task_id, **payload.model_dump())
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.delete("/{task_id}/links/{link_id}", status_code=204)
def remove_link(
    task_id: int, link_id: int, db: Session = Depends(get_db)
) -> None:
    link = db.get(TaskLink, link_id)
    if link is None or link.task_id != task_id:
        raise HTTPException(status_code=404, detail="Link not found")
    db.delete(link)
    db.commit()


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


@router.post("/{task_id}/comments", response_model=CommentOut, status_code=201)
def add_comment(
    task_id: int, payload: CommentCreate, db: Session = Depends(get_db)
) -> Comment:
    _get_task(db, task_id)
    comment = Comment(task_id=task_id, **payload.model_dump())
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.get("/{task_id}/comments", response_model=list[CommentOut])
def list_comments(task_id: int, db: Session = Depends(get_db)) -> list[Comment]:
    _get_task(db, task_id)
    return list(
        db.scalars(
            select(Comment)
            .where(Comment.task_id == task_id)
            .order_by(Comment.created_at)
        )
    )


@router.delete("/{task_id}/comments/{comment_id}", status_code=204)
def remove_comment(
    task_id: int, comment_id: int, db: Session = Depends(get_db)
) -> None:
    comment = db.get(Comment, comment_id)
    if comment is None or comment.task_id != task_id:
        raise HTTPException(status_code=404, detail="Comment not found")
    db.delete(comment)
    db.commit()
