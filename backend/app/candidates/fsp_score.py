"""ФСП-скор и бейджи кандидата по кэшу достижений (T5.3).

Формула та же, что в генераторе фикстур (`scripts/seed/generate_fixtures.py`):
скор = 100 · (1 − e^(−Σ / 2,5)), где Σ = Σ уровень × место × свежесть,
уровень: региональный 1, всероссийский 2, международный 3;
место: 1 → 1,0; 2 → 0,8; 3 → 0,65; другое место → 0,45; без места → 0,3;
свежесть = e^(−возраст в годах / 2).
Снимок (скор + бейджи) хранится в профиле: по нему сортируется банк кандидатов.
"""

import math
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates.models import CandidateProfile
from app.catalog.clock import now_msk
from app.fsp.models import FspAchievement, FspLink

LEVEL_WEIGHT = {"regional": 1.0, "national": 2.0, "international": 3.0}
LEVEL_LABEL = {
    "regional": "регионального",
    "national": "всероссийского",
    "international": "международного",
}


def _place_weight(place: int | None) -> float:
    return {1: 1.0, 2: 0.8, 3: 0.65}.get(place or 0, 0.3 if place is None else 0.45)


def fsp_score(achievements: list[dict[str, Any]], today: date | None = None) -> float | None:
    if not achievements:
        return None
    today = today or now_msk().date()
    total = 0.0
    for a in achievements:
        age_years = (today - a["date"]).days / 365
        total += (
            LEVEL_WEIGHT.get(a["level"], 1.0)
            * _place_weight(a.get("place"))
            * math.exp(-age_years / 2)
        )
    return round(100 * (1 - math.exp(-total / 2.5)), 1)


def fsp_badges(achievements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    badges: list[dict[str, Any]] = []
    for level in ("international", "national", "regional"):
        if any(a["level"] == level and a.get("place") and a["place"] <= 3 for a in achievements):
            badges.append(
                {
                    "id": f"{level}_prize",
                    "title": f"Призёр {LEVEL_LABEL[level]} соревнования",
                    "level": level,
                    "verified": True,
                }
            )
    if len(achievements) >= 2:
        badges.append(
            {
                "id": "participant_many",
                "title": f"Участник {len(achievements)} соревнований ФСП",
                "level": None,
                "verified": True,
            }
        )
    elif len(achievements) == 1 and not badges:
        badges.append(
            {
                "id": "participant",
                "title": "Участник соревнования ФСП",
                "level": None,
                "verified": True,
            }
        )
    return badges


async def achievements_for(session: AsyncSession, fsp_id: str) -> list[dict[str, Any]]:
    rows = await session.scalars(select(FspAchievement).where(FspAchievement.fsp_id == fsp_id))
    return [{"date": a.date, "level": a.level, "place": a.place} for a in rows]


async def refresh_fsp_snapshot(session: AsyncSession, candidate_id: int) -> None:
    """Пересчитать снимок ФСП-скора и бейджей кандидата (вызывать после синхронизации
    достижений или привязки/отвязки ФСП ID). Коммит — за вызывающим."""
    profile = await session.get(CandidateProfile, candidate_id)
    if profile is None:
        return
    fsp_id = await session.scalar(
        select(FspLink.fsp_id).where(FspLink.candidate_id == candidate_id)
    )
    achs = await achievements_for(session, fsp_id) if fsp_id else []
    profile.fsp_score = fsp_score(achs)
    profile.fsp_badges = fsp_badges(achs)
