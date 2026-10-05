"""Профиль компании и дашборд рекрутера."""

from collections import Counter
from typing import Any

from app.candidates.service import CandidateService
from app.common.enums import ApplicationStatus, NeedStatus
from app.common.fixtures import Record
from app.companies.repository import CompanyRepository
from app.core.errors import not_found
from app.invitations.service import InvitationService


class CompanyService:
    def __init__(
        self,
        repo: CompanyRepository | None = None,
        invitations: InvitationService | None = None,
        candidates: CandidateService | None = None,
    ) -> None:
        self.repo = repo or CompanyRepository()
        self.invitations = invitations or InvitationService()
        self.candidates = candidates or CandidateService()

    def get_or_404(self, company_id: int) -> Record:
        company = self.repo.get(company_id)
        if company is None:
            raise not_found("company", company_id)
        return company

    def dashboard(self, company_id: int, recruiter_id: int) -> dict[str, Any]:
        company = self.get_or_404(company_id)
        needs = [n for n in self.repo.needs(company_id) if n["status"] == NeedStatus.active]
        by_status = Counter(i["status"] for i in self.repo.invitations(company_id))
        apps = sorted(
            self.repo.applications(company_id), key=lambda a: a["created_at"], reverse=True
        )
        new_apps = [a for a in apps if a["status"] == ApplicationStatus.new]
        recent = []
        for app in new_apps[:5]:
            cand = self.candidates.repo.get(app["candidate_id"]) or {}
            recent.append(
                {
                    "id": app["id"],
                    "vacancy_id": app["vacancy_id"],
                    "vacancy_title": app["vacancy_title"],
                    "candidate_pseudonym": cand.get("pseudonym", ""),
                    "created_at": app["created_at"],
                }
            )
        quota = self.invitations.quota(recruiter_id)
        quota.pop("hint", None)
        return {
            "company_name": company["name"],
            "active_needs": needs,
            "invitations_by_status": dict(by_status),
            "quota": quota,
            "new_applications_count": len(new_apps),
            "recent_applications": recent,
        }
