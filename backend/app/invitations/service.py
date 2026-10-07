"""Приглашения на БД: видимость по ролям, машина состояний, валидации, квота, подсказка, письма.

Правила [ТЗ 2.1, 2.2]:
- до принятия рекрутер видит только обезличенную карточку (псевдоним, без ФИО, контактов,
  минимальной зарплаты, с учётом приватности); после принятия — контакты кандидата,
  а кандидат — контакты рекрутера; раскрытие пишется в журнал событий и `audit_log`;
- вилка от–до обязательна; максимум вилки ниже минимума кандидата → 422 без суммы;
- кандидат видит только свои приглашения, рекрутер — приглашения своей компании (чужое → 404);
- `sent`/`viewed` старше срока из настроек становятся `expired` лениво, при любом обращении.
"""

import math
import statistics
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.audit import write_audit
from app.candidates.service import to_card, to_contacts
from app.catalog.clock import as_msk, now_msk
from app.catalog.repository import CatalogDb
from app.common.enums import (
    DeclineReason,
    InvitationStatus,
    Role,
)
from app.common.fixtures import Record
from app.core.config import get_settings
from app.core.errors import AppError, not_found
from app.core.security import CurrentUser
from app.invitations.models import Invitation, InvitationEvent
from app.invitations.repository import InvitationDb, InvitationRow
from app.invitations.schemas import InvitationCreate
from app.matching.models import Need
from app.matching.repository import CandidatePool
from app.vacancies.models import Vacancy

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
STATUS_LABELS = {
    S.sent: "Отправлено",
    S.viewed: "Просмотрено",
    S.accepted: "Принято",
    S.declined: "Отклонено",
    S.expired: "Истекло",
    S.withdrawn: "Отозвано",
}
DECLINE_LABELS = {
    DeclineReason.salary_too_low: "Мала зарплата",
    DeclineReason.wrong_stack: "Не тот стек",
    DeclineReason.not_interested_domain: "Не интересна сфера",
    DeclineReason.not_looking: "Не ищу работу сейчас",
    DeclineReason.other: "Другое",
}
QUOTA_HINT = "Квота исчерпана. Отзовите неактуальные приглашения или дождитесь ответов кандидатов."
MIN_HINT_SAMPLE = 3
NBSP = " "


def can_transition(current: InvitationStatus, target: InvitationStatus) -> bool:
    return target in TRANSITIONS[current]


def money(value: int) -> str:
    return f"{value:,}".replace(",", NBSP) + f"{NBSP}₽"


def _half_up(value: float) -> int:
    return math.floor(value + 0.5)


def _median(values: list[int]) -> int:
    return _half_up(statistics.median(values))


def _round10k(value: float) -> int:
    return _half_up(value / 10000) * 10000


@dataclass
class Mail:
    to: str
    subject: str
    text: str


class InvitationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.db = InvitationDb(session)
        self.pool = CandidatePool(session)
        self.catalog = CatalogDb(session)
        # письма, которые роутер отправит после ответа (BackgroundTasks)
        self.outbox: list[Mail] = []

    # ---------- проекция по роли ----------

    @staticmethod
    def _record(row: InvitationRow) -> dict[str, Any]:
        inv, company_name, recruiter_name, category_label = row
        reason = inv.decline_reason
        return {
            "id": inv.id,
            "candidate_id": inv.candidate_id,
            "recruiter_id": inv.recruiter_id,
            "company_id": inv.company_id,
            "company_name": company_name,
            "recruiter_name": recruiter_name,
            "need_id": inv.need_id,
            "vacancy_id": inv.vacancy_id,
            "category": inv.category,
            "category_label": category_label or inv.category,
            "description": inv.description,
            "salary_from": inv.salary_from,
            "salary_to": inv.salary_to,
            "contact_method": {"type": inv.contact_type, "value": inv.contact_value},
            "task_text": inv.task_text,
            "status": inv.status,
            "decline_reason": reason,
            "decline_reason_label": DECLINE_LABELS.get(DeclineReason(reason)) if reason else None,
            "decline_comment": inv.decline_comment,
            "created_at": as_msk(inv.created_at),
            "viewed_at": as_msk(inv.viewed_at),
            "responded_at": as_msk(inv.responded_at),
            "expires_at": as_msk(inv.expires_at),
            "withdrawn_at": as_msk(inv.withdrawn_at),
            "candidate": None,
            "candidate_contacts": None,
            "recruiter_contacts": None,
        }

    async def _views(self, rows: list[InvitationRow], role: Role) -> list[dict[str, Any]]:
        """Записи для API пачкой: карточки кандидатов и контакты — одним запросом на всех."""
        data = [self._record(r) for r in rows]
        if role == Role.recruiter:
            cands = await self.pool.records(list({d["candidate_id"] for d in data}))
            for d in data:
                cand = cands.get(d["candidate_id"])
                if cand is None:
                    continue
                d["candidate"] = to_card(cand)
                if d["status"] == S.accepted:
                    d["candidate_contacts"] = to_contacts(cand)
        elif role == Role.candidate:
            accepted = [d["recruiter_id"] for d in data if d["status"] == S.accepted]
            contacts = await self.db.recruiter_contacts(list(set(accepted)))
            for d in data:
                if d["status"] == S.accepted:
                    d["recruiter_contacts"] = contacts.get(d["recruiter_id"])
        return data

    async def _view(self, invitation_id: int, role: Role) -> dict[str, Any]:
        row = await self.db.row(invitation_id)
        assert row is not None
        return (await self._views([row], role))[0]

    # ---------- доступ ----------

    async def _expire(self) -> None:
        if await self.db.expire_overdue(now_msk()):
            await self.session.commit()

    @staticmethod
    def _visible(inv: Invitation, user: CurrentUser) -> bool:
        if user.role == Role.candidate:
            return user.candidate_id is not None and inv.candidate_id == user.candidate_id
        if user.role == Role.recruiter:
            return user.company_id is not None and inv.company_id == user.company_id
        return False

    async def _own(self, invitation_id: int, user: CurrentUser) -> Invitation:
        await self._expire()
        inv = await self.db.get(invitation_id)
        if inv is None or not self._visible(inv, user):
            # чужое приглашение неотличимо от несуществующего
            raise not_found("invitation", invitation_id)
        return inv

    def _event(self, inv: Invitation, type_: str, user: CurrentUser | None) -> None:
        self.session.add(
            InvitationEvent(
                invitation_id=inv.id,
                type=type_,
                at=now_msk(),
                actor_user_id=user.user_id if user else None,
                actor_role=str(user.role) if user else None,
            )
        )

    # ---------- списки и карточка ----------

    async def list_for(self, user: CurrentUser, status: InvitationStatus | None) -> list[Any]:
        await self._expire()
        conditions = []
        if user.role == Role.candidate:
            conditions.append(Invitation.candidate_id == (user.candidate_id or -1))
        elif user.role == Role.recruiter:
            conditions.append(Invitation.company_id == (user.company_id or -1))
        else:
            return []
        if status:
            conditions.append(Invitation.status == status.value)
        return await self._views(await self.db.rows(*conditions), user.role)

    async def detail(self, invitation_id: int, user: CurrentUser) -> dict[str, Any]:
        inv = await self._own(invitation_id, user)
        now = now_msk()
        if user.role == Role.candidate and inv.status == S.sent:
            # открытие кандидатом автоматически переводит в «просмотрено»
            inv.status = S.viewed.value
            inv.viewed_at = now
            self._event(inv, "viewed", user)
        elif user.role == Role.recruiter:
            inv.recruiter_seen_at = now
        await self.session.commit()
        data = await self._view(invitation_id, user.role)
        data["events"] = [
            {
                "id": e.id,
                "invitation_id": e.invitation_id,
                "type": e.type,
                "at": as_msk(e.at),
                "actor_role": e.actor_role,
            }
            for e in await self.db.events(invitation_id)
        ]
        return data

    async def counters(self, user: CurrentUser) -> dict[str, int]:
        await self._expire()
        if user.role == Role.candidate and user.candidate_id is not None:
            new, active = await self.db.count_candidate_new(user.candidate_id)
            return {"new": new, "active": active}
        if user.role == Role.recruiter and user.company_id is not None:
            return {
                "new": await self.db.count_company_updates(user.company_id),
                "active": await self.db.count_company_active(user.company_id),
            }
        return {"new": 0, "active": 0}

    # ---------- переходы ----------

    @staticmethod
    def _check_transition(inv: Invitation, target: InvitationStatus) -> None:
        current = InvitationStatus(inv.status)
        if not can_transition(current, target):
            raise AppError(
                409,
                "invalid_transition",
                f"Действие недоступно: приглашение в статусе «{STATUS_LABELS[current]}»",
                {"from": current.value, "to": target.value},
            )

    def _mark_viewed(self, inv: Invitation, user: CurrentUser) -> None:
        if inv.viewed_at is None:
            inv.viewed_at = now_msk()
            self._event(inv, "viewed", user)

    async def accept(self, invitation_id: int, user: CurrentUser) -> dict[str, Any]:
        inv = await self._own(invitation_id, user)
        self._check_transition(inv, S.accepted)
        self._mark_viewed(inv, user)
        inv.status = S.accepted.value
        inv.responded_at = now_msk()
        self._event(inv, "accepted", user)
        self._event(inv, "contacts_revealed", None)
        cand = (await self.pool.records([inv.candidate_id])).get(inv.candidate_id) or {}
        company = await self.db.company(inv.company_id)
        company_name = company.name if company else ""
        await write_audit(
            self.session,
            user,
            "contacts_revealed",
            "invitation",
            inv.id,
            f"Раскрыты контакты: {cand.get('pseudonym', 'кандидат')} ↔ {company_name}",
            {
                "candidate_id": inv.candidate_id,
                "company_id": inv.company_id,
                "recruiter_id": inv.recruiter_id,
            },
        )
        await self.session.commit()
        await self._notify_recruiter(inv, cand, accepted=True)
        return await self._view(invitation_id, user.role)

    async def decline(
        self, invitation_id: int, user: CurrentUser, reason: DeclineReason, comment: str | None
    ) -> dict[str, Any]:
        inv = await self._own(invitation_id, user)
        comment = (comment or "").strip() or None
        if reason == DeclineReason.other and not comment:
            raise AppError(
                422,
                "validation_error",
                "Опишите причину в комментарии",
                {"fields": {"comment": "Напишите пару слов"}},
            )
        self._check_transition(inv, S.declined)
        self._mark_viewed(inv, user)
        inv.status = S.declined.value
        inv.responded_at = now_msk()
        inv.decline_reason = reason.value
        inv.decline_comment = comment
        self._event(inv, "declined", user)
        await self.session.commit()
        cand = (await self.pool.records([inv.candidate_id])).get(inv.candidate_id) or {}
        await self._notify_recruiter(inv, cand, accepted=False)
        return await self._view(invitation_id, user.role)

    async def withdraw(self, invitation_id: int, user: CurrentUser) -> dict[str, Any]:
        inv = await self._own(invitation_id, user)
        self._check_transition(inv, S.withdrawn)
        inv.status = S.withdrawn.value
        inv.withdrawn_at = now_msk()
        self._event(inv, "withdrawn", user)
        await self.session.commit()
        return await self._view(invitation_id, user.role)

    # ---------- квота и создание ----------

    async def quota(self, recruiter_id: int) -> dict[str, Any]:
        await self._expire()
        limit = int((await self.catalog.settings()).get("invitation_quota", 20))
        used = await self.db.active_count(recruiter_id)
        left = max(0, limit - used)
        return {"limit": limit, "used": used, "left": left, "hint": None if left else QUOTA_HINT}

    async def create(self, body: InvitationCreate, user: CurrentUser) -> dict[str, Any]:
        assert user.recruiter_id is not None and user.company_id is not None
        if not await self.pool.is_searchable(body.candidate_id):
            raise AppError(
                404,
                "not_found",
                "Кандидат не найден или скрыл профиль",
                {"resource": "candidate", "id": body.candidate_id},
            )
        quota = await self.quota(user.recruiter_id)
        if quota["left"] <= 0:
            raise AppError(
                409,
                "quota_exceeded",
                f"Достигнута квота: {quota['limit']} активных приглашений. "
                "Отзовите неактуальные или дождитесь ответов.",
                {"limit": quota["limit"], "used": quota["used"]},
            )
        existing = await self.db.active_for(user.company_id, body.candidate_id)
        if existing is not None:
            raise AppError(
                409,
                "already_invited",
                "У кандидата уже есть активное приглашение от вашей компании",
                {"invitation_id": existing.id},
            )
        cand = (await self.pool.records([body.candidate_id]))[body.candidate_id]
        min_salary = cand.get("min_salary")
        if min_salary and body.salary_to < min_salary:
            # сумму ожиданий кандидата не раскрываем — только факт
            raise AppError(
                422,
                "salary_below_expectations",
                "Вилка ниже ожиданий кандидата. Поднимите верхнюю границу.",
            )
        if body.need_id is not None:
            need = await self.session.get(Need, body.need_id)
            if need is None or need.company_id != user.company_id:
                raise not_found("need", body.need_id)
        if body.vacancy_id is not None:
            vacancy = await self.session.get(Vacancy, body.vacancy_id)
            if vacancy is None or vacancy.company_id != user.company_id:
                raise not_found("vacancy", body.vacancy_id)

        now = now_msk()
        ttl = int((await self.catalog.settings()).get("invitation_ttl_days", 7))
        inv = Invitation(
            candidate_id=body.candidate_id,
            recruiter_id=user.recruiter_id,
            company_id=user.company_id,
            need_id=body.need_id,
            vacancy_id=body.vacancy_id,
            category=cand["category"],
            description=body.description.strip(),
            salary_from=body.salary_from,
            salary_to=body.salary_to,
            contact_type=str(body.contact_method.type),
            contact_value=body.contact_method.value.strip(),
            task_text=(body.task_text or "").strip() or None,
            status=S.sent.value,
            created_at=now,
            expires_at=now + timedelta(days=ttl),
        )
        self.session.add(inv)
        await self.session.flush()
        self._event(inv, "created", user)
        await self.session.commit()
        await self._notify_candidate(inv, cand)
        return await self._view(inv.id, Role.recruiter)

    # ---------- письма (T7.8) ----------

    async def _notify_candidate(self, inv: Invitation, cand: Record) -> None:
        if not cand.get("email"):
            return
        company = await self.db.company(inv.company_id)
        name = company.name if company else "Компания"
        link = f"{get_settings().public_frontend_url}/candidate/invitations/{inv.id}"
        salary = f"от {money(inv.salary_from)} до {money(inv.salary_to)}"
        self.outbox.append(
            Mail(
                to=cand["email"],
                subject=f"Новое приглашение от «{name}»: {salary}",
                text=(
                    f"Здравствуйте!\n\n«{name}» приглашает вас: {salary}.\n\n"
                    f"{inv.description}\n\n"
                    f"Приглашение действует до {as_msk(inv.expires_at):%d.%m.%Y}. "
                    f"Принять или отклонить: {link}\n\n"
                    "Ваши контакты компания увидит, только если вы примете приглашение.\n"
                    "— fsp-talent"
                ),
            )
        )

    async def _notify_recruiter(self, inv: Invitation, cand: Record, *, accepted: bool) -> None:
        to = await self.db.recruiter_email(inv.recruiter_id)
        if not to:
            return
        who = cand.get("pseudonym", "Кандидат")
        link = f"{get_settings().public_frontend_url}/recruiter/invitations"
        if accepted:
            subject = f"{who} принял приглашение"
            body = (
                f"{who} принял ваше приглашение "
                f"(от {money(inv.salary_from)} до {money(inv.salary_to)}).\n\n"
                f"Контакты: {cand.get('full_name', '')}, {cand.get('email', '')}"
                f"{', ' + cand['phone'] if cand.get('phone') else ''}"
                f"{', ' + cand['telegram'] if cand.get('telegram') else ''}.\n\n"
                f"Приглашения: {link}\n— fsp-talent"
            )
        else:
            reason = (
                DECLINE_LABELS.get(DeclineReason(inv.decline_reason), "")
                if inv.decline_reason
                else ""
            )
            comment = f"\nКомментарий: {inv.decline_comment}" if inv.decline_comment else ""
            subject = f"{who} отклонил приглашение"
            body = (
                f"{who} отклонил ваше приглашение.\nПричина: {reason}.{comment}\n\n"
                f"Приглашения: {link}\n— fsp-talent"
            )
        self.outbox.append(Mail(to=to, subject=subject, text=body))

    # ---------- рыночная подсказка (T7.7) ----------

    async def market_hint(
        self, category: str, salary_from: int | None, salary_to: int | None
    ) -> dict[str, Any]:
        cat = await self.catalog.category(category)
        if cat is None:
            raise not_found("category", category)
        label = cat.label
        accepted = await self.db.accepted_ranges(category)
        mins = await self.db.candidate_minimums(category)
        med_from: int | None = None
        med_to: int | None = None
        if len(accepted) >= MIN_HINT_SAMPLE:
            med_from = _median([a for a, _ in accepted])
            med_to = _median([b for _, b in accepted])
            sample = len(accepted)
        else:
            # мало принятых приглашений — оцениваем по ожиданиям кандидатов категории (+ принятые)
            pool = mins + [a for a, _ in accepted]
            sample = len(pool)
            if sample >= MIN_HINT_SAMPLE:
                m = statistics.median(pool)
                med_from, med_to = _round10k(m), _round10k(m * 1.25)
        probability: float | None = None
        upper = salary_to or salary_from
        if sample >= MIN_HINT_SAMPLE and upper and len(mins) >= MIN_HINT_SAMPLE:
            share = sum(1 for v in mins if v <= upper) / len(mins)
            lower = min(1.0, salary_from / med_from) if med_from and salary_from else 1.0
            raw = 0.1 + 0.85 * share * (0.6 + 0.4 * lower)
            probability = round(max(0.05, min(0.95, raw)), 2)
        if med_from is None:
            message = f"По категории {label} пока мало данных для подсказки."
        else:
            message = f"В категории {label} обычно принимают от {money(med_from)}."
            if probability is not None:
                message += (
                    f" Вероятность принятия с такой вилкой — около "
                    f"{round(probability * 100)}{NBSP}%."
                )
        return {
            "category": category,
            "category_label": label,
            "median_accepted_from": med_from,
            "median_accepted_to": med_to,
            "acceptance_probability": probability,
            "sample_size": sample,
            "message": message,
        }
