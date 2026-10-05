"""Статус привязки ФСП ID и достижения (кэш реестра). Синхронизация с моком реестра — волна 2c."""

from typing import Any

from app.common.fixtures import Record
from app.core.errors import not_found
from app.fsp.repository import FspRepository

NO_HISTORY_LINKED = "ФСП ID привязан, но в реестре пока нет достижений. Это не влияет на подбор."
NOT_LINKED = "Нет данных ФСП. Привяжите ФСП ID, если участвовали в соревнованиях."


class FspService:
    def __init__(self, repo: FspRepository | None = None) -> None:
        self.repo = repo or FspRepository()

    def _candidate(self, candidate_id: int) -> Record:
        cand = self.repo.candidate(candidate_id)
        if cand is None:
            raise not_found("candidate", candidate_id)
        return cand

    def achievements(self, candidate_id: int) -> list[Record]:
        fsp_id = self._candidate(candidate_id).get("fsp_id")
        if not fsp_id:
            return []
        return sorted(self.repo.achievements(fsp_id), key=lambda a: a["date"], reverse=True)

    def status(self, candidate_id: int, *, fsp_id_override: str | None = None) -> dict[str, Any]:
        cand = self._candidate(candidate_id)
        fsp_id = fsp_id_override or cand.get("fsp_id")
        if not fsp_id:
            return {"linked": False, "has_history": False, "message": NOT_LINKED}
        achs = self.repo.achievements(fsp_id)
        linked_at = cand["created_at"]
        return {
            "linked": True,
            "fsp_id": fsp_id,
            "linked_at": linked_at,
            "last_sync_at": cand.get("last_test_at") or linked_at,
            "achievements_count": len(achs),
            "fsp_score": cand.get("fsp_score"),
            "badges": cand.get("fsp_badges", []),
            "has_history": bool(achs),
            "message": None if achs else NO_HISTORY_LINKED,
        }

    def unlinked(self) -> dict[str, Any]:
        return {"linked": False, "has_history": False, "message": NOT_LINKED}
