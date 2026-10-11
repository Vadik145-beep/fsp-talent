"""Компании и рекрутеры в БД (+ счётчики по приглашениям, откликам и жалобам)."""

from collections import Counter
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import Report
from app.candidates.models import CandidateProfile
from app.catalog.clock import as_msk
from app.common.enums import ACTIVE_INVITATION_STATUSES
from app.common.fixtures import Record
from app.companies.models import Company, Recruiter
from app.invitations.models import Invitation
from app.matching.models import Need
from app.users.models import User
from app.vacancies.models import Application, Vacancy


def company_record(c: Company) -> Record:
    return {
        "id": c.id,
        "name": c.name,
        "description": c.description,
        "industry": c.industry,
        "website": c.website,
        "city": c.city,
        "contact_email": c.contact_email,
        "contact_phone": c.contact_phone,
        "inn": c.inn,
        "verified_domain": c.verified_domain,
        "trust_score": c.trust_score,
        "blocked": c.blocked,
        "created_at": as_msk(c.created_at),
    }


class CompanyDb:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, company_id: int) -> Company | None:
        return await self.session.get(Company, company_id)

    async def all(self) -> list[Company]:
        return list((await self.session.scalars(select(Company).order_by(Company.id))).all())

    async def recruiter(self, recruiter_id: int) -> Recruiter | None:
        return await self.session.get(Recruiter, recruiter_id)

    async def recruiters(self, company_id: int) -> list[Record]:
        rows = (
            await self.session.execute(
                select(Recruiter, User)
                .join(User, User.id == Recruiter.user_id)
                .where(Recruiter.company_id == company_id)
                .order_by(Recruiter.id)
            )
        ).all()
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "company_id": r.company_id,
                "full_name": u.full_name,
                "position": r.position,
                "email": u.email,
                "phone": r.phone,
                "telegram": r.telegram,
                "is_company_admin": r.is_company_admin,
            }
            for r, u in rows
        ]

    async def recruiters_count(self) -> Counter[int]:
        rows = await self.session.execute(
            select(Recruiter.company_id, func.count()).group_by(Recruiter.company_id)
        )
        return Counter({cid: n for cid, n in rows})

    async def invitation_statuses(self, company_id: int | None = None) -> dict[int, Counter[str]]:
        """company_id → Counter статусов приглашений."""
        stmt = select(Invitation.company_id, Invitation.status, func.count()).group_by(
            Invitation.company_id, Invitation.status
        )
        if company_id is not None:
            stmt = stmt.where(Invitation.company_id == company_id)
        result: dict[int, Counter[str]] = {}
        for cid, status, n in await self.session.execute(stmt):
            result.setdefault(cid, Counter())[status] = n
        return result

    async def report_statuses(self) -> dict[int, Counter[str]]:
        result: dict[int, Counter[str]] = {}
        stmt = select(Report.company_id, Report.status, func.count()).group_by(
            Report.company_id, Report.status
        )
        for cid, status, n in await self.session.execute(stmt):
            result.setdefault(cid, Counter())[status] = n
        return result

    async def active_invitations_of(self, recruiter_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(Invitation)
            .where(
                Invitation.recruiter_id == recruiter_id,
                Invitation.status.in_([s.value for s in ACTIVE_INVITATION_STATUSES]),
            )
        )
        return int(await self.session.scalar(stmt) or 0)

    async def active_needs(self, company_id: int) -> list[Need]:
        rows = await self.session.scalars(
            select(Need)
            .where(Need.company_id == company_id, Need.status == "active")
            .order_by(Need.created_at.desc(), Need.id.desc())
        )
        return list(rows.all())

    async def applications(self, company_id: int) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                select(Application, Vacancy.title, CandidateProfile.pseudonym, User.full_name)
                .join(Vacancy, Vacancy.id == Application.vacancy_id)
                .join(CandidateProfile, CandidateProfile.id == Application.candidate_id)
                .join(User, User.id == CandidateProfile.user_id)
                .where(Vacancy.company_id == company_id)
                .order_by(Application.created_at.desc(), Application.id.desc())
            )
        ).all()
        return [
            {
                "id": a.id,
                "vacancy_id": a.vacancy_id,
                "vacancy_title": title,
                "candidate_pseudonym": pseudonym,
                # кандидат откликнулся сам — контакты и ФИО компании открыты
                "candidate_name": full_name,
                "status": a.status,
                "created_at": as_msk(a.created_at),
            }
            for a, title, pseudonym, full_name in rows
        ]
