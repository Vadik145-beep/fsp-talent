"""Пользователи и согласия: БД; для пользователей из фикстур (демо-режим) — `consents.json`."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.models  # noqa: F401 — все таблицы в metadata, иначе ORM не разрешит внешние ключи
from app.common import fixtures
from app.common.fixtures import Record
from app.users.models import Consent, User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def consents(self, user_id: int) -> list[Consent]:
        return list(
            (
                await self.session.execute(
                    select(Consent).where(Consent.user_id == user_id).order_by(Consent.id)
                )
            ).scalars()
        )

    async def consent(self, user_id: int, consent_type: str) -> Consent | None:
        return (
            await self.session.execute(
                select(Consent)
                .where(Consent.user_id == user_id, Consent.type == consent_type)
                .order_by(Consent.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    @staticmethod
    def fixture_consents(user_id: int) -> list[Record]:
        return fixtures.where("consents", user_id=user_id)
