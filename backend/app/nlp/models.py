"""Тесты, собранные из текста вакансии (T4.8): хранятся целиком — для списка и объяснения."""

from typing import Any

from sqlalchemy import BigInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin


class VacancyTest(TimestampMixin, Base):
    __tablename__ = "vacancy_tests"
    __test__ = False

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    vacancy_title: Mapped[str] = mapped_column(String(200))
    vacancy_text: Mapped[str] = mapped_column(Text)
    specialization: Mapped[str] = mapped_column(String(32))
    grade: Mapped[str] = mapped_column(String(16))
    parser: Mapped[str] = mapped_column(String(16), default="rules")
    # topics / items / drafts / explanation — форма VacancyTestResult
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
