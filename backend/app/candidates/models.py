"""Профиль кандидата, его стек и загруженные резюме."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin

candidate_skills = Table(
    "candidate_skills",
    Base.metadata,
    Column(
        "candidate_id",
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("skill_code", ForeignKey("skills.code"), primary_key=True),
    # порядок технологий, как его ввёл кандидат (миграция 0002_2b)
    Column("position", Integer, nullable=False, default=0, server_default="0"),
)


class CandidateProfile(TimestampMixin, Base):
    __tablename__ = "candidate_profiles"
    __table_args__ = (CheckConstraint("min_salary IS NULL OR min_salary >= 0", name="min_salary"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    pseudonym: Mapped[str] = mapped_column(String(32), unique=True)
    phone: Mapped[str | None] = mapped_column(String(32))
    telegram: Mapped[str | None] = mapped_column(String(64))
    city: Mapped[str | None] = mapped_column(String(100))
    work_formats: Mapped[list[str]] = mapped_column(ARRAY(String(16)), default=list)
    specialization: Mapped[str | None] = mapped_column(ForeignKey("specializations.code"))
    grade: Mapped[str | None] = mapped_column(ForeignKey("grades.code"))
    category: Mapped[str | None] = mapped_column(ForeignKey("categories.code"), index=True)
    theta: Mapped[float | None] = mapped_column(Float)
    theta_se: Mapped[float | None] = mapped_column(Float)
    topic_scores: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    roles_in_team: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list)
    experience_years: Mapped[float] = mapped_column(Float, default=0)
    soft_skills: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list)
    about: Mapped[str] = mapped_column(Text, default="")
    links: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    # видна только системе, рекрутеру не отдаётся никогда
    min_salary: Mapped[int | None] = mapped_column(Integer)
    privacy: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    job_search_paused: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # согласие на публикацию профиля работодателям (T2.4); история — в таблице consents
    publication_consent: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    # снимок ФСП-скора и бейджей (T5.3), пересчитывается после синхронизации достижений
    fsp_score: Mapped[float | None] = mapped_column(Float)
    fsp_badges: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    freshness: Mapped[float] = mapped_column(Float, default=0)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    grade_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Resume(TimestampMixin, Base):
    """Загруженное PDF-резюме и результат разбора."""

    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(500))
    parser: Mapped[str] = mapped_column(String(16), default="rules")
    parsed: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
