"""Логика модуля ФСП: привязка ФСП ID, синхронизация достижений с реестром, статус и сводки.

Данные — из БД (`fsp_links`, кэш `fsp_achievements`). Реестр — через `RegistryClient`.
Случай «нет истории ФСП» (T5.4) — не ошибка: нейтральный ответ без штрафа.
"""

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.fsp.models import FspAchievement, FspLink
from app.fsp.registry import (
    MAX_BATCH,
    ParticipantNotFoundError,
    RegistryClient,
    RegistryError,
    RegistryUnavailableError,
    get_registry_client,
    parse_updated_at,
)
from app.fsp.repository import FspRepository
from app.fsp.scoring import DIPLOMA_LABEL, FspSummary, summarize

logger = logging.getLogger("app.fsp")

NOT_LINKED = "Нет данных ФСП. Привяжите ФСП ID, если участвовали в соревнованиях."
NO_HISTORY_LINKED = "ФСП ID привязан, но в реестре пока нет достижений. Это не влияет на подбор."
NOT_SYNCED = (
    "ФСП ID привязан, но реестр ФСП сейчас недоступен. Достижения подтянутся позже — "
    "нажмите «Обновить»."
)
NOT_IN_REGISTRY = "Участник с этим ФСП ID не найден в реестре. Это не влияет на подбор."

# коды дисциплин реестра → коды платформы (app/common/enums.py FspDiscipline)
DISCIPLINE_FROM_REGISTRY = {
    "product": "product",
    "algorithmic": "algorithmic",
    "security": "cybersecurity",
    "cybersecurity": "cybersecurity",
    "uav": "uas",
    "uas": "uas",
    "robotics": "robotics",
}
WEBHOOK_EVENT_UPDATED = "participant.achievements_updated"


def utcnow() -> datetime:
    return datetime.now(UTC)


def registry_item_to_row(item: dict[str, Any], synced_at: datetime) -> dict[str, Any]:
    """Достижение из API реестра → строка кэша `fsp_achievements` (формат схемы FspAchievement)."""
    result = item.get("result") or {}
    team = item.get("team")
    competition = item.get("competition") or {}
    role = None
    if team:
        role = f"Капитан, {team['role']}" if team.get("is_captain") else team.get("role")
    kind = result.get("kind")
    degree = result.get("diploma_degree")
    discipline = (item.get("discipline") or {}).get("code", "product")
    return {
        "external_id": str(item["id"]),
        "competition": str(competition.get("title", ""))[:300],
        "discipline": DISCIPLINE_FROM_REGISTRY.get(discipline, "product"),
        "level": (item.get("level") or {}).get("code", "regional"),
        "date": date.fromisoformat(item["date"]),
        "place": result.get("place") if kind == "place" else None,
        "diploma": DIPLOMA_LABEL.get(degree or 0, "Диплом") if kind == "diploma" else None,
        "team": team.get("name") if team else None,
        "role": role[:100] if role else None,
        "rating": float(item["rating_points"]) if item.get("rating_points") is not None else None,
        "protocol_url": competition.get("protocol_url"),
        "verified": bool(item.get("verified", True)),
        "synced_at": synced_at,
    }


@dataclass
class SyncReport:
    """Итог пакетной синхронизации (ночное задание)."""

    checked: int = 0
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    not_found: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


class FspService:
    def __init__(self, session: AsyncSession, registry: RegistryClient | None = None) -> None:
        self.session = session
        self.repo = FspRepository(session)
        self._registry = registry

    @property
    def registry(self) -> RegistryClient:
        if self._registry is None:
            self._registry = get_registry_client()
        return self._registry

    # ------------------------------------------------------------ чтение

    async def status(self, candidate_id: int, message: str | None = None) -> dict[str, Any]:
        link = await self.repo.link_by_candidate(candidate_id)
        if link is None:
            return not_linked_status()
        achs = await self.repo.achievements(link.fsp_id)
        return self._status(link, achs, message)

    def _status(
        self, link: FspLink, achs: list[FspAchievement], message: str | None = None
    ) -> dict[str, Any]:
        summary = summarize(link.candidate_id, link.fsp_id, achs)
        if message is None and not achs:
            message = NO_HISTORY_LINKED if link.last_sync_at else NOT_SYNCED
        return {
            "linked": True,
            "fsp_id": link.fsp_id,
            "linked_at": link.linked_at,
            "last_sync_at": link.last_sync_at,
            "achievements_count": summary.achievements_count,
            "fsp_score": summary.fsp_score,
            "badges": summary.badges,
            "has_history": summary.has_history,
            "message": message,
        }

    async def achievements(self, candidate_id: int) -> list[FspAchievement]:
        link = await self.repo.link_by_candidate(candidate_id)
        if link is None:
            return []
        return await self.repo.achievements(link.fsp_id)

    async def login_user_id(self, fsp_id: str) -> int:
        """Пользователь, к профилю которого привязан ФСП ID; нет связи — 404."""
        link = await self.repo.link_by_fsp_id(fsp_id)
        user_id = await self.repo.candidate_user_id(link.candidate_id) if link else None
        if user_id is None:
            raise AppError(
                404,
                "fsp_account_not_linked",
                "Этот ФСП ID не привязан ни к одному профилю. Войдите по почте и паролю "
                "и привяжите ФСП ID в настройках.",
                {"fsp_id": fsp_id},
            )
        return user_id

    # ------------------------------------------------------------ привязка

    async def link(
        self, candidate_id: int, fsp_id: str, keycloak_sub: str | None = None
    ) -> dict[str, Any]:
        """Привязать ФСП ID к кандидату и сразу подтянуть достижения из реестра."""
        if await self.repo.candidate_user_id(candidate_id) is None:
            raise AppError(404, "not_found", "Профиль кандидата не найден", {"id": candidate_id})
        current = await self.repo.link_by_candidate(candidate_id)
        if current is not None and current.fsp_id != fsp_id:
            raise AppError(
                409,
                "fsp_already_linked",
                "К профилю уже привязан другой ФСП ID. Сначала отвяжите его.",
                {"fsp_id": current.fsp_id},
            )
        if current is None:
            other = await self.repo.link_by_fsp_id(fsp_id)
            if other is not None:
                raise fsp_id_taken(fsp_id)
            try:
                current = await self.repo.add_link(candidate_id, fsp_id, keycloak_sub, utcnow())
                await self.session.commit()
            except IntegrityError as exc:  # гонка двух привязок одного ID
                await self.session.rollback()
                raise fsp_id_taken(fsp_id) from exc
        message = await self._try_sync(current)
        return await self.status(candidate_id, message)

    async def unlink(self, candidate_id: int) -> dict[str, Any]:
        """Отвязать ФСП ID: связь и кэш достижений удаляются, профиль и вход не меняются."""
        link = await self.repo.link_by_candidate(candidate_id)
        if link is None:
            raise AppError(409, "fsp_not_linked", "ФСП ID не привязан")
        await self.repo.delete_achievements(link.fsp_id)
        await self.repo.delete_link(link)
        await self.session.commit()
        return not_linked_status()

    # ------------------------------------------------------------ синхронизация

    async def refresh(self, candidate_id: int) -> dict[str, Any]:
        """Кнопка «Обновить»: перечитать достижения из реестра. Реестр недоступен — 503."""
        link = await self.repo.link_by_candidate(candidate_id)
        if link is None:
            raise AppError(409, "fsp_not_linked", "ФСП ID не привязан")
        try:
            message = await self.sync_link(link)
        except RegistryError as exc:
            raise registry_app_error(exc) from exc
        return await self.status(candidate_id, message)

    async def _try_sync(self, link: FspLink) -> str | None:
        try:
            return await self.sync_link(link)
        except RegistryError as exc:
            logger.warning("Синхронизация %s не удалась: %s", link.fsp_id, exc)
            return NOT_SYNCED

    async def sync_link(self, link: FspLink) -> str | None:
        """Загрузить достижения участника в кэш. Возвращает сообщение для статуса или None."""
        now = utcnow()
        message = None
        try:
            data = await self.registry.achievements(link.fsp_id)
            items = data.get("items") or []
        except ParticipantNotFoundError:
            items, message = [], NOT_IN_REGISTRY
        await self.repo.replace_achievements(
            link.fsp_id, [registry_item_to_row(i, now) for i in items]
        )
        link.last_sync_at = now
        await self.session.commit()
        logger.info("ФСП %s: синхронизировано достижений — %d", link.fsp_id, len(items))
        return message

    async def sync_fsp_id(self, fsp_id: str) -> FspLink | None:
        """Пересинхронизировать участника по ФСП ID (вебхук). Не привязан — None."""
        link = await self.repo.link_by_fsp_id(fsp_id)
        if link is None:
            return None
        await self.sync_link(link)
        return link

    async def sync_many(
        self, fsp_ids: Iterable[str] | None = None, *, force: bool = False
    ) -> SyncReport:
        """Пакетное обновление (для ночного задания): `GET /participants?ids=` пачками по 100.

        Достижения перезапрашиваются, только если `updated_at` участника в реестре новее нашей
        последней синхронизации (или force). Участник пропал из реестра — кэш очищается.
        Недоступный реестр по одной пачке не роняет остальные: ID попадают в `failed`.
        """
        links = {link.fsp_id: link for link in await self.repo.all_links()}
        wanted = [i for i in (fsp_ids if fsp_ids is not None else links) if i in links]
        report = SyncReport()
        for start in range(0, len(wanted), MAX_BATCH):
            chunk = wanted[start : start + MAX_BATCH]
            try:
                batch = await self.registry.participants_batch(chunk)
            except RegistryError as exc:
                logger.warning("Пакет реестра ФСП не получен: %s", exc)
                report.failed.extend(chunk)
                continue
            report.checked += len(chunk)
            for fsp_id in batch.get("not_found") or []:
                if fsp_id in links:
                    await self.repo.delete_achievements(fsp_id)
                    links[fsp_id].last_sync_at = utcnow()
                    report.not_found.append(fsp_id)
            await self.session.commit()
            for item in batch.get("items") or []:
                link = links.get(item.get("fsp_id", ""))
                if link is None:
                    continue
                updated_at = parse_updated_at(item.get("updated_at"))
                stale = (
                    force
                    or link.last_sync_at is None
                    or updated_at is None
                    or updated_at > link.last_sync_at
                )
                if not stale:
                    report.unchanged.append(link.fsp_id)
                    continue
                try:
                    await self.sync_link(link)
                    report.updated.append(link.fsp_id)
                except RegistryError as exc:
                    logger.warning("ФСП %s не обновлён: %s", link.fsp_id, exc)
                    report.failed.append(link.fsp_id)
        return report


# ---------------------------------------------------------------- сводки для других модулей


async def fsp_summaries(
    session: AsyncSession, candidate_ids: Iterable[int], today: date | None = None
) -> dict[int, FspSummary]:
    """ФСП-сводка по списку кандидатов одним проходом по БД (профиль, выдача, ранжирование).

    Для каждого запрошенного id есть запись; без ФСП ID — нейтральная (linked=False,
    fsp_score=None). Вклад в ранжирование: `(summary.fsp_score or 0) / 100`.
    """
    ids = list(dict.fromkeys(candidate_ids))
    repo = FspRepository(session)
    links = {link.candidate_id: link for link in await repo.links_for_candidates(ids)}
    achs = await repo.achievements_by_fsp_ids(link.fsp_id for link in links.values())
    result: dict[int, FspSummary] = {}
    for cid in ids:
        link = links.get(cid)
        if link is None:
            result[cid] = summarize(cid, None, [])
        else:
            result[cid] = summarize(cid, link.fsp_id, achs.get(link.fsp_id, []), today)
    return result


async def fsp_id_for_candidate(session: AsyncSession, candidate_id: int) -> str | None:
    """ФСП ID кандидата из БД (для /api/auth/me и профиля)."""
    link = await FspRepository(session).link_by_candidate(candidate_id)
    return link.fsp_id if link else None


def not_linked_status() -> dict[str, Any]:
    return {
        "linked": False,
        "fsp_id": None,
        "linked_at": None,
        "last_sync_at": None,
        "achievements_count": 0,
        "fsp_score": None,
        "badges": [],
        "has_history": False,
        "message": NOT_LINKED,
    }


def fsp_id_taken(fsp_id: str) -> AppError:
    return AppError(
        409,
        "fsp_id_taken",
        "Этот ФСП ID уже привязан к другому профилю",
        {"fsp_id": fsp_id},
    )


def registry_app_error(exc: RegistryError) -> AppError:
    if isinstance(exc, RegistryUnavailableError):
        return AppError(
            503,
            "fsp_registry_unavailable",
            "Реестр ФСП временно недоступен, показаны сохранённые данные",
        )
    return AppError(502, exc.code, "Реестр ФСП ответил с ошибкой", {"status": exc.status})
