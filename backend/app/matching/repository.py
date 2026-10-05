"""Потребности работодателя. До волны 3b — фикстуры `needs.json`."""

from app.common import fixtures
from app.common.fixtures import Record


class NeedRepository:
    def by_company(self, company_id: int) -> list[Record]:
        return fixtures.where("needs", company_id=company_id)

    def get(self, need_id: int) -> Record | None:
        return fixtures.by_id("needs", need_id)

    def next_id(self) -> int:
        return max((int(n["id"]) for n in fixtures.load("needs")), default=0) + 1

    def skills(self) -> list[Record]:
        return fixtures.all_records("skills")
