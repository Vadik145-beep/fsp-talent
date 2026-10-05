"""Приглашения: видимость по ролям, машина состояний, валидации, квота, подсказка.

Заглушки до волны 3b: изменения возвращаются в ответе, но не сохраняются.
"""

import statistics
from datetime import datetime, timedelta
from typing import Any

from app.candidates.service import CandidateService, is_searchable, to_card, to_contacts
from app.catalog.repository import CatalogRepository
from app.common.enums import (
    ACTIVE_INVITATION_STATUSES,
    DeclineReason,
    InvitationStatus,
    Role,
)
from app.common.fixtures import Record
from app.core.errors import AppError, not_found
from app.core.security import CurrentUser
from app.invitations.repository import InvitationRepository
from app.invitations.schemas import InvitationCreate

S = InvitationStatus
# Допустимые переходы статусов (T7.3). Недопустимый переход → 409 invalid_transition.
TRANSITIONS: dict[InvitationStatus, set[InvitationStatus]] = {
    S.sent: {S.viewed, S.accepted, S.declined, S.expired, S.withdrawn},
    S.viewed: {S.accepted, S.declined, S.expired, S.withdrawn},
    S.accepted: set(),
    S.declined: set(),
    S.expired: set(),
    S.withdrawn: set(),
}
DECLINE_LABELS = {
    DeclineReason.salary_too_low: "Мала зарплата",
    DeclineReason.wrong_stack: "Не тот стек",
    DeclineReason.not_interested_domain: "Не интересна сфера",
    DeclineReason.not_looking: "Не ищу работу сейчас",
    DeclineReason.other: "Другое",
}


def can_transition(current: InvitationStatus, target: InvitationStatus) -> bool:
    return target in TRANSITIONS[current]


def _now() -> str:
    return datetime.now().astimezone().isoformat()


class InvitationService:
    def __init__(
        self,
        repo: InvitationRepository | None = None,
        candidates: CandidateService | None = None,
        catalog: CatalogRepository | None = None,
    ) -> None:
        self.repo = repo or InvitationRepository()
        self.candidates = candidates or CandidateService()
        self.catalog = catalog or CatalogRepository()

    # ---------- проекция по роли ----------

    def to_api(self, inv: Record, role: Role) -> dict[str, Any]:
        data = dict(inv)
        accepted = inv["status"] == InvitationStatus.accepted
        data["decline_reason_label"] = (
            DECLINE_LABELS.get(DeclineReason(inv["decline_reason"]))
            if inv.get("decline_reason")
            else None
        )
        data["candidate"] = None
        data["candidate_contacts"] = None
        data["recruiter_contacts"] = None
        if role == Role.recruiter:
            cand = self.candidates.repo.get(inv["candidate_id"])
            if cand:
                data["candidate"] = to_card(cand)
                if accepted:
                    data["candidate_contacts"] = to_contacts(cand)
        elif role == Role.candidate and accepted:
            rec = self.repo.recruiter(inv["recruiter_id"])
            if rec:
                data["recruiter_contacts"] = {
                    k: rec.get(k) for k in ("full_name", "position", "email", "phone", "telegram")
                }
        return data

    # ---------- доступ ----------

    def _visible(self, inv: Record, user: CurrentUser) -> bool:
        if user.role == Role.candidate:
            return bool(inv["candidate_id"] == user.candidate_id)
        if user.role == Role.recruiter:
            return bool(inv["company_id"] == user.company_id)
        return user.role == Role.admin

    def _get_visible(self, invitation_id: int, user: CurrentUser) -> Record:
        inv = self.repo.get(invitation_id)
        if inv is None or not self._visible(inv, user):
            # чужое приглашение неотличимо от несуществующего
            raise not_found("invitation", invitation_id)
        return inv

    def list_for(self, user: CurrentUser, status: InvitationStatus | None) -> list[dict[str, Any]]:
        items = [i for i in self.repo.all() if self._visible(i, user)]
        if status:
            items = [i for i in items if i["status"] == status]
        items.sort(key=lambda i: i["created_at"], reverse=True)
        return [self.to_api(i, user.role) for i in items]

    def detail(self, invitation_id: int, user: CurrentUser) -> dict[str, Any]:
        inv = dict(self._get_visible(invitation_id, user))
        events = list(self.repo.events(invitation_id))
        if user.role == Role.candidate and inv["status"] == InvitationStatus.sent:
            # открытие кандидатом автоматически переводит в «просмотрено»
            inv["status"] = InvitationStatus.viewed
            inv["viewed_at"] = _now()
            events.append(
                {
                    "id": 0,
                    "invitation_id": invitation_id,
                    "type": "viewed",
                    "at": inv["viewed_at"],
                    "actor_role": "candidate",
                }
            )
        data = self.to_api(inv, user.role)
        data["events"] = events
        return data

    def _transition(
        self, invitation_id: int, user: CurrentUser, target: InvitationStatus, **changes: Any
    ) -> dict[str, Any]:
        inv = dict(self._get_visible(invitation_id, user))
        current = InvitationStatus(inv["status"])
        if not can_transition(current, target):
            raise AppError(
                409,
                "invalid_transition",
                "Действие недоступно в текущем статусе приглашения",
                {"from": current, "to": target},
            )
        inv.update(status=target, **changes)
        return self.to_api(inv, user.role)

    def accept(self, invitation_id: int, user: CurrentUser) -> dict[str, Any]:
        return self._transition(invitation_id, user, S.accepted, responded_at=_now())

    def decline(
        self, invitation_id: int, user: CurrentUser, reason: DeclineReason, comment: str | None
    ) -> dict[str, Any]:
        return self._transition(
            invitation_id,
            user,
            S.declined,
            responded_at=_now(),
            decline_reason=reason,
            decline_comment=comment,
        )

    def withdraw(self, invitation_id: int, user: CurrentUser) -> dict[str, Any]:
        return self._transition(invitation_id, user, S.withdrawn, withdrawn_at=_now())

    # ---------- создание ----------

    def quota(self, recruiter_id: int) -> dict[str, Any]:
        limit = int(self.catalog.platform_settings().get("invitation_quota", 20))
        used = sum(
            1
            for i in self.repo.all()
            if i["recruiter_id"] == recruiter_id and i["status"] in ACTIVE_INVITATION_STATUSES
        )
        left = max(0, limit - used)
        return {
            "limit": limit,
            "used": used,
            "left": left,
            "hint": None if left else "Квота исчерпана: отзовите или дождитесь ответа по старым",
        }

    def create(self, body: InvitationCreate, user: CurrentUser) -> dict[str, Any]:
        assert user.recruiter_id is not None and user.company_id is not None
        cand = self.candidates.repo.get(body.candidate_id)
        if cand is None or not is_searchable(cand):
            raise not_found("candidate", body.candidate_id)
        if self.quota(user.recruiter_id)["left"] <= 0:
            raise AppError(409, "quota_exceeded", "Достигнута квота активных приглашений")
        if any(
            i["company_id"] == user.company_id
            and i["candidate_id"] == body.candidate_id
            and i["status"] in ACTIVE_INVITATION_STATUSES
            for i in self.repo.all()
        ):
            raise AppError(409, "already_invited", "У кандидата уже есть активное приглашение")
        min_salary = cand.get("min_salary")
        if min_salary and body.salary_to < min_salary:
            # сумму кандидата не раскрываем
            raise AppError(422, "salary_below_expectations", "Вилка ниже ожиданий кандидата")
        rec = self.repo.recruiter(user.recruiter_id) or {}
        company = self.repo.company(user.company_id) or {}
        now = datetime.now().astimezone()
        ttl = int(self.catalog.platform_settings().get("invitation_ttl_days", 7))
        inv = {
            "id": self.repo.next_id(),
            "candidate_id": body.candidate_id,
            "recruiter_id": user.recruiter_id,
            "company_id": user.company_id,
            "company_name": company.get("name", ""),
            "recruiter_name": rec.get("full_name", user.full_name),
            "need_id": body.need_id,
            "vacancy_id": body.vacancy_id,
            "category": cand["category"],
            "category_label": cand["category_label"],
            "description": body.description,
            "salary_from": body.salary_from,
            "salary_to": body.salary_to,
            "contact_method": body.contact_method.model_dump(),
            "task_text": body.task_text,
            "status": InvitationStatus.sent,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=ttl)).isoformat(),
        }
        return self.to_api(inv, Role.recruiter)

    # ---------- рыночная подсказка ----------

    def market_hint(
        self, category: str, salary_from: int | None, salary_to: int | None
    ) -> dict[str, Any]:
        cat = self.catalog.category(category)
        if cat is None:
            raise not_found("category", category)
        accepted = [
            i
            for i in self.repo.all()
            if i["category"] == category and i["status"] == InvitationStatus.accepted
        ]
        mins = [
            c["min_salary"]
            for c in self.candidates.repo.all()
            if c.get("category") == category and c.get("min_salary")
        ]
        med_from = int(statistics.median(i["salary_from"] for i in accepted)) if accepted else None
        med_to = int(statistics.median(i["salary_to"] for i in accepted)) if accepted else None
        probability = None
        if salary_to and mins:
            probability = round(sum(1 for m in mins if m <= salary_to) / len(mins), 2)
        reference = med_from or (int(statistics.median(mins)) if mins else None)
        message = (
            f"В категории «{cat['label']}» обычно принимают от {reference:,} ₽".replace(",", " ")
            if reference
            else f"По категории «{cat['label']}» пока мало данных"
        )
        return {
            "category": category,
            "category_label": cat["label"],
            "median_accepted_from": med_from,
            "median_accepted_to": med_to,
            "acceptance_probability": probability,
            "sample_size": len(accepted) + len(mins),
            "message": message,
        }
