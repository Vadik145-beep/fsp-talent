"""Вакансии и отклики (БД). Выборки пакетные (без N+1), коммит — за сервисом."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.catalog.models import Category
from app.companies.models import Company, Recruiter
from app.users.models import User
from app.vacancies.models import Application, Vacancy

# Строка выборки вакансии: вакансия + название компании + подпись категории
VacancyRow = tuple[Vacancy, str, str | None]
# Строка выборки отклика: отклик + вакансия + название компании
ApplicationRow = tuple[Application, Vacancy, str]


class VacancyDb:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---------- вакансии ----------

    def _select(self) -> Any:
        return (
            select(Vacancy, Company.name, Category.label)
            .join(Company, Company.id == Vacancy.company_id)
            .outerjoin(Category, Category.code == Vacancy.category)
        )

    async def rows(
        self,
        conditions: Sequence[ColumnElement[bool]],
        order_by: Sequence[Any],
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[VacancyRow]:
        stmt = self._select().where(*conditions).order_by(*order_by).offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        return [(r[0], r[1], r[2]) for r in (await self.session.execute(stmt)).all()]

    async def count(self, conditions: Sequence[ColumnElement[bool]]) -> int:
        stmt = (
            select(func.count())
            .select_from(Vacancy)
            .join(Company, Company.id == Vacancy.company_id)
            .where(*conditions)
        )
        return int(await self.session.scalar(stmt) or 0)

    async def row(self, vacancy_id: int) -> VacancyRow | None:
        rows = await self.rows([Vacancy.id == vacancy_id], [Vacancy.id])
        return rows[0] if rows else None

    async def get(self, vacancy_id: int) -> Vacancy | None:
        return await self.session.get(Vacancy, vacancy_id)

    async def company(self, company_id: int) -> Company | None:
        return await self.session.get(Company, company_id)

    async def applications_count(self, vacancy_ids: Sequence[int]) -> dict[int, int]:
        """Число откликов по вакансиям — один запрос."""
        if not vacancy_ids:
            return {}
        rows = (
            await self.session.execute(
                select(Application.vacancy_id, func.count())
                .where(Application.vacancy_id.in_(list(vacancy_ids)))
                .group_by(Application.vacancy_id)
            )
        ).all()
        return {vid: int(n) for vid, n in rows}

    async def my_applications(
        self, candidate_id: int, vacancy_ids: Sequence[int]
    ) -> dict[int, int]:
        """id отклика кандидата по вакансиям (vacancy_id → application_id) — один запрос."""
        if not vacancy_ids:
            return {}
        rows = (
            await self.session.execute(
                select(Application.vacancy_id, Application.id).where(
                    Application.candidate_id == candidate_id,
                    Application.vacancy_id.in_(list(vacancy_ids)),
                )
            )
        ).all()
        return {vid: aid for vid, aid in rows}

    # ---------- отклики ----------

    def _app_select(self) -> Any:
        return (
            select(Application, Vacancy, Company.name)
            .join(Vacancy, Vacancy.id == Application.vacancy_id)
            .join(Company, Company.id == Vacancy.company_id)
        )

    async def application_rows(self, *conditions: ColumnElement[bool]) -> list[ApplicationRow]:
        stmt = (
            self._app_select()
            .where(*conditions)
            .order_by(Application.created_at.desc(), Application.id.desc())
        )
        return [(r[0], r[1], r[2]) for r in (await self.session.execute(stmt)).all()]

    async def application_row(self, application_id: int) -> ApplicationRow | None:
        rows = await self.application_rows(Application.id == application_id)
        return rows[0] if rows else None

    async def application_of(self, vacancy_id: int, candidate_id: int) -> Application | None:
        rows = await self.session.scalars(
            select(Application).where(
                Application.vacancy_id == vacancy_id, Application.candidate_id == candidate_id
            )
        )
        return rows.first()

    async def recruiter_emails(self, company_id: int) -> list[str]:
        """Почта рекрутеров компании (не заблокированных) — для писем о новых откликах."""
        rows = await self.session.scalars(
            select(User.email)
            .join(Recruiter, Recruiter.user_id == User.id)
            .where(Recruiter.company_id == company_id, User.blocked.is_(False))
            .order_by(Recruiter.id)
        )
        return [str(e) for e in rows.all() if e]
