"""Доступ к справочникам.

- `CatalogDb` — таблицы БД (async). Им пользуются справочники, профили, компании и админка.
- `CatalogRepository` — фикстуры `data/seed`; остаётся для модулей, которые ещё работают
  на фикстурах (matching, invitations, vacancies, tasks, testing — волна 3).
"""

from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import (
    Category,
    Grade,
    PlatformSetting,
    Skill,
    Specialization,
    Topic,
    skill_specializations,
)
from app.common import fixtures
from app.common.enums import SpecializationCode
from app.common.fixtures import Record

SPEC_ORDER = {code.value: i for i, code in enumerate(SpecializationCode)}


def _spec_key(code: str) -> int:
    return SPEC_ORDER.get(code, len(SPEC_ORDER))


class CatalogRepository:
    """Справочники из фикстур (для модулей на фикстурах)."""

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


class CatalogDb:
    """Справочники и настройки платформы в БД."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---------- чтение ----------

    @staticmethod
    def spec_record(row: Specialization) -> Record:
        return {
            "id": row.code,
            "label": row.label,
            "description": row.description,
            "active": row.active,
        }

    async def specializations(self) -> list[Record]:
        rows = (await self.session.scalars(select(Specialization))).all()
        return sorted((self.spec_record(r) for r in rows), key=lambda r: _spec_key(r["id"]))

    async def specialization(self, code: str) -> Specialization | None:
        return await self.session.get(Specialization, code)

    async def grades(self) -> list[Record]:
        rows = (await self.session.scalars(select(Grade).order_by(Grade.order))).all()
        return [{"id": r.code, "label": r.label, "order": r.order} for r in rows]

    async def grade(self, code: str) -> Grade | None:
        return await self.session.get(Grade, code)

    async def categories(self, specialization: str | None = None) -> list[Record]:
        stmt = select(Category, Grade.order).join(Grade, Grade.code == Category.grade)
        if specialization:
            stmt = stmt.where(Category.specialization == specialization)
        rows = (await self.session.execute(stmt)).all()
        rows = sorted(rows, key=lambda r: (_spec_key(r[0].specialization), r[1]))
        return [
            {
                "id": c.code,
                "specialization": c.specialization,
                "grade": c.grade,
                "label": c.label,
            }
            for c, _ in rows
        ]

    async def category(self, code: str) -> Category | None:
        return await self.session.get(Category, code)

    async def category_labels(self) -> dict[str, str]:
        rows = (await self.session.execute(select(Category.code, Category.label))).all()
        return {code: label for code, label in rows}

    async def topics(self, specialization: str | None = None) -> list[Record]:
        stmt = select(Topic)
        if specialization:
            stmt = stmt.where(Topic.specialization == specialization)
        rows = (await self.session.scalars(stmt)).all()
        rows = sorted(rows, key=lambda t: (_spec_key(t.specialization), t.code))
        return [{"id": t.code, "specialization": t.specialization, "label": t.label} for t in rows]

    async def topic(self, code: str) -> Topic | None:
        return await self.session.get(Topic, code)

    async def skills(self, specialization: str | None = None, q: str | None = None) -> list[Record]:
        links = (await self.session.execute(select(skill_specializations))).all()
        by_skill: dict[str, list[str]] = {}
        for skill_code, spec in links:
            by_skill.setdefault(skill_code, []).append(spec)
        rows = (await self.session.scalars(select(Skill).order_by(Skill.code))).all()
        items: list[Record] = [
            {
                "id": s.code,
                "label": s.label,
                "specializations": sorted(by_skill.get(s.code, []), key=_spec_key),
            }
            for s in rows
        ]
        if specialization:
            items = [s for s in items if specialization in s["specializations"]]
        if q:
            needle = q.lower()
            items = [s for s in items if needle in s["label"].lower() or needle in s["id"]]
        return items

    async def skill(self, code: str) -> Record | None:
        row = await self.session.get(Skill, code)
        if row is None:
            return None
        specs = (
            await self.session.scalars(
                select(skill_specializations.c.specialization).where(
                    skill_specializations.c.skill_code == code
                )
            )
        ).all()
        return {"id": row.code, "label": row.label, "specializations": sorted(specs, key=_spec_key)}

    async def existing_skill_codes(self, codes: list[str]) -> set[str]:
        if not codes:
            return set()
        rows = await self.session.scalars(select(Skill.code).where(Skill.code.in_(codes)))
        return set(rows.all())

    async def settings(self) -> Record:
        rows = (await self.session.scalars(select(PlatformSetting))).all()
        return {"id": "default", **{r.key: r.value for r in rows}}

    # ---------- запись ----------

    async def upsert_settings(self, values: dict[str, Any]) -> None:
        for key, value in values.items():
            row = await self.session.get(PlatformSetting, key)
            if row is None:
                self.session.add(PlatformSetting(key=key, value=value))
            else:
                row.value = value

    async def save_skill(self, code: str, label: str, specializations: list[str]) -> None:
        row = await self.session.get(Skill, code)
        if row is None:
            self.session.add(Skill(code=code, label=label))
        else:
            row.label = label
        await self.session.flush()
        await self.session.execute(
            delete(skill_specializations).where(skill_specializations.c.skill_code == code)
        )
        if specializations:
            await self.session.execute(
                insert(skill_specializations),
                [{"skill_code": code, "specialization": s} for s in dict.fromkeys(specializations)],
            )

    async def delete_skill(self, code: str) -> None:
        await self.session.execute(
            delete(skill_specializations).where(skill_specializations.c.skill_code == code)
        )
        await self.session.execute(delete(Skill).where(Skill.code == code))

    async def relabel_categories(self, *, specialization: str | None, grade: str | None) -> None:
        """Пересобрать подписи категорий «<специализация> · <грейд>» после смены подписи."""
        stmt = select(Category)
        if specialization:
            stmt = stmt.where(Category.specialization == specialization)
        if grade:
            stmt = stmt.where(Category.grade == grade)
        specs = {s.code: s.label for s in (await self.session.scalars(select(Specialization)))}
        grades = {g.code: g.label for g in (await self.session.scalars(select(Grade)))}
        for cat in (await self.session.scalars(stmt)).all():
            cat.label = f"{specs[cat.specialization]} · {grades[cat.grade]}"

    async def create_specialization(self, code: str, label: str, description: str) -> None:
        self.session.add(Specialization(code=code, label=label, description=description))
        await self.session.flush()
        grades = (await self.session.scalars(select(Grade))).all()
        for g in grades:
            self.session.add(
                Category(
                    code=f"{code}:{g.code}",
                    specialization=code,
                    grade=g.code,
                    label=f"{label} · {g.label}",
                )
            )

    async def delete_specialization(self, code: str) -> None:
        await self.session.execute(
            delete(skill_specializations).where(skill_specializations.c.specialization == code)
        )
        await self.session.execute(delete(Topic).where(Topic.specialization == code))
        await self.session.execute(delete(Category).where(Category.specialization == code))
        await self.session.execute(delete(Specialization).where(Specialization.code == code))

    async def update_topic(self, code: str, label: str) -> None:
        await self.session.execute(update(Topic).where(Topic.code == code).values(label=label))
