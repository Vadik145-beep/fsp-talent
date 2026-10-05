"""Запросы к БД модуля ФСП: привязки `fsp_links` и кэш достижений `fsp_achievements`."""

from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates.models import CandidateProfile
from app.fsp.models import FspAchievement, FspLink


class FspRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def candidate_user_id(self, candidate_id: int) -> int | None:
        stmt = select(CandidateProfile.user_id).where(CandidateProfile.id == candidate_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def link_by_candidate(self, candidate_id: int) -> FspLink | None:
        stmt = select(FspLink).where(FspLink.candidate_id == candidate_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def link_by_fsp_id(self, fsp_id: str) -> FspLink | None:
        stmt = select(FspLink).where(FspLink.fsp_id == fsp_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def links_for_candidates(self, candidate_ids: Iterable[int]) -> list[FspLink]:
        ids = list(candidate_ids)
        if not ids:
            return []
        stmt = select(FspLink).where(FspLink.candidate_id.in_(ids))
        return list((await self.session.execute(stmt)).scalars())

    async def all_links(self) -> list[FspLink]:
        stmt = select(FspLink).order_by(FspLink.fsp_id)
        return list((await self.session.execute(stmt)).scalars())

    async def add_link(
        self, candidate_id: int, fsp_id: str, keycloak_sub: str | None, now: datetime
    ) -> FspLink:
        link = FspLink(
            candidate_id=candidate_id, fsp_id=fsp_id, keycloak_sub=keycloak_sub, linked_at=now
        )
        self.session.add(link)
        await self.session.flush()
        return link

    async def delete_link(self, link: FspLink) -> None:
        await self.session.delete(link)
        await self.session.flush()

    async def achievements(self, fsp_id: str) -> list[FspAchievement]:
        stmt = (
            select(FspAchievement)
            .where(FspAchievement.fsp_id == fsp_id)
            .order_by(FspAchievement.date.desc(), FspAchievement.id.desc())
        )
        return list((await self.session.execute(stmt)).scalars())

    async def achievements_by_fsp_ids(
        self, fsp_ids: Iterable[str]
    ) -> dict[str, list[FspAchievement]]:
        ids = list(fsp_ids)
        result: dict[str, list[FspAchievement]] = {i: [] for i in ids}
        if not ids:
            return result
        stmt = (
            select(FspAchievement)
            .where(FspAchievement.fsp_id.in_(ids))
            .order_by(FspAchievement.date.desc(), FspAchievement.id.desc())
        )
        for row in (await self.session.execute(stmt)).scalars():
            result[row.fsp_id].append(row)
        return result

    async def delete_achievements(self, fsp_id: str) -> None:
        await self.session.execute(delete(FspAchievement).where(FspAchievement.fsp_id == fsp_id))

    async def replace_achievements(self, fsp_id: str, rows: Sequence[dict[str, Any]]) -> None:
        """Кэш участника целиком заменяется свежим списком из реестра (идемпотентно)."""
        await self.delete_achievements(fsp_id)
        self.session.add_all(FspAchievement(fsp_id=fsp_id, **row) for row in rows)
        await self.session.flush()
