"""Вакансии и отклики кандидатов."""

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
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin


class Vacancy(TimestampMixin, Base):
    __tablename__ = "vacancies"
    __table_args__ = (
        CheckConstraint("salary_from > 0 AND salary_from <= salary_to", name="salary_range"),
        # лента опубликованных вакансий (миграция 0006_5a)
        Index("ix_vacancies_status_published", "status", "published_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    # описание команды (миграция 0006_5a)
    team_description: Mapped[str] = mapped_column(Text, default="", server_default="")
    specialization: Mapped[str] = mapped_column(ForeignKey("specializations.code"))
    grade: Mapped[str] = mapped_column(ForeignKey("grades.code"))
    category: Mapped[str] = mapped_column(ForeignKey("categories.code"), index=True)
    skills_required: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    skills_desired: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    work_format: Mapped[str] = mapped_column(String(16))
    city: Mapped[str | None] = mapped_column(String(100))
    salary_from: Mapped[int] = mapped_column(Integer)
    salary_to: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), index=True)  # draft|published|unpublished
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Application(TimestampMixin, Base):
    """Отклик кандидата на вакансию — компания сразу видит контакты."""

    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("vacancy_id", "candidate_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    vacancy_id: Mapped[int] = mapped_column(
        ForeignKey("vacancies.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True
    )
    cover_letter: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16))  # new|viewed|invited|rejected
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
