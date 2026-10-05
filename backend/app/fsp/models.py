"""Привязка ФСП ID и кэш достижений из реестра ФСП."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class FspLink(Base):
    __tablename__ = "fsp_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), unique=True
    )
    fsp_id: Mapped[str] = mapped_column(String(16), unique=True)
    keycloak_sub: Mapped[str | None] = mapped_column(String(64))
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FspAchievement(Base):
    """Кэш достижения участника (наша версия API реестра ФСП)."""

    __tablename__ = "fsp_achievements"
    __table_args__ = (UniqueConstraint("fsp_id", "external_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fsp_id: Mapped[str] = mapped_column(String(16), index=True)
    external_id: Mapped[str] = mapped_column(String(64), comment="id достижения в реестре")
    competition: Mapped[str] = mapped_column(String(300))
    discipline: Mapped[str] = mapped_column(String(32))
    level: Mapped[str] = mapped_column(String(32))
    date: Mapped[date] = mapped_column(Date)
    place: Mapped[int | None] = mapped_column(Integer)
    diploma: Mapped[str | None] = mapped_column(String(100))
    team: Mapped[str | None] = mapped_column(String(200))
    role: Mapped[str | None] = mapped_column(String(100))
    rating: Mapped[float | None] = mapped_column(Float)
    protocol_url: Mapped[str | None] = mapped_column(String(500))
    verified: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
