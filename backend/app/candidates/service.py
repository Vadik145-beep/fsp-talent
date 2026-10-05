"""Профиль кандидата и правила видимости для рекрутера.

Главное правило [ТЗ 2.1, 2.2 п.2]: рекрутер видит обезличенную карточку. ФИО и контакты —
только если кандидат принял приглашение компании рекрутера или сам откликнулся
на её вакансию. Минимальная зарплата не уходит рекрутеру никогда.
"""

from collections.abc import Callable
from datetime import date
from typing import Any

from app.candidates.repository import CandidateRepository
from app.common.enums import ACTIVE_INVITATION_STATUSES, InvitationStatus
from app.common.fixtures import Record
from app.common.schemas import paginate
from app.core.errors import not_found

# Поля карточки, которые рекрутер видит всегда (без ФИО, контактов, зарплаты, ФСП ID)
CARD_FIELDS = (
    "id",
    "pseudonym",
    "specialization",
    "grade",
    "category",
    "category_label",
    "theta",
    "stack",
    "work_formats",
    "roles_in_team",
    "topic_scores",
    "freshness",
)


def is_searchable(candidate: Record) -> bool:
    """В выдаче: есть грейд, дано согласие на публикацию, поиск не на паузе [T2.4, T3.4]."""
    return (
        bool(candidate.get("grade"))
        and bool(candidate.get("publication_consent"))
        and not candidate.get("job_search_paused")
    )


def to_card(candidate: Record) -> dict[str, Any]:
    privacy = candidate.get("privacy") or {}
    card: dict[str, Any] = {key: candidate.get(key) for key in CARD_FIELDS}
    card["city"] = candidate.get("city") if privacy.get("show_city") else None
    card["experience_years"] = (
        candidate.get("experience_years") if privacy.get("show_experience") else None
    )
    card["links"] = candidate.get("links") if privacy.get("show_links") else None
    card["has_fsp"] = bool(candidate.get("fsp_id"))
    show_fsp = privacy.get("show_fsp_achievements", True)
    card["fsp_score"] = candidate.get("fsp_score") if show_fsp else None
    card["fsp_badges"] = candidate.get("fsp_badges", []) if show_fsp else []
    return card


def to_contacts(candidate: Record) -> dict[str, Any]:
    return {
        "full_name": candidate["full_name"],
        "email": candidate["email"],
        "phone": candidate.get("phone"),
        "telegram": candidate.get("telegram"),
    }


SORT_KEYS: dict[str, Callable[[Record], Any]] = {
    "theta": lambda c: -(c.get("theta") or -99),
    "fsp": lambda c: -(c.get("fsp_score") or 0),
    "freshness": lambda c: -c["freshness"],
    "recent": lambda c: c.get("last_test_at") or "",
}


class CandidateService:
    def __init__(self, repo: CandidateRepository | None = None) -> None:
        self.repo = repo or CandidateRepository()

    def get_or_404(self, candidate_id: int) -> Record:
        candidate = self.repo.get(candidate_id)
        if candidate is None:
            raise not_found("candidate", candidate_id)
        return candidate

    # ---------- видимость контактов ----------

    def contacts_visible(self, candidate_id: int, company_id: int) -> bool:
        accepted = any(
            inv["company_id"] == company_id and inv["status"] == InvitationStatus.accepted
            for inv in self.repo.invitations(candidate_id)
        )
        applied = any(
            app["company_id"] == company_id for app in self.repo.applications(candidate_id)
        )
        return accepted or applied

    # ---------- кабинет кандидата ----------

    def dashboard(self, candidate_id: int) -> dict[str, Any]:
        cand = self.get_or_404(candidate_id)
        invitations = sorted(
            self.repo.invitations(candidate_id), key=lambda i: i["created_at"], reverse=True
        )
        new = [i for i in invitations if i["status"] in ACTIVE_INVITATION_STATUSES]
        active = next(
            (s for s in self.repo.submissions(candidate_id) if s["status"] == "assigned"), None
        )
        hints: list[str] = []
        if not cand.get("fsp_id"):
            hints.append(
                "Привяжите ФСП ID — достижения появятся в профиле с отметкой «подтверждено ФСП»"
            )
        if not cand.get("links"):
            hints.append("Добавьте ссылку на GitHub — профиль станет полнее")
        if not cand.get("grade"):
            hints.append("Пройдите тест, чтобы получить категорию и попасть в выдачу работодателям")
        return {
            "full_name": cand["full_name"],
            "category": cand.get("category"),
            "category_label": cand.get("category_label"),
            "grade": cand.get("grade"),
            "theta": cand.get("theta"),
            "onboarding_completed": bool(cand.get("grade")),
            "new_invitations_count": len(new),
            "recent_invitations": invitations[:3],
            "active_task": (
                {
                    "submission_id": active["id"],
                    "title": active["task_title"],
                    "due_at": active["due_at"],
                }
                if active
                else None
            ),
            "profile_completeness": cand["profile_completeness"],
            "fsp_linked": bool(cand.get("fsp_id")),
            "hints": hints,
        }

    def settings(self, candidate_id: int) -> dict[str, Any]:
        cand = self.get_or_404(candidate_id)
        return {
            "privacy": cand["privacy"],
            "job_search_paused": cand["job_search_paused"],
            "publication_consent": cand["publication_consent"],
            "fsp_linked": bool(cand.get("fsp_id")),
            "fsp_id": cand.get("fsp_id"),
        }

    # ---------- кабинет рекрутера ----------

    def search(
        self,
        *,
        specialization: str | None = None,
        grade: str | None = None,
        category: str | None = None,
        skills: list[str] | None = None,
        has_fsp: bool | None = None,
        work_format: str | None = None,
        city: str | None = None,
        sort: str = "theta",
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        items = [c for c in self.repo.all() if is_searchable(c)]
        if specialization:
            items = [c for c in items if c["specialization"] == specialization]
        if grade:
            items = [c for c in items if c["grade"] == grade]
        if category:
            items = [c for c in items if c["category"] == category]
        if skills:
            items = [c for c in items if set(skills) <= set(c["stack"])]
        if has_fsp is not None:
            items = [c for c in items if bool(c.get("fsp_id")) == has_fsp]
        if work_format:
            items = [c for c in items if work_format in c["work_formats"]]
        if city:
            items = [c for c in items if c["privacy"].get("show_city") and c.get("city") == city]
        items.sort(key=SORT_KEYS.get(sort, SORT_KEYS["theta"]), reverse=sort == "recent")
        return paginate([to_card(c) for c in items], page, page_size)

    def anonymous_profile(self, candidate_id: int, company_id: int) -> dict[str, Any]:
        cand = self.get_or_404(candidate_id)
        visible = self.contacts_visible(candidate_id, company_id)
        if not is_searchable(cand) and not visible:
            # профиль скрыт (нет согласия / пауза поиска) — для рекрутера его нет
            raise not_found("candidate", candidate_id)
        company_invs = sorted(
            (i for i in self.repo.invitations(candidate_id) if i["company_id"] == company_id),
            key=lambda i: i["created_at"],
            reverse=True,
        )
        last_inv = company_invs[0] if company_invs else None
        history = [
            {
                "date": date.fromisoformat(s["finished_at"][:10]),
                "category": s["result_category"],
                "theta": s["theta"],
            }
            for s in self.repo.test_sessions(candidate_id)
            if s["status"] == "finished" and s.get("passed")
        ]
        profile = to_card(cand)
        profile.update(
            soft_skills=cand.get("soft_skills", []),
            test_history=history,
            invitation_id=last_inv["id"] if last_inv else None,
            invitation_status=last_inv["status"] if last_inv else None,
            contacts_visible=visible,
            contacts=to_contacts(cand) if visible else None,
            can_invite=is_searchable(cand)
            and not (last_inv and last_inv["status"] in ACTIVE_INVITATION_STATUSES),
        )
        return profile
