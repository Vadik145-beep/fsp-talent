"""Кэш достижений ФСП. До волны 2 — фикстуры `fsp_achievements.json`."""

from app.common import fixtures
from app.common.fixtures import Record


class FspRepository:
    def achievements(self, fsp_id: str) -> list[Record]:
        return fixtures.where("fsp_achievements", fsp_id=fsp_id)

    def candidate(self, candidate_id: int) -> Record | None:
        return fixtures.by_id("candidates", candidate_id)
