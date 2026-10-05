"""Банк шаблонов задач, журнал калибровки, сессии теста, ответы, история грейда."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin


class Item(TimestampMixin, Base):
    """Параметрический шаблон задачи (генератор от seed + проверка ответа, IRT a/b)."""

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    specialization: Mapped[str] = mapped_column(ForeignKey("specializations.code"), index=True)
    topic: Mapped[str] = mapped_column(ForeignKey("topics.code"), index=True)
    target_grade: Mapped[str] = mapped_column(ForeignKey("grades.code"))
    format: Mapped[str] = mapped_column(String(32))
    generator: Mapped[str] = mapped_column(String(100), comment="Имя генератора в движке")
    generator_params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    a: Mapped[float] = mapped_column(Float)
    b: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), index=True)  # draft|pilot|active|retired
    source: Mapped[str] = mapped_column(String(16), default="expert")
    exposures: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    correct_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    leak_flag: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    leak_score: Mapped[float] = mapped_column(Float, default=0, server_default="0")


class ItemParamsLog(TimestampMixin, Base):
    """Журнал пересчёта калибровки шаблона."""

    __tablename__ = "item_params_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), index=True)
    a_before: Mapped[float] = mapped_column(Float)
    a_after: Mapped[float] = mapped_column(Float)
    b_before: Mapped[float] = mapped_column(Float)
    b_after: Mapped[float] = mapped_column(Float)
    responses_count: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(64), default="recalibration")


class TestSession(Base):
    __tablename__ = "test_sessions"
    __test__ = False

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True
    )
    specialization: Mapped[str] = mapped_column(ForeignKey("specializations.code"))
    target_grade: Mapped[str] = mapped_column(ForeignKey("grades.code"))
    kind: Mapped[str] = mapped_column(String(16))  # placement|lower|higher
    status: Mapped[str] = mapped_column(String(16), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    items_answered: Mapped[int] = mapped_column(Integer, default=0)
    max_items: Mapped[int] = mapped_column(Integer, default=15)
    theta: Mapped[float | None] = mapped_column(Float)
    se: Mapped[float | None] = mapped_column(Float)
    result_grade: Mapped[str | None] = mapped_column(ForeignKey("grades.code"))
    passed: Mapped[bool | None] = mapped_column(Boolean)
    topic_scores: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    engine_state: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, comment="Состояние движка CAT (трек 0b)"
    )


class TestAnswer(Base):
    """Показ варианта задачи и ответ кандидата. Время считает сервер."""

    __tablename__ = "test_answers"
    __test__ = False

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("test_sessions.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    seed: Mapped[int] = mapped_column(BigInteger)
    position: Mapped[int] = mapped_column(Integer)
    shown_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    answer: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    correct: Mapped[bool | None] = mapped_column(Boolean)
    response_time_ms: Mapped[int | None] = mapped_column(Integer)
    is_scored: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="false — непроверочная (калибровочная) задача"
    )
    theta_after: Mapped[float | None] = mapped_column(Float)
    se_after: Mapped[float | None] = mapped_column(Float)


class GradeHistory(Base):
    __tablename__ = "grade_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    event: Mapped[str] = mapped_column(String(32))
    specialization: Mapped[str | None] = mapped_column(ForeignKey("specializations.code"))
    grade_from: Mapped[str | None] = mapped_column(ForeignKey("grades.code"))
    grade_to: Mapped[str | None] = mapped_column(ForeignKey("grades.code"))
    test_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("test_sessions.id", ondelete="SET NULL")
    )
    comment: Mapped[str] = mapped_column(Text, default="")
