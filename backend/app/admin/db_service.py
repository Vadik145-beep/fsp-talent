"""Админка на БД (T10.1–T10.3): дашборд, пользователи, компании, справочники, настройки, журнал.

Каждое действие администратора пишется в audit_log.
"""

from collections import Counter
from datetime import timedelta
from typing import Any

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.audit import write_audit
from app.admin.models import Report
from app.admin.repository import AdminDb, audit_record, user_record
from app.admin.schemas import (
    AdminUserUpdate,
    CatalogLabelUpdate,
    PlatformSettingsUpdate,
    SkillUpsert,
    SpecializationCreate,
    TopicCreate,
)
from app.catalog.clock import now_msk
from app.catalog.service import CatalogDbService
from app.common.enums import InvitationStatus, ReportStatus, Role, TestSessionStatus
from app.common.fixtures import Record
from app.companies.antifraud import set_company_blocked
from app.companies.models import Company
from app.companies.repository import CompanyDb, company_record
from app.companies.service import response_rate, trust_score
from app.core.errors import AppError, not_found
from app.core.security import CurrentUser
from app.invitations.models import Invitation
from app.testing.models import Item, TestSession
from app.users.models import User

SETTING_LABELS = {
    "grade_thresholds": "Пороги θ",
    "grade_change_cooldown_days": "Кулдаун смены грейда, дней",
    "retry_cooldown_days": "Кулдаун повтора попытки, дней",
    "invitation_quota": "Квота приглашений",
    "invitation_ttl_days": "Срок приглашения, дней",
    "cat_se_stop": "Стоп CAT по SE",
    "cat_max_items": "Задач в тесте, максимум",
    "exposure_max_share": "Доля показов шаблона, максимум",
    "ranking_weights": "Веса ранжирования",
}

ROLE_LABELS = {"candidate": "соискатель", "recruiter": "рекрутер", "admin": "администратор"}


def _page(items: list[Record], total: int, page: int, page_size: int) -> dict[str, Any]:
    return {"items": items, "total": total, "page": page, "page_size": page_size}


class AdminDbService:
    def __init__(self, session: AsyncSession, actor: CurrentUser) -> None:
        self.session = session
        self.actor = actor
        self.db = AdminDb(session)
        self.catalog = CatalogDbService(session)
        self.companies_db = CompanyDb(session)

    async def _audit(
        self,
        action: str,
        target_type: str,
        target_id: int | None,
        summary: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        await write_audit(
            self.session, self.actor, action, target_type, target_id, summary, details
        )

    # ---------- дашборд (T10.1) ----------

    async def dashboard(self, period_days: int | None = None) -> Record:
        """Сводка платформы из БД.

        - пользователи по ролям — учётки с подтверждённой почтой (только они могут войти);
        - тесты — завершённые сессии; `period_days` ограничивает число и график по дням;
        - приглашения по статусам — с учётом просроченных, которые ещё не пересчитаны;
        - конверсия «приглашение → принятие» = принятые / (все − отозванные рекрутером);
        - открытые жалобы (новые и в работе), флаги утечек шаблонов (`items.leak_flag`).
        """
        now = now_msk()
        roles = await self.session.execute(
            select(User.role, func.count()).where(User.email_verified.is_(True)).group_by(User.role)
        )
        users_by_role = {r.value: 0 for r in Role} | {role: n for role, n in roles.all()}

        day = func.date(func.timezone("Europe/Moscow", TestSession.finished_at))
        tests_stmt = (
            select(day, func.count())
            .where(
                TestSession.status == TestSessionStatus.finished.value,
                TestSession.finished_at.is_not(None),
            )
            .group_by(day)
            .order_by(day)
        )
        if period_days:
            tests_stmt = tests_stmt.where(
                TestSession.finished_at >= now - timedelta(days=period_days)
            )
        tests_by_day = [
            {"date": d, "count": n} for d, n in (await self.session.execute(tests_stmt))
        ]

        overdue = and_(
            Invitation.status.in_([InvitationStatus.sent.value, InvitationStatus.viewed.value]),
            Invitation.expires_at < now,
        )
        status = case((overdue, InvitationStatus.expired.value), else_=Invitation.status)
        inv_rows = await self.session.execute(select(status, func.count()).group_by(status))
        by_status = {s.value: 0 for s in InvitationStatus} | {st: n for st, n in inv_rows.all()}
        base = sum(by_status.values()) - by_status[InvitationStatus.withdrawn]
        accepted = by_status[InvitationStatus.accepted]

        leaks = await self.session.scalars(
            select(Item).where(Item.leak_flag.is_(True)).order_by(Item.leak_score.desc(), Item.id)
        )
        open_reports = await self.session.scalar(
            select(func.count())
            .select_from(Report)
            .where(Report.status.in_([ReportStatus.new.value, ReportStatus.in_review.value]))
        )
        return {
            "users_by_role": users_by_role,
            "tests_total": sum(d["count"] for d in tests_by_day),
            "tests_by_day": tests_by_day,
            "invitations_by_status": by_status,
            "invite_to_accept_conversion": round(accepted / base, 3) if base else 0.0,
            "leak_flags": [
                {
                    "item_id": it.id,
                    "title": it.title,
                    "specialization": it.specialization,
                    "leak_score": it.leak_score,
                }
                for it in leaks.all()
            ],
            "open_reports": int(open_reports or 0),
        }

    # ---------- пользователи ----------

    async def users(
        self, q: str | None, role: Role | None, blocked: bool | None, page: int, page_size: int
    ) -> dict[str, Any]:
        rows, total = await self.db.users(q, role, blocked, page, page_size)
        return _page([user_record(u) for u in rows], total, page, page_size)

    async def update_user(self, user_id: int, body: AdminUserUpdate) -> Record:
        user = await self.db.user(user_id)
        if user is None:
            raise not_found("user", user_id)
        if user_id == self.actor.user_id and (
            body.blocked or (body.role and body.role != Role.admin)
        ):
            raise AppError(409, "cannot_change_self", "Нельзя заблокировать или понизить себя")
        if body.role is not None and body.role != user.role:
            await self._check_role_profile(user_id, body.role)
            old = user.role
            user.role = body.role.value
            await self._audit(
                "user_role_changed",
                "user",
                user_id,
                f"Роль изменена: {ROLE_LABELS.get(old, old)} → {ROLE_LABELS[body.role]}",
                {"role": [old, body.role.value]},
            )
        if body.blocked is not None and body.blocked != user.blocked:
            user.blocked = body.blocked
            verb = "заблокирован" if body.blocked else "разблокирован"
            await self._audit(
                "user_blocked" if body.blocked else "user_unblocked",
                "user",
                user_id,
                f"Пользователь {verb}: {user.email}",
            )
        await self.session.commit()
        return user_record(user)

    async def _check_role_profile(self, user_id: int, role: Role) -> None:
        """Роль соискателя/рекрутера требует соответствующего профиля, иначе кабинет пустой."""
        if role == Role.candidate and not await self.db.has_candidate_profile(user_id):
            raise AppError(
                409,
                "role_profile_missing",
                "У пользователя нет профиля соискателя — роль «соискатель» не назначить",
                {"role": role.value},
            )
        if role == Role.recruiter and not await self.db.has_recruiter_profile(user_id):
            raise AppError(
                409,
                "role_profile_missing",
                "Пользователь не состоит в компании — роль «рекрутер» не назначить",
                {"role": role.value},
            )

    async def user_audit(self, user_id: int) -> list[Record]:
        if await self.db.user(user_id) is None:
            raise not_found("user", user_id)
        return [audit_record(a) for a in await self.db.user_audit(user_id)]

    async def audit(
        self, action: str | None, target_type: str | None, page: int, page_size: int
    ) -> dict[str, Any]:
        rows, total = await self.db.audit(
            action=action, target_type=target_type, page=page, page_size=page_size
        )
        return _page([audit_record(a) for a in rows], total, page, page_size)

    # ---------- компании ----------

    @staticmethod
    def _company_view(
        company: Company,
        statuses: dict[int, Counter[str]],
        reports: dict[int, Counter[str]],
        recruiters: Counter[int],
    ) -> Record:
        inv = statuses.get(company.id, Counter())
        rep = reports.get(company.id, Counter())
        record = company_record(company)
        record.update(
            trust_score=trust_score(company, inv, rep),
            recruiters_count=recruiters[company.id],
            invitations_sent=sum(inv.values()),
            response_rate=response_rate(inv),
            reports_count=sum(rep.values()),
        )
        return record

    async def _views(self, companies: list[Company]) -> list[Record]:
        statuses = await self.companies_db.invitation_statuses()
        reports = await self.companies_db.report_statuses()
        recruiters = await self.companies_db.recruiters_count()
        return [self._company_view(c, statuses, reports, recruiters) for c in companies]

    async def companies(self) -> list[Record]:
        return await self._views(await self.companies_db.all())

    async def update_company(self, company_id: int, blocked: bool) -> Record:
        company = await self.companies_db.get(company_id)
        if company is None:
            raise not_found("company", company_id)
        await set_company_blocked(self.session, company, blocked, self.actor)
        await self.session.commit()
        return (await self._views([company]))[0]

    # ---------- настройки ----------

    async def settings(self) -> Record:
        return await self.catalog.settings()

    async def update_settings(self, body: PlatformSettingsUpdate) -> Record:
        changes = body.model_dump(exclude_none=True, mode="json")
        before, changed = await self.catalog.update_settings(changes)
        if changed:
            parts = []
            for key, value in changed.items():
                label = SETTING_LABELS.get(key, key)
                scalar = not isinstance(value, dict | list)
                parts.append(f"{label}: {before.get(key)} → {value}" if scalar else label)
            await self._audit(
                "settings_updated",
                "settings",
                None,
                "Изменены настройки — " + "; ".join(parts),
                {key: [before.get(key), value] for key, value in changed.items()},
            )
        await self.session.commit()
        return await self.catalog.settings()

    # ---------- справочники ----------

    async def _catalog_audit(
        self, action: str, target_type: str, code: str, summary: str, data: Record | None = None
    ) -> None:
        await self._audit(action, target_type, None, summary, {"id": code, **(data or {})})
        await self.session.commit()

    async def create_skill(self, body: SkillUpsert) -> Record:
        skill = await self.catalog.create_skill(body.id, body.label, list(body.specializations))
        await self._catalog_audit(
            "catalog_created", "skill", body.id, f"Добавлена технология «{body.label}»"
        )
        return skill

    async def update_skill(self, skill_id: str, body: SkillUpsert) -> Record:
        if body.id != skill_id:
            raise AppError(
                422, "id_mismatch", "Код технологии менять нельзя", {"id": skill_id, "new": body.id}
            )
        skill = await self.catalog.update_skill(skill_id, body.label, list(body.specializations))
        await self._catalog_audit(
            "catalog_updated", "skill", skill_id, f"Изменена технология «{body.label}»"
        )
        return skill

    async def delete_skill(self, skill_id: str) -> None:
        skill = await self.catalog.delete_skill(skill_id)
        await self._catalog_audit(
            "catalog_deleted", "skill", skill_id, f"Удалена технология «{skill['label']}»"
        )

    async def create_specialization(self, body: SpecializationCreate) -> Record:
        spec = await self.catalog.create_specialization(body.id, body.label, body.description)
        await self._catalog_audit(
            "catalog_created", "specialization", body.id, f"Добавлена специализация «{body.label}»"
        )
        return spec

    async def update_specialization(self, spec_id: str, body: CatalogLabelUpdate) -> Record:
        spec = await self.catalog.update_specialization(
            spec_id, body.label, body.description, body.active
        )
        await self._catalog_audit(
            "catalog_updated",
            "specialization",
            spec_id,
            f"Изменена специализация «{body.label}»",
            body.model_dump(exclude_none=True),
        )
        return spec

    async def delete_specialization(self, spec_id: str) -> None:
        spec = await self.catalog.delete_specialization(spec_id)
        await self._catalog_audit(
            "catalog_deleted", "specialization", spec_id, f"Удалена специализация «{spec['label']}»"
        )

    async def update_grade(self, grade_id: str, label: str) -> Record:
        grade = await self.catalog.update_grade(grade_id, label)
        await self._catalog_audit(
            "catalog_updated", "grade", grade_id, f"Изменена подпись грейда: {label}"
        )
        return grade

    async def update_category(self, category_id: str, label: str) -> Record:
        category = await self.catalog.update_category(category_id, label)
        await self._catalog_audit(
            "catalog_updated", "category", category_id, f"Изменена подпись категории: {label}"
        )
        return category

    async def create_topic(self, body: TopicCreate) -> Record:
        topic = await self.catalog.create_topic(body.id, body.specialization, body.label)
        await self._catalog_audit(
            "catalog_created", "topic", body.id, f"Добавлена тема «{body.label}»"
        )
        return topic

    async def update_topic(self, topic_id: str, label: str) -> Record:
        topic = await self.catalog.update_topic(topic_id, label)
        await self._catalog_audit("catalog_updated", "topic", topic_id, f"Изменена тема «{label}»")
        return topic

    async def delete_topic(self, topic_id: str) -> None:
        topic = await self.catalog.delete_topic(topic_id)
        await self._catalog_audit(
            "catalog_deleted", "topic", topic_id, f"Удалена тема «{topic['label']}»"
        )
