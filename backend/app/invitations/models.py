"""Приглашения кандидату и журнал их событий."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin


class Invitation(TimestampMixin, Base):
    __tablename__ = "invitations"
    __table_args__ = (
        CheckConstraint("salary_from > 0 AND salary_from <= salary_to", name="salary_range"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True
    )
    recruiter_id: Mapped[int] = mapped_column(ForeignKey("recruiters.id"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    need_id: Mapped[int | None] = mapped_column(ForeignKey("needs.id", ondelete="SET NULL"))
    vacancy_id: Mapped[int | None] = mapped_column(ForeignKey("vacancies.id", ondelete="SET NULL"))
    category: Mapped[str] = mapped_column(ForeignKey("categories.code"))
    description: Mapped[str] = mapped_column(Text)
    salary_from: Mapped[int] = mapped_column(Integer)
    salary_to: Mapped[int] = mapped_column(Integer)
    contact_type: Mapped[str] = mapped_column(String(16))
    contact_value: Mapped[str] = mapped_column(String(200))
    task_text: Mapped[str | None] = mapped_column(Text)
    # sent | viewed | accepted | declined | expired | withdrawn
    status: Mapped[str] = mapped_column(String(16), index=True)
    decline_reason: Mapped[str | None] = mapped_column(String(32))
    decline_comment: Mapped[str | None] = mapped_column(Text)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InvitationEvent(Base):
    __tablename__ = "invitation_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    invitation_id: Mapped[int] = mapped_column(
        ForeignKey("invitations.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(32))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_role: Mapped[str | None] = mapped_column(String(16))
