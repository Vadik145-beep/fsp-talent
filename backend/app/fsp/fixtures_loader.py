"""Загрузка ФСП-части фикстур `data/seed` в БД: `fsp_links` и кэш `fsp_achievements`.

Нужна сиду (загрузчик трека 2b может вызвать `load_fsp_fixtures` после кандидатов) и тестам.
Идемпотентна: повторный вызов приводит ФСП-данные указанных кандидатов к состоянию фикстур.

- связь: `candidates.json` → `fsp_id`, `linked_at` = `created_at` кандидата;
- достижения: `fsp_achievements.json` с теми же id; `external_id` (id в реестре) восстанавливается
  как `ACH-<номер участника>-<порядковый номер>` — фикстура хранит достижения в порядке реестра.
"""

from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates.models import CandidateProfile
from app.common import fixtures
from app.fsp.models import FspAchievement, FspLink

FIXTURE_SYNC_AT = datetime.fromisoformat("2026-10-06T03:00:00+03:00")


def external_id(fsp_id: str, ordinal: int) -> str:
    return f"ACH-{fsp_id.removeprefix('FSP-')}-{ordinal:02d}"


async def load_fsp_fixtures(
    session: AsyncSession, candidate_ids: Iterable[int] | None = None
) -> int:
    """Привести связи и кэш достижений к фикстурам. Возвращает число привязанных кандидатов.

    Кандидаты, которых ещё нет в `candidate_profiles`, пропускаются (внешний ключ).
    """
    wanted = set(candidate_ids) if candidate_ids is not None else None
    cands = [
        c
        for c in fixtures.load("candidates")
        if c.get("fsp_id") and (wanted is None or c["id"] in wanted)
    ]
    ids = [c["id"] for c in cands]
    existing = set(
        (await session.execute(select(CandidateProfile.id).where(CandidateProfile.id.in_(ids))))
        .scalars()
        .all()
    )
    by_fsp: dict[str, list[dict[str, object]]] = defaultdict(list)
    for ach in fixtures.load("fsp_achievements"):
        by_fsp[ach["fsp_id"]].append(ach)

    linked = 0
    for cand in cands:
        if cand["id"] not in existing:
            continue
        fsp_id = cand["fsp_id"]
        await session.execute(
            delete(FspLink).where((FspLink.candidate_id == cand["id"]) | (FspLink.fsp_id == fsp_id))
        )
        fixture_ids = [a["id"] for a in by_fsp.get(fsp_id, [])]
        # id из фикстуры мог занять кэш другого участника (синхронизация до загрузки сида)
        await session.execute(
            delete(FspAchievement).where(
                (FspAchievement.fsp_id == fsp_id) | FspAchievement.id.in_(fixture_ids)
            )
        )
        await session.flush()
        session.add(
            FspLink(
                candidate_id=cand["id"],
                fsp_id=fsp_id,
                keycloak_sub=None,
                linked_at=datetime.fromisoformat(cand["created_at"]),
                last_sync_at=FIXTURE_SYNC_AT,
            )
        )
        for ordinal, ach in enumerate(by_fsp.get(fsp_id, []), start=1):
            session.add(
                FspAchievement(
                    id=ach["id"],
                    fsp_id=fsp_id,
                    external_id=external_id(fsp_id, ordinal),
                    competition=ach["competition"],
                    discipline=ach["discipline"],
                    level=ach["level"],
                    date=date.fromisoformat(str(ach["date"])),
                    place=ach["place"],
                    diploma=ach["diploma"],
                    team=ach["team"],
                    role=ach["role"],
                    rating=ach["rating"],
                    protocol_url=ach["protocol_url"],
                    verified=ach["verified"],
                    synced_at=FIXTURE_SYNC_AT,
                )
            )
        linked += 1
    await session.flush()
    await bump_sequences(session)
    await session.commit()
    return linked


async def bump_sequences(session: AsyncSession) -> None:
    """После вставки с явными id сдвинуть последовательности, иначе следующая вставка упадёт."""
    for table, model in (("fsp_achievements", FspAchievement), ("fsp_links", FspLink)):
        max_id = (await session.execute(select(func.max(model.id)))).scalar_one_or_none()
        if max_id:
            await session.execute(
                text("SELECT setval(pg_get_serial_sequence(:t, 'id'), :v)"),
                {"t": table, "v": max_id},
            )
