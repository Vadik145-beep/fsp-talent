"""Профиль компании, рекрутеры, дашборд рекрутера и скоринг надёжности компании."""

import secrets
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.audit import write_audit
from app.candidates.repository import CandidateDb
from app.catalog.repository import CatalogDb
from app.common.fixtures import Record
from app.companies.models import Company, Recruiter
from app.companies.repository import CompanyDb, company_record
from app.companies.schemas import CompanyUpdate
from app.core.errors import AppError, not_found
from app.core.security import CurrentUser

ANSWERED = ("accepted", "declined")
# Приглашения, по которым кандидат уже должен был ответить (активные и отозванные не считаем)
DECIDED = ("accepted", "declined", "expired")


def response_rate(statuses: Counter[str]) -> float:
    """Доля приглашений с ответом кандидата среди тех, где ответ уже мог быть."""
    decided = sum(statuses[s] for s in DECIDED)
    return round(sum(statuses[s] for s in ANSWERED) / decided, 2) if decided else 0.0


def trust_score(company: Company, statuses: Counter[str], reports: Counter[str]) -> float:
    """Скоринг надёжности компании 0..100 (антифрод, простая прозрачная формула).

    - база: 30 + 50 × доля отвеченных приглашений; нет данных по приглашениям — 50;
    - +10 за подтверждённый домен почты;
    - −15 за каждую подтверждённую жалобу (resolved), −5 за жалобу в работе (new/in_review);
      отклонённые жалобы не учитываются.
    """
    decided = sum(statuses[s] for s in DECIDED)
    score = 30 + 50 * response_rate(statuses) if decided else 50.0
    if company.verified_domain:
        score += 10
    score -= 15 * reports["resolved"] + 5 * (reports["new"] + reports["in_review"])
    return round(min(100.0, max(0.0, score)), 1)


class CompanyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.db = CompanyDb(session)

    async def _company_or_404(self, company_id: int) -> Company:
        company = await self.db.get(company_id)
        if company is None:
            raise not_found("company", company_id)
        return company

    async def scored_record(self, company: Company) -> Record:
        statuses = (await self.db.invitation_statuses(company.id)).get(company.id, Counter())
        reports = (await self.db.report_statuses()).get(company.id, Counter())
        record = company_record(company)
        record["trust_score"] = trust_score(company, statuses, reports)
        return record

    async def get_or_404(self, company_id: int) -> Record:
        return await self.scored_record(await self._company_or_404(company_id))

    async def _admin_of(self, company_id: int, user: CurrentUser) -> Recruiter | None:
        recruiter = await self.db.recruiter(user.recruiter_id) if user.recruiter_id else None
        if recruiter is None or recruiter.company_id != company_id:
            return None
        return recruiter if recruiter.is_company_admin else None

    async def _new_invite_code(self) -> str:
        """Тот же формат, что при регистрации компании (`app/auth/service.py`): 8 hex-символов."""
        while True:
            code = secrets.token_hex(4).upper()
            taken = await self.session.scalar(select(Company.id).where(Company.invite_code == code))
            if taken is None:
                return code

    async def my(self, company_id: int, user: CurrentUser, *, regenerate: bool = False) -> Record:
        """Профиль своей компании; администратору — с кодом приглашения рекрутеров.

        Кода нет (компания из демо-данных) — выпускаем при первом запросе администратора.
        """
        company = await self._company_or_404(company_id)
        record = await self.scored_record(company)
        if await self._admin_of(company_id, user) is None:
            if regenerate:
                raise AppError(
                    403, "forbidden", "Код приглашения меняет только администратор компании"
                )
            return record
        if company.invite_code is None or regenerate:
            company.invite_code = await self._new_invite_code()
            if regenerate:
                await write_audit(
                    self.session,
                    user,
                    "company_invite_code_changed",
                    "company",
                    company_id,
                    f"Выпущен новый код приглашения в компанию «{company.name}»",
                )
            await self.session.commit()
        record["invite_code"] = company.invite_code
        return record

    async def update(self, company_id: int, body: CompanyUpdate, user: CurrentUser) -> Record:
        company = await self._company_or_404(company_id)
        if await self._admin_of(company_id, user) is None:
            raise AppError(403, "forbidden", "Менять профиль может только администратор компании")
        for field, value in body.model_dump().items():
            setattr(company, field, value.strip() if isinstance(value, str) else value)
        await self.session.commit()
        return await self.my(company_id, user)

    async def recruiters(self, company_id: int) -> list[Record]:
        await self._company_or_404(company_id)
        return await self.db.recruiters(company_id)

    async def quota(self, recruiter_id: int) -> dict[str, int]:
        limit = int((await CatalogDb(self.session).settings()).get("invitation_quota", 20))
        used = await self.db.active_invitations_of(recruiter_id)
        return {"limit": limit, "used": used, "left": max(limit - used, 0)}

    async def dashboard(self, company_id: int, recruiter_id: int) -> dict[str, Any]:
        company = await self._company_or_404(company_id)
        candidates = CandidateDb(self.session)
        needs = [
            {
                "id": n.id,
                "title": n.title,
                "category": n.category,
                "candidates_count": await candidates.count_searchable_in_category(n.category),
            }
            for n in await self.db.active_needs(company_id)
        ]
        statuses = (await self.db.invitation_statuses(company_id)).get(company_id, Counter())
        new_apps = [a for a in await self.db.applications(company_id) if a["status"] == "new"]
        return {
            "company_name": company.name,
            "active_needs": needs,
            "invitations_by_status": dict(statuses),
            "quota": await self.quota(recruiter_id),
            "new_applications_count": len(new_apps),
            "recent_applications": new_apps[:5],
        }
