"""Таблицы авторизации: одноразовые токены почты, refresh-сессии, журнал для ограничения попыток."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin


class EmailToken(TimestampMixin, Base):
    """Подтверждение почты (24 ч) и сброс пароля. В БД только sha256 токена."""

    __tablename__ = "email_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(32))  # verify_email | reset_password
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefreshSession(TimestampMixin, Base):
    """Refresh-сессия: sha256 случайного токена из httpOnly cookie.

    При refresh строка отзывается (`revoked_at`) и выдаётся новая — ротация.
    `user_id` без внешнего ключа: в демо-режиме сессию получают и пользователи из фикстур,
    которых ещё нет в БД (до загрузчика демо-данных); существование проверяется при refresh.
    """

    __tablename__ = "refresh_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    ip: Mapped[str | None] = mapped_column(String(45))


class AuthThrottleEvent(Base):
    """Событие для ограничения частоты: неудачный вход, повторное письмо, сброс пароля.

    kind: login_failed (key = "почта|ip"), resend_verification, password_reset (key = почта).
    """

    __tablename__ = "auth_throttle_events"
    __table_args__ = (Index("ix_auth_throttle_events_kind_key", "kind", "key", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32))
    key: Mapped[str] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
