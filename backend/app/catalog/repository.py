"""Доступ к справочникам. До волны 2 — фикстуры `data/seed`, затем — таблицы БД."""

from app.common import fixtures
from app.common.fixtures import Record


class CatalogRepository:
    def specializations(self) -> list[Record]:
        return fixtures.all_records("specializations")

    def grades(self) -> list[Record]:
        return fixtures.all_records("grades")

    def categories(self) -> list[Record]:
        return fixtures.all_records("categories")

    def topics(self) -> list[Record]:
        return fixtures.all_records("topics")

    def skills(self) -> list[Record]:
        return fixtures.all_records("skills")

    def decline_reasons(self) -> list[Record]:
        return fixtures.all_records("decline_reasons")

    def category(self, category_id: str) -> Record | None:
        return fixtures.by_id("categories", category_id)

    def platform_settings(self) -> Record:
        return fixtures.by_id("platform_settings", "default") or {}
