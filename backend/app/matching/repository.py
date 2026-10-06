"""Потребности работодателя и пакетная загрузка кандидатов для подборки (БД).

Все выборки пакетные: профили одним запросом, стек одним запросом, ФСП — `fsp_summaries`
(один проход), статусы приглашений компании — одним запросом. Без N+1.
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates.models import CandidateProfile
from app.candidates.repository import CandidateDb, searchable_conditions
from app.catalog.clock import as_msk
from app.catalog.models import Category, Skill
from app.common.fixtures import Record
from app.fsp.scoring import FspSummary
from app.fsp.service import fsp_summaries
from app.invitations.models import Invitation
from app.matching.models import Need
from app.users.models import User


class NeedDb:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def by_company(self, company_id: int) -> list[Need]:
        rows = await self.session.scalars(
            select(Need)
            .where(Need.company_id == company_id)
            .order_by(Need.created_at.desc(), Need.id.desc())
        )
        return list(rows.all())

    async def get(self, need_id: int) -> Need | None:
        return await self.session.get(Need, need_id)


class CandidatePool:
    """Кандидаты для подборки и приглашений: только пакетные запросы."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def searchable_ids(self, category: str) -> list[int]:
        """Кандидаты в выдаче (грейд, согласие, поиск не на паузе, не заблокирован)."""
        stmt = (
            select(CandidateProfile.id)
            .join(User, User.id == CandidateProfile.user_id)
            .where(*searchable_conditions(), CandidateProfile.category == category)
            .order_by(CandidateProfile.id)
        )
        return list((await self.session.scalars(stmt)).all())

    async def is_searchable(self, candidate_id: int) -> bool:
        stmt = (
            select(CandidateProfile.id)
            .join(User, User.id == CandidateProfile.user_id)
            .where(*searchable_conditions(), CandidateProfile.id == candidate_id)
        )
        return (await self.session.scalar(stmt)) is not None

    async def counts(self, categories: Sequence[str]) -> dict[str, int]:
        """Число кандидатов в выдаче по категориям — один запрос."""
        result = dict.fromkeys(categories, 0)
        if not categories:
            return result
        stmt = (
            select(CandidateProfile.category, func.count())
            .join(User, User.id == CandidateProfile.user_id)
            .where(*searchable_conditions(), CandidateProfile.category.in_(list(categories)))
            .group_by(CandidateProfile.category)
        )
        for category, count in (await self.session.execute(stmt)).all():
            result[category] = int(count)
        return result

    async def records(self, ids: Sequence[int]) -> dict[int, Record]:
        """Записи профилей (поля карточки, счёта и контактов) с ФСП из `fsp_summaries`."""
        if not ids:
            return {}
        rows = (
            await self.session.execute(
                select(CandidateProfile, User.full_name, User.email, User.blocked, Category.label)
                .join(User, User.id == CandidateProfile.user_id)
                .outerjoin(Category, Category.code == CandidateProfile.category)
                .where(CandidateProfile.id.in_(list(ids)))
            )
        ).all()
        stacks = await CandidateDb(self.session).stacks(list(ids))
        fsp = await fsp_summaries(self.session, ids)
        result: dict[int, Record] = {}
        for p, full_name, email, blocked, category_label in rows:
            summary: FspSummary | None = fsp.get(p.id)
            result[p.id] = {
                "id": p.id,
                "user_id": p.user_id,
                "pseudonym": p.pseudonym,
                "full_name": full_name,
                "email": email,
                "phone": p.phone,
                "telegram": p.telegram,
                "city": p.city,
                "work_formats": list(p.work_formats or []),
                "specialization": p.specialization,
                "grade": p.grade,
                "category": p.category,
                "category_label": category_label,
                "theta": p.theta,
                "topic_scores": list(p.topic_scores or []),
                "stack": stacks.get(p.id, []),
                "roles_in_team": list(p.roles_in_team or []),
                "experience_years": p.experience_years,
                "links": list(p.links or []),
                "min_salary": p.min_salary,
                "fsp_id": summary.fsp_id if summary else None,
                "fsp_score": summary.fsp_score if summary else None,
                "fsp_badges": list(summary.badges) if summary else [],
                "fsp_reason": summary.reason if summary else None,
                "privacy": dict(p.privacy or {}),
                "job_search_paused": p.job_search_paused,
                "publication_consent": p.publication_consent,
                "freshness": p.freshness,
                "blocked": blocked,
                "last_test_at": as_msk(p.last_test_at),
            }
        return result

    async def last_invitation_status(self, company_id: int, ids: Sequence[int]) -> dict[int, str]:
        """Статус последнего приглашения компании каждому кандидату — один запрос."""
        if not ids:
            return {}
        stmt = (
            select(Invitation.candidate_id, Invitation.status)
            .where(Invitation.company_id == company_id, Invitation.candidate_id.in_(list(ids)))
            .distinct(Invitation.candidate_id)
            .order_by(Invitation.candidate_id, Invitation.created_at.desc(), Invitation.id.desc())
        )
        return {cid: status for cid, status in (await self.session.execute(stmt)).all()}


async def skill_labels(session: AsyncSession) -> dict[str, str]:
    rows = (await session.execute(select(Skill.code, Skill.label))).all()
    return {code: label for code, label in rows}


async def category_labels(session: AsyncSession, codes: Sequence[str]) -> dict[str, str]:
    if not codes:
        return {}
    rows = (
        await session.execute(
            select(Category.code, Category.label).where(Category.code.in_(list(codes)))
        )
    ).all()
    return {code: label for code, label in rows}


def need_record(n: Need, category_label: str, candidates_count: int) -> dict[str, Any]:
    return {
        "id": n.id,
        "company_id": n.company_id,
        "recruiter_id": n.recruiter_id,
        "title": n.title,
        "raw_text": n.raw_text,
        "specialization": n.specialization,
        "grade": n.grade,
        "skills_required": list(n.skills_required or []),
        "skills_desired": list(n.skills_desired or []),
        "team_description": n.team_description or "",
        "work_format": n.work_format,
        "city": n.city,
        "salary_from": n.salary_from,
        "salary_to": n.salary_to,
        "category": n.category,
        "category_label": category_label,
        "status": n.status,
        "candidates_count": candidates_count,
        "created_at": as_msk(n.created_at),
    }
