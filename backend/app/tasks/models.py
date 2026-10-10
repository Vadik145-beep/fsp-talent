"""Регулярные короткие задания и ответы кандидатов."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin


class RegularTask(TimestampMixin, Base):
    __tablename__ = "regular_tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    recruiter_id: Mapped[int] = mapped_column(ForeignKey("recruiters.id"))
    title: Mapped[str] = mapped_column(String(200))
    statement: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(ForeignKey("categories.code"), index=True)
    deadline_days: Mapped[int] = mapped_column(Integer, default=7)
    status: Mapped[str] = mapped_column(String(16), default="active")


class TaskSubmission(Base):
    """Задание, предложенное кандидату, и его ответ.

    assigned → submitted → graded; assigned → skipped (выбрал другое) | expired (срок вышел).
    """

    __tablename__ = "task_submissions"
    __table_args__ = (
        CheckConstraint("score IS NULL OR score BETWEEN 0 AND 3", name="score"),
        # одно и то же задание не предлагается кандидату дважды одновременно (миграция 0010)
        Index(
            "uq_task_submissions_offer",
            "candidate_id",
            "task_id",
            unique=True,
            postgresql_where=text("status = 'assigned'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("regular_tasks.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(16))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    answer_kind: Mapped[str | None] = mapped_column(String(16))
    answer_text: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score: Mapped[int | None] = mapped_column(Integer)
    grader_comment: Mapped[str | None] = mapped_column(Text)
    graded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
