"""Справочники: фильтрация и подписи."""

from app.catalog.repository import CatalogRepository
from app.common.enums import SpecializationCode
from app.common.fixtures import Record


class CatalogService:
    def __init__(self, repo: CatalogRepository | None = None) -> None:
        self.repo = repo or CatalogRepository()

    def specializations(self) -> list[Record]:
        return self.repo.specializations()

    def grades(self) -> list[Record]:
        return self.repo.grades()

    def categories(self, specialization: SpecializationCode | None = None) -> list[Record]:
        items = self.repo.categories()
        if specialization:
            items = [c for c in items if c["specialization"] == specialization]
        return items

    def topics(self, specialization: SpecializationCode | None = None) -> list[Record]:
        items = self.repo.topics()
        if specialization:
            items = [t for t in items if t["specialization"] == specialization]
        return items

    def skills(
        self, specialization: SpecializationCode | None = None, q: str | None = None
    ) -> list[Record]:
        items = self.repo.skills()
        if specialization:
            items = [s for s in items if specialization in s["specializations"]]
        if q:
            needle = q.lower()
            items = [s for s in items if needle in s["label"].lower() or needle in s["id"]]
        return items

    def decline_reasons(self) -> list[Record]:
        return self.repo.decline_reasons()

    def category_label(self, category_id: str) -> str:
        cat = self.repo.category(category_id)
        return str(cat["label"]) if cat else category_id
