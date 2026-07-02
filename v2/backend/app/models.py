from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LinkType(str, enum.Enum):
    pr = "pr"
    slack = "slack"
    other = "other"


class CommentKind(str, enum.Enum):
    comment = "comment"
    annotation = "annotation"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    swimlanes: Mapped[list["SwimLane"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="SwimLane.position",
    )


class SwimLane(Base):
    __tablename__ = "swimlanes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_done_column: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    project: Mapped["Project"] = relationship(back_populates="swimlanes")
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="swimlane",
        cascade="all, delete-orphan",
        order_by="Task.position",
    )


class Epic(Base):
    __tablename__ = "epics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str | None] = mapped_column(String(9), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    tasks: Mapped[list["Task"]] = relationship(back_populates="epic")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    epic_id: Mapped[int | None] = mapped_column(
        ForeignKey("epics.id", ondelete="SET NULL"), nullable=True
    )
    swimlane_id: Mapped[int] = mapped_column(
        ForeignKey("swimlanes.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Free-text ticket type ("chore", "fix", "feature", or anything the user
    # wants) — deliberately not an enum/CHECK constraint, so it stays open.
    type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_blocked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    epic: Mapped["Epic | None"] = relationship(back_populates="tasks")
    swimlane: Mapped["SwimLane"] = relationship(back_populates="tasks")

    comments: Mapped[list["Comment"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="Comment.created_at",
    )
    links: Mapped[list["TaskLink"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )
    # Dependencies this task has (rows where this task is task_id).
    dependencies: Mapped[list["TaskDependency"]] = relationship(
        back_populates="task",
        foreign_keys="TaskDependency.task_id",
        cascade="all, delete-orphan",
    )
    # Rows where other tasks depend on this task.
    dependents: Mapped[list["TaskDependency"]] = relationship(
        back_populates="depends_on",
        foreign_keys="TaskDependency.depends_on_task_id",
        cascade="all, delete-orphan",
    )


class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    __table_args__ = (
        CheckConstraint(
            "task_id != depends_on_task_id", name="ck_no_self_dependency"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    depends_on_task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )

    task: Mapped["Task"] = relationship(
        back_populates="dependencies", foreign_keys=[task_id]
    )
    depends_on: Mapped["Task"] = relationship(
        back_populates="dependents", foreign_keys=[depends_on_task_id]
    )


class TaskLink(Base):
    __tablename__ = "task_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    link_type: Mapped[LinkType] = mapped_column(
        SAEnum(LinkType, name="link_type"), nullable=False, default=LinkType.other
    )

    task: Mapped["Task"] = relationship(back_populates="links")


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[CommentKind] = mapped_column(
        SAEnum(CommentKind, name="comment_kind"),
        nullable=False,
        default=CommentKind.comment,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    task: Mapped["Task"] = relationship(back_populates="comments")
