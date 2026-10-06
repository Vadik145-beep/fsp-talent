"""Справочники: чтение, изменение (админка, T10.3) и запреты на удаление используемых записей."""

from typing import Any

from sqlalchemy import ColumnElement, any_, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates.models import CandidateProfile, candidate_skills
from app.catalog.models import Topic
from app.catalog.repository import CatalogDb, CatalogRepository
from app.common.fixtures import Record
from app.core.errors import AppError, not_found
from app.invitations.models import Invitation
from app.matching.models import Need
from app.tasks.models import RegularTask
from app.testing.engine.grading import GradeThresholds
from app.testing.models import GradeHistory, Item, TestSession
from app.vacancies.models import Vacancy


class CatalogService:
    """Причины отказа — фиксированный справочник (enum), отдаётся из фикстуры."""

    def __init__(self, repo: CatalogRepository | None = None) -> None:
        self.repo = repo or CatalogRepository()

    def decline_reasons(self) -> list[Record]:
        return self.repo.decline_reasons()


async def _count(session: AsyncSession, model: Any, condition: ColumnElement[bool]) -> int:
    return int(await session.scalar(select(func.count()).select_from(model).where(condition)) or 0)


class CatalogDbService:
    """Справочники в БД: публичное чтение и изменения из админки."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.db = CatalogDb(session)

    # ---------- чтение ----------

    async def specializations(self) -> list[Record]:
        return await self.db.specializations()

    async def grades(self) -> list[Record]:
        return await self.db.grades()

    async def categories(self, specialization: str | None = None) -> list[Record]:
        return await self.db.categories(specialization)

    async def topics(self, specialization: str | None = None) -> list[Record]:
        return await self.db.topics(specialization)

    async def skills(self, specialization: str | None = None, q: str | None = None) -> list[Record]:
        return await self.db.skills(specialization, q)

    async def settings(self) -> Record:
        return await self.db.settings()

    # ---------- специализации ----------

    async def _spec_or_404(self, code: str) -> Any:
        spec = await self.db.specialization(code)
        if spec is None:
            raise not_found("specialization", code)
        return spec

    async def specialization_usage(self, code: str) -> dict[str, int]:
        prefix = f"{code}:%"
        usage = {
            "candidates": await _count(
                self.session, CandidateProfile, CandidateProfile.specialization == code
            ),
            "vacancies": await _count(self.session, Vacancy, Vacancy.specialization == code),
            "needs": await _count(self.session, Need, Need.specialization == code),
            "items": await _count(self.session, Item, Item.specialization == code),
            "test_sessions": await _count(
                self.session, TestSession, TestSession.specialization == code
            ),
            "grade_history": await _count(
                self.session, GradeHistory, GradeHistory.specialization == code
            ),
            "invitations": await _count(self.session, Invitation, Invitation.category.like(prefix)),
            "regular_tasks": await _count(
                self.session, RegularTask, RegularTask.category.like(prefix)
            ),
        }
        return {k: v for k, v in usage.items() if v}

    async def create_specialization(self, code: str, label: str, description: str) -> Record:
        if await self.db.specialization(code) is not None:
            raise AppError(
                409, "specialization_exists", "Такая специализация уже есть", {"id": code}
            )
        await self.db.create_specialization(code, label, description)
        await self.session.flush()
        return self.db.spec_record(await self._spec_or_404(code))

    async def update_specialization(
        self, code: str, label: str, description: str | None, active: bool | None
    ) -> Record:
        spec = await self._spec_or_404(code)
        spec.label = label
        if description is not None:
            spec.description = description
        if active is not None:
            spec.active = active
        await self.session.flush()
        await self.db.relabel_categories(specialization=code, grade=None)
        return self.db.spec_record(spec)

    async def delete_specialization(self, code: str) -> Record:
        spec = await self._spec_or_404(code)
        usage = await self.specialization_usage(code)
        if usage:
            raise AppError(
                409,
                "specialization_in_use",
                "Специализация используется: есть кандидаты, вакансии или задачи. "
                "Её можно скрыть (active = false), но не удалить",
                {"id": code, "usage": usage},
            )
        record = self.db.spec_record(spec)
        await self.db.delete_specialization(code)
        return record

    # ---------- грейды и категории ----------

    async def update_grade(self, code: str, label: str) -> Record:
        grade = await self.db.grade(code)
        if grade is None:
            raise not_found("grade", code)
        grade.label = label
        await self.session.flush()
        await self.db.relabel_categories(specialization=None, grade=code)
        return {"id": grade.code, "label": grade.label, "order": grade.order}

    async def update_category(self, code: str, label: str) -> Record:
        cat = await self.db.category(code)
        if cat is None:
            raise not_found("category", code)
        cat.label = label
        await self.session.flush()
        return {
            "id": cat.code,
            "specialization": cat.specialization,
            "grade": cat.grade,
            "label": cat.label,
        }

    # ---------- темы ----------

    async def create_topic(self, code: str, specialization: str, label: str) -> Record:
        await self._spec_or_404(specialization)
        if not code.startswith(f"{specialization}."):
            raise AppError(
                422,
                "topic_code_invalid",
                "Код темы начинается с кода специализации: <специализация>.<тема>",
                {"id": code, "specialization": specialization},
            )
        if await self.db.topic(code) is not None:
            raise AppError(409, "topic_exists", "Такая тема уже есть", {"id": code})
        self.session.add(Topic(code=code, specialization=specialization, label=label))
        await self.session.flush()
        return {"id": code, "specialization": specialization, "label": label}

    async def update_topic(self, code: str, label: str) -> Record:
        topic = await self.db.topic(code)
        if topic is None:
            raise not_found("topic", code)
        topic.label = label
        await self.session.flush()
        return {"id": topic.code, "specialization": topic.specialization, "label": topic.label}

    async def delete_topic(self, code: str) -> Record:
        topic = await self.db.topic(code)
        if topic is None:
            raise not_found("topic", code)
        items = await _count(self.session, Item, Item.topic == code)
        if items:
            raise AppError(
                409,
                "topic_in_use",
                "По теме есть шаблоны задач — сначала перенесите или выведите их",
                {"id": code, "usage": {"items": items}},
            )
        record = {"id": topic.code, "specialization": topic.specialization, "label": topic.label}
        await self.session.delete(topic)
        await self.session.flush()
        return record

    # ---------- стек ----------

    async def _check_specs(self, specializations: list[str]) -> None:
        known = {s["id"] for s in await self.db.specializations()}
        unknown = [s for s in specializations if s not in known]
        if unknown:
            raise AppError(
                422,
                "unknown_specialization",
                "Нет такой специализации в справочнике",
                {"specializations": unknown},
            )

    async def create_skill(self, code: str, label: str, specializations: list[str]) -> Record:
        if await self.db.skill(code) is not None:
            raise AppError(409, "skill_exists", "Такая технология уже есть", {"id": code})
        await self._check_specs(specializations)
        await self.db.save_skill(code, label, specializations)
        await self.session.flush()
        return await self.db.skill(code) or {}

    async def update_skill(self, code: str, label: str, specializations: list[str]) -> Record:
        if await self.db.skill(code) is None:
            raise not_found("skill", code)
        await self._check_specs(specializations)
        await self.db.save_skill(code, label, specializations)
        await self.session.flush()
        return await self.db.skill(code) or {}

    async def skill_usage(self, code: str) -> dict[str, int]:
        usage = {
            "candidates": await _count(
                self.session, candidate_skills, candidate_skills.c.skill_code == code
            ),
            "vacancies": await _count(
                self.session,
                Vacancy,
                or_(
                    literal(code) == any_(Vacancy.skills_required),
                    literal(code) == any_(Vacancy.skills_desired),
                ),
            ),
            "needs": await _count(
                self.session,
                Need,
                or_(
                    literal(code) == any_(Need.skills_required),
                    literal(code) == any_(Need.skills_desired),
                ),
            ),
        }
        return {k: v for k, v in usage.items() if v}

    async def delete_skill(self, code: str) -> Record:
        record = await self.db.skill(code)
        if record is None:
            raise not_found("skill", code)
        usage = await self.skill_usage(code)
        if usage:
            raise AppError(
                409,
                "skill_in_use",
                "Технология используется в профилях, вакансиях или потребностях",
                {"id": code, "usage": usage},
            )
        await self.db.delete_skill(code)
        return record

    # ---------- настройки ----------

    async def update_settings(self, changes: dict[str, Any]) -> tuple[Record, Record]:
        """Применить изменения настроек. Возвращает (было, стало) по изменённым ключам."""
        current = await self.db.settings()
        thresholds = changes.get("grade_thresholds")
        if thresholds is not None:
            seen: set[str] = set()
            for row in thresholds:
                spec = row["specialization"]
                if spec in seen:
                    raise AppError(
                        422,
                        "invalid_thresholds",
                        "Специализация указана в порогах дважды",
                        {"specialization": spec},
                    )
                seen.add(spec)
                try:
                    GradeThresholds(row["junior_from"], row["middle_from"], row["senior_from"])
                except ValueError as exc:
                    raise AppError(
                        422,
                        "invalid_thresholds",
                        "Пороги θ должны возрастать: junior < middle < senior",
                        {"specialization": spec},
                    ) from exc
        weights = changes.get("ranking_weights")
        if weights is not None and sum(weights.values()) <= 0:
            raise AppError(
                422, "invalid_weights", "Хотя бы один вес ранжирования должен быть больше нуля"
            )
        before = {k: current.get(k) for k in changes}
        changed = {k: v for k, v in changes.items() if current.get(k) != v}
        await self.db.upsert_settings(changed)
        await self.session.flush()
        return before, changed
