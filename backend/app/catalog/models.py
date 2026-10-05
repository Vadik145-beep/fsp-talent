"""Справочники: специализации, грейды, категории, темы, стек, настройки платформы."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Specialization(Base):
    __tablename__ = "specializations"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    label: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Grade(Base):
    __tablename__ = "grades"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    label: Mapped[str] = mapped_column(String(64))
    order: Mapped[int] = mapped_column(Integer, unique=True)


class Category(Base):
    """Категория = специализация × грейд, код `<spec>:<grade>`."""

    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("specialization", "grade"),)

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    specialization: Mapped[str] = mapped_column(ForeignKey("specializations.code"))
    grade: Mapped[str] = mapped_column(ForeignKey("grades.code"))
    label: Mapped[str] = mapped_column(String(128))


class Topic(Base):
    __tablename__ = "topics"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    specialization: Mapped[str] = mapped_column(ForeignKey("specializations.code"), index=True)
    label: Mapped[str] = mapped_column(String(128))


skill_specializations = Table(
    "skill_specializations",
    Base.metadata,
    Column("skill_code", ForeignKey("skills.code", ondelete="CASCADE"), primary_key=True),
    Column("specialization", ForeignKey("specializations.code"), primary_key=True),
)


class Skill(Base):
    """Технология из справочника стека (связь со специализациями — skill_specializations)."""

    __tablename__ = "skills"

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    label: Mapped[str] = mapped_column(String(64))


class PlatformSetting(Base):
    """Настройки платформы ключ → JSON (пороги θ, кулдауны, квота, веса ранжирования)."""

    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
