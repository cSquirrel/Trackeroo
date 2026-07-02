from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .models import CommentKind, LinkType

Priority = Literal["low", "medium", "high", "urgent"]

# ---------------------------------------------------------------------------
# SwimLane
# ---------------------------------------------------------------------------


class SwimLaneBase(BaseModel):
    name: str
    position: int = 0
    is_done_column: bool = False


class SwimLaneCreate(SwimLaneBase):
    pass


class SwimLaneUpdate(BaseModel):
    name: str | None = None
    position: int | None = None
    is_done_column: bool | None = None


class SwimLaneOut(SwimLaneBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int


class SwimLaneReorder(BaseModel):
    ordered_ids: list[int]


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


class ProjectBase(BaseModel):
    name: str
    description: str | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ProjectOut(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    swimlanes: list[SwimLaneOut] = []


# ---------------------------------------------------------------------------
# Epic
# ---------------------------------------------------------------------------


class EpicBase(BaseModel):
    title: str
    description: str | None = None
    color: str | None = None
    priority: Priority | None = None


class EpicCreate(EpicBase):
    pass


class EpicUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    color: str | None = None
    priority: Priority | None = None


class EpicOut(EpicBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# TaskLink
# ---------------------------------------------------------------------------


class TaskLinkBase(BaseModel):
    url: str
    label: str | None = None
    link_type: LinkType = LinkType.other


class TaskLinkCreate(TaskLinkBase):
    pass


class TaskLinkUpdate(BaseModel):
    url: str | None = None
    label: str | None = None
    link_type: LinkType | None = None


class TaskLinkOut(TaskLinkBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int


# ---------------------------------------------------------------------------
# Comment
# ---------------------------------------------------------------------------


class CommentBase(BaseModel):
    author: str
    body: str
    kind: CommentKind = CommentKind.comment


class CommentCreate(CommentBase):
    pass


class CommentUpdate(BaseModel):
    author: str | None = None
    body: str | None = None
    kind: CommentKind | None = None


class CommentOut(CommentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# TaskDependency
# ---------------------------------------------------------------------------


class TaskDependencyCreate(BaseModel):
    depends_on_task_id: int


class TaskDependencyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    depends_on_task_id: int


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------


class TaskBase(BaseModel):
    title: str
    description: str | None = None
    # Free-text ticket type ("chore", "fix", "feature", or anything the user
    # wants) — deliberately open, not a fixed enum.
    type: str | None = None
    priority: Priority | None = None
    epic_id: int | None = None
    swimlane_id: int
    position: int = 0


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    type: str | None = None
    priority: Priority | None = None
    epic_id: int | None = None
    swimlane_id: int | None = None
    position: int | None = None
    is_blocked: bool | None = None
    blocked_reason: str | None = None


class TaskOut(BaseModel):
    """Summary representation of a task (list views)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None = None
    type: str | None = None
    priority: Priority | None = None
    epic_id: int | None = None
    swimlane_id: int
    position: int
    is_blocked: bool
    blocked_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class TaskDetail(TaskOut):
    """Full representation nesting comments, links, and dependencies."""

    comments: list[CommentOut] = []
    links: list[TaskLinkOut] = []
    dependencies: list[TaskDependencyOut] = []


# ---------------------------------------------------------------------------
# Task action bodies
# ---------------------------------------------------------------------------


class TaskMove(BaseModel):
    swimlane_id: int
    position: int


class TaskMoveResult(TaskOut):
    warnings: list[str] = []


class TaskBlock(BaseModel):
    reason: str
