"""Доступ к БД для авторизации: пользователи, токены почты, refresh-сессии, ограничение частоты.

Демо-учётки из `demo_accounts.json` и пользователи `users.json` читаются из фикстур только как
запасной вариант в демо-режиме (пока загрузчик демо-данных не положил их в БД).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

import app.models  # noqa: F401 — все таблицы в metadata, иначе ORM не разрешит внешние ключи
from app.auth.models import AuthThrottleEvent, EmailToken, RefreshSession
from app.auth.tokens import hash_token, new_token, same_hash
from app.common import fixtures
from app.common.fixtures import Record
from app.users.models import User


def utcnow() -> datetime:
    return datetime.now(UTC)


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- пользователи ---

    async def user(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def user_by_email(self, email: str) -> User | None:
        return (
            await self.session.execute(select(User).where(func.lower(User.email) == email.lower()))
        ).scalar_one_or_none()

    @staticmethod
    def fixture_user_by_email(email: str) -> Record | None:
        return next((u for u in fixtures.load("users") if u["email"] == email.lower()), None)

    @staticmethod
    def demo_account(email: str) -> Record | None:
        return next(
            (a for a in fixtures.load("demo_accounts") if a["email"] == email.lower()), None
        )

    @staticmethod
    def demo_accounts() -> list[Record]:
        return fixtures.all_records("demo_accounts")

    # --- одноразовые токены почты ---

    async def create_email_token(self, user_id: int, purpose: str, ttl: timedelta) -> str:
        """Новый токен; прежние неиспользованные токены этого назначения гасятся."""
        await self.session.execute(
            update(EmailToken)
            .where(
                EmailToken.user_id == user_id,
                EmailToken.purpose == purpose,
                EmailToken.used_at.is_(None),
            )
            .values(used_at=utcnow())
        )
        raw = new_token()
        self.session.add(
            EmailToken(
                user_id=user_id,
                purpose=purpose,
                token_hash=hash_token(raw),
                expires_at=utcnow() + ttl,
            )
        )
        await self.session.flush()
        return raw

    async def find_email_token(self, purpose: str, raw: str) -> EmailToken | None:
        row = (
            await self.session.execute(
                select(EmailToken).where(
                    EmailToken.token_hash == hash_token(raw), EmailToken.purpose == purpose
                )
            )
        ).scalar_one_or_none()
        if row is None or not same_hash(row.token_hash, raw):
            return None
        return row

    # --- refresh-сессии ---

    async def create_refresh(
        self, user_id: int, ttl: timedelta, user_agent: str | None, ip: str | None
    ) -> str:
        raw = new_token()
        self.session.add(
            RefreshSession(
                user_id=user_id,
                token_hash=hash_token(raw),
                expires_at=utcnow() + ttl,
                user_agent=(user_agent or "")[:300] or None,
                ip=ip,
            )
        )
        await self.session.flush()
        return raw

    async def claim_refresh(self, raw: str) -> RefreshSession | None:
        """Атомарно отозвать действующую сессию по токену и вернуть её (для ротации и выхода).

        UPDATE ... WHERE revoked_at IS NULL — из двух одновременных refresh с одним токеном
        пройдёт только один.
        """
        token_hash = hash_token(raw)
        row = (
            await self.session.execute(
                update(RefreshSession)
                .where(
                    RefreshSession.token_hash == token_hash,
                    RefreshSession.revoked_at.is_(None),
                    RefreshSession.expires_at > utcnow(),
                )
                .values(revoked_at=utcnow())
                .returning(RefreshSession)
            )
        ).scalar_one_or_none()
        if row is None or not same_hash(row.token_hash, raw):
            return None
        return row

    async def revoke_all_refresh(self, user_id: int) -> None:
        await self.session.execute(
            update(RefreshSession)
            .where(RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )

    # --- ограничение частоты ---

    async def throttle_count(self, kind: str, key: str, window: timedelta) -> int:
        return int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(AuthThrottleEvent)
                    .where(
                        AuthThrottleEvent.kind == kind,
                        AuthThrottleEvent.key == key,
                        AuthThrottleEvent.created_at > utcnow() - window,
                    )
                )
            ).scalar_one()
        )

    async def throttle_add(self, kind: str, key: str, keep: timedelta) -> None:
        """Записать событие и заодно удалить старые события этого ключа."""
        await self.session.execute(
            delete(AuthThrottleEvent).where(
                AuthThrottleEvent.kind == kind,
                AuthThrottleEvent.key == key,
                AuthThrottleEvent.created_at <= utcnow() - keep,
            )
        )
        self.session.add(AuthThrottleEvent(kind=kind, key=key, created_at=utcnow()))
        await self.session.flush()

    async def throttle_clear(self, kind: str, key_prefix: str) -> None:
        await self.session.execute(
            delete(AuthThrottleEvent).where(
                AuthThrottleEvent.kind == kind,
                AuthThrottleEvent.key.startswith(key_prefix, autoescape=True),
            )
        )
