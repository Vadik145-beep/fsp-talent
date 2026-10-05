"""Потребность работодателя (запрос на подбор)."""

from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin


class Need(TimestampMixin, Base):
    __tablename__ = "needs"
    __table_args__ = (
        CheckConstraint("salary_from > 0 AND salary_from <= salary_to", name="salary_range"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    recruiter_id: Mapped[int] = mapped_column(ForeignKey("recruiters.id"))
    title: Mapped[str] = mapped_column(String(200))
    raw_text: Mapped[str | None] = mapped_column(Text)
    specialization: Mapped[str] = mapped_column(ForeignKey("specializations.code"))
    grade: Mapped[str] = mapped_column(ForeignKey("grades.code"))
    category: Mapped[str] = mapped_column(ForeignKey("categories.code"), index=True)
    skills_required: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    skills_desired: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    team_description: Mapped[str] = mapped_column(Text, default="")
    work_format: Mapped[str] = mapped_column(String(16))
    city: Mapped[str | None] = mapped_column(String(100))
    salary_from: Mapped[int] = mapped_column(Integer)
    salary_to: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="active")
    saved_filters: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, comment="Уточнения подборки (T6.4)"
    )
