"""Пользователи и согласия 152-ФЗ: версия текста и даты выдачи/отзыва хранятся в БД."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import ConsentType
from app.core.security import CurrentUser
from app.users.models import Consent
from app.users.repository import UserRepository


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UserRepository(session)

    async def consents(self, user: CurrentUser) -> list[Any]:
        if user.source == "fixture":
            return self.repo.fixture_consents(user.user_id)
        return await self.repo.consents(user.user_id)

    async def update_consent(
        self, user: CurrentUser, consent_type: ConsentType, granted: bool, version: str
    ) -> Any:
        now = datetime.now(UTC)
        if user.source == "fixture":
            return self._fixture_update(user.user_id, consent_type, granted, version, now)
        consent = await self.repo.consent(user.user_id, str(consent_type))
        if consent is None:
            consent = Consent(user_id=user.user_id, type=str(consent_type), granted=False)
            self.session.add(consent)
        consent.version = version
        if granted:
            consent.granted = True
            consent.granted_at = now
            consent.revoked_at = None
        elif consent.granted:
            consent.granted = False
            consent.revoked_at = now
        await self.session.commit()
        return consent

    def _fixture_update(
        self,
        user_id: int,
        consent_type: ConsentType,
        granted: bool,
        version: str,
        now: datetime,
    ) -> dict[str, Any]:
        """Пользователь из фикстур (демо-режим, до загрузчика 2b): ответ без сохранения."""
        current = next(
            (c for c in self.repo.fixture_consents(user_id) if c["type"] == consent_type), None
        )
        return {
            "id": current["id"] if current else 0,
            "user_id": user_id,
            "type": consent_type,
            "version": version,
            "granted": granted,
            "granted_at": now if granted else (current or {}).get("granted_at"),
            "revoked_at": None if granted else now,
        }
