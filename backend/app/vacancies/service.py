"""Вакансии и отклики: лента, CRUD своей компании, отклик, статусы. Заглушки до волны 5a."""

from datetime import datetime
from typing import Any

from app.candidates.service import CandidateService, to_card, to_contacts
from app.catalog.repository import CatalogRepository
from app.common.enums import ApplicationStatus, Role, VacancyStatus
from app.common.fixtures import Record
from app.core.errors import AppError, not_found
from app.core.security import CurrentUser
from app.vacancies.repository import VacancyRepository
from app.vacancies.schemas import VacancyCreate


def _now() -> str:
    return datetime.now().astimezone().isoformat()


class VacancyService:
    def __init__(
        self,
        repo: VacancyRepository | None = None,
        candidates: CandidateService | None = None,
        catalog: CatalogRepository | None = None,
    ) -> None:
        self.repo = repo or VacancyRepository()
        self.candidates = candidates or CandidateService()
        self.catalog = catalog or CatalogRepository()

    # ---------- вакансии ----------

    def _for_candidate(self, vacancy: Record, candidate_id: int | None) -> dict[str, Any]:
        data = dict(vacancy)
        data["my_application_id"] = next(
            (
                a["id"]
                for a in self.repo.applications()
                if a["vacancy_id"] == vacancy["id"] and a["candidate_id"] == candidate_id
            ),
            None,
        )
        return data

    def list_for(
        self,
        user: CurrentUser,
        *,
        specialization: str | None = None,
        grade: str | None = None,
        work_format: str | None = None,
        skills: list[str] | None = None,
        salary_min: int | None = None,
        q: str | None = None,
    ) -> list[dict[str, Any]]:
        if user.role == Role.recruiter:
            items = [v for v in self.repo.all() if v["company_id"] == user.company_id]
        else:
            items = [v for v in self.repo.all() if v["status"] == VacancyStatus.published]
        if specialization:
            items = [v for v in items if v["specialization"] == specialization]
        if grade:
            items = [v for v in items if v["grade"] == grade]
        if work_format:
            items = [v for v in items if v["work_format"] == work_format]
        if skills:
            items = [
                v for v in items if set(skills) & set(v["skills_required"] + v["skills_desired"])
            ]
        if salary_min:
            items = [v for v in items if v["salary_to"] >= salary_min]
        if q:
            needle = q.lower()
            items = [v for v in items if needle in (v["title"] + v["description"]).lower()]
        items.sort(key=lambda v: v.get("published_at") or v["created_at"], reverse=True)
        if user.role == Role.candidate:
            return [self._for_candidate(v, user.candidate_id) for v in items]
        return [dict(v) for v in items]

    def get(self, vacancy_id: int, user: CurrentUser) -> dict[str, Any]:
        vacancy = self.repo.get(vacancy_id)
        if vacancy is None:
            raise not_found("vacancy", vacancy_id)
        if user.role == Role.recruiter:
            if vacancy["company_id"] != user.company_id:
                raise not_found("vacancy", vacancy_id)
            return dict(vacancy)
        if vacancy["status"] != VacancyStatus.published:
            raise not_found("vacancy", vacancy_id)
        return self._for_candidate(vacancy, user.candidate_id)

    def create(self, body: VacancyCreate, user: CurrentUser) -> dict[str, Any]:
        assert user.company_id is not None
        category = f"{body.specialization}:{body.grade}"
        cat = self.catalog.category(category) or {"label": category}
        company = self.repo.company(user.company_id) or {}
        return {
            **body.model_dump(),
            "id": self.repo.next_id(),
            "company_id": user.company_id,
            "company_name": company.get("name", ""),
            "category": category,
            "category_label": cat["label"],
            "status": VacancyStatus.draft,
            "applications_count": 0,
            "created_at": _now(),
            "published_at": None,
        }

    def update(self, vacancy_id: int, body: VacancyCreate, user: CurrentUser) -> dict[str, Any]:
        vacancy = self.get(vacancy_id, user)
        category = f"{body.specialization}:{body.grade}"
        cat = self.catalog.category(category) or {"label": category}
        vacancy.update(body.model_dump(), category=category, category_label=cat["label"])
        return vacancy

    def set_published(self, vacancy_id: int, user: CurrentUser, published: bool) -> dict[str, Any]:
        vacancy = self.get(vacancy_id, user)
        if published and vacancy["status"] == VacancyStatus.published:
            raise AppError(409, "invalid_transition", "Вакансия уже опубликована")
        if not published and vacancy["status"] != VacancyStatus.published:
            raise AppError(409, "invalid_transition", "Вакансия не опубликована")
        vacancy["status"] = VacancyStatus.published if published else VacancyStatus.unpublished
        if published:
            vacancy["published_at"] = _now()
        return vacancy

    # ---------- отклики ----------

    def application_view(self, app: Record, role: Role) -> dict[str, Any]:
        data = dict(app)
        data["candidate"] = None
        data["candidate_contacts"] = None
        if role == Role.recruiter:
            cand = self.candidates.repo.get(app["candidate_id"])
            if cand:
                data["candidate"] = to_card(cand)
                # кандидат откликнулся сам — контакты компании открыты сразу [ТЗ 2.1]
                data["candidate_contacts"] = to_contacts(cand)
        return data

    def list_applications(self, user: CurrentUser) -> list[dict[str, Any]]:
        if user.role == Role.recruiter:
            items = [a for a in self.repo.applications() if a["company_id"] == user.company_id]
        else:
            items = [a for a in self.repo.applications() if a["candidate_id"] == user.candidate_id]
        items.sort(key=lambda a: a["created_at"], reverse=True)
        return [self.application_view(a, user.role) for a in items]

    def vacancy_applications(self, vacancy_id: int, user: CurrentUser) -> list[dict[str, Any]]:
        self.get(vacancy_id, user)
        items = [a for a in self.repo.applications() if a["vacancy_id"] == vacancy_id]
        items.sort(key=lambda a: a["created_at"], reverse=True)
        return [self.application_view(a, Role.recruiter) for a in items]

    def apply(self, vacancy_id: int, user: CurrentUser, cover_letter: str) -> dict[str, Any]:
        vacancy = self.get(vacancy_id, user)
        if vacancy.get("my_application_id"):
            raise AppError(409, "already_applied", "Вы уже откликнулись на эту вакансию")
        now = _now()
        app = {
            "id": self.repo.next_application_id(),
            "vacancy_id": vacancy_id,
            "candidate_id": user.candidate_id,
            "vacancy_title": vacancy["title"],
            "company_id": vacancy["company_id"],
            "company_name": vacancy["company_name"],
            "cover_letter": cover_letter,
            "status": ApplicationStatus.new,
            "created_at": now,
            "updated_at": now,
        }
        return self.application_view(app, Role.candidate)

    def update_application(
        self, application_id: int, user: CurrentUser, new_status: ApplicationStatus
    ) -> dict[str, Any]:
        app = self.repo.application(application_id)
        if app is None or app["company_id"] != user.company_id:
            raise not_found("application", application_id)
        data = dict(app)
        data.update(status=new_status, updated_at=_now())
        return self.application_view(data, Role.recruiter)
