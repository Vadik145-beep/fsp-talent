"""Вакансии и отклики на БД (E8): лента, CRUD своей компании, публикация, отклик, статусы, письма.

Правила [ТЗ 2.1, 2.2]:
- вилка от–до обязательна (от ≤ до), стек — только коды из справочника;
- рекрутер видит и меняет только вакансии и отклики своей компании (чужое → 404);
- кандидат видит опубликованные вакансии незаблокированных компаний; вакансию, на которую
  он уже откликнулся, — и после снятия с публикации; откликнуться можно только на опубликованную;
- один отклик кандидата на вакансию (повтор → 409 `already_applied`);
- кандидат откликнулся сам — компания сразу видит его контакты; раскрытие пишется в `audit_log`;
- статусы отклика `new → viewed → invited / rejected`, назад к `new`/`viewed` нельзя (409);
  `invited` ↔ `rejected` — исправление решения рекрутера;
- приглашая, рекрутер указывает способ связи (обязательно) и сообщение; кандидат видит их
  в отклике и в письме, пока статус `invited` [ТЗ 2.2 п.2 — как в приглашении];
- письма (рекрутерам — о новом отклике, кандидату — о смене статуса) роутер шлёт в фоне.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.admin.audit import write_audit
from app.candidates.service import to_card, to_contacts
from app.catalog.clock import as_msk, now_msk
from app.catalog.repository import CatalogDb
from app.common.enums import ApplicationStatus, ContactMethodType, Role, VacancyStatus
from app.common.fixtures import Record
from app.companies.antifraud import ensure_company_active
from app.companies.models import Company
from app.core.config import get_settings
from app.core.errors import AppError, not_found
from app.core.security import CurrentUser
from app.integrations.webhooks import notify_application_created
from app.matching.repository import CandidatePool
from app.vacancies.models import Application, Vacancy
from app.vacancies.repository import ApplicationRow, VacancyDb, VacancyRow
from app.vacancies.schemas import VacancyCreate

V = VacancyStatus
A = ApplicationStatus

# Переходы статусов вакансии. Недопустимый → 409 invalid_transition.
VACANCY_TRANSITIONS: dict[VacancyStatus, set[VacancyStatus]] = {
    V.draft: {V.published},
    V.published: {V.unpublished},
    V.unpublished: {V.published},
}
VACANCY_STATUS_LABELS = {
    V.draft: "Черновик",
    V.published: "Опубликована",
    V.unpublished: "Снята с публикации",
}
# Переходы статусов отклика (T8.3). Тот же статус — без изменений.
APPLICATION_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    A.new: {A.viewed, A.invited, A.rejected},
    A.viewed: {A.invited, A.rejected},
    A.invited: {A.rejected},
    A.rejected: {A.invited},
}
# Подписи — как в кабинете рекрутера
APPLICATION_STATUS_LABELS = {
    A.new: "Новый",
    A.viewed: "Просмотрен",
    A.invited: "Приглашён",
    A.rejected: "Отказ",
}
# Что пишем кандидату о смене статуса
CANDIDATE_STATUS_TEXT = {
    A.new: "отклик снова в статусе «Новый»",
    A.viewed: "работодатель посмотрел ваш отклик",
    A.invited: "работодатель приглашает вас пообщаться — ваши контакты у него есть",
    A.rejected: "работодатель выбрал другого кандидата",
}
CONTACT_TYPE_TEXT = {
    ContactMethodType.email: "почта",
    ContactMethodType.phone: "телефон",
    ContactMethodType.telegram: "Telegram",
    ContactMethodType.other: "контакт",
}


def can_publish_transition(current: VacancyStatus, target: VacancyStatus) -> bool:
    return target in VACANCY_TRANSITIONS[current]


def can_application_transition(current: ApplicationStatus, target: ApplicationStatus) -> bool:
    return target in APPLICATION_TRANSITIONS[current]


def clean_skills(codes: list[str]) -> list[str]:
    return list(dict.fromkeys(c.strip().lower() for c in codes if c.strip()))


def split_skills(values: list[str] | None) -> list[str]:
    """`skills=a&skills=b` и `skills=a,b` — одно и то же."""
    return clean_skills([part for v in values or [] for part in v.split(",")])


@dataclass
class Mail:
    to: str
    subject: str
    text: str


@dataclass
class VacancyFilters:
    specialization: str | None = None
    grade: str | None = None
    work_format: str | None = None
    skills: list[str] | None = None
    salary_min: int | None = None
    q: str | None = None


class VacancyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.db = VacancyDb(session)
        self.pool = CandidatePool(session)
        self.catalog = CatalogDb(session)
        # письма, которые роутер отправит после ответа (BackgroundTasks)
        self.outbox: list[Mail] = []

    # ---------- проекция вакансии ----------

    @staticmethod
    def _record(row: VacancyRow, applications_count: int) -> dict[str, Any]:
        v, company_name, category_label = row
        return {
            "id": v.id,
            "company_id": v.company_id,
            "company_name": company_name,
            "title": v.title,
            "description": v.description,
            "team_description": v.team_description or "",
            "specialization": v.specialization,
            "grade": v.grade,
            "category": v.category,
            "category_label": category_label or v.category,
            "skills_required": list(v.skills_required or []),
            "skills_desired": list(v.skills_desired or []),
            "work_format": v.work_format,
            "city": v.city,
            "salary_from": v.salary_from,
            "salary_to": v.salary_to,
            "status": v.status,
            "applications_count": applications_count,
            "created_at": as_msk(v.created_at),
            "published_at": as_msk(v.published_at),
            "my_application_id": None,
        }

    async def _views(self, rows: list[VacancyRow], user: CurrentUser) -> list[dict[str, Any]]:
        ids = [r[0].id for r in rows]
        counts = await self.db.applications_count(ids)
        data = [self._record(r, counts.get(r[0].id, 0)) for r in rows]
        if user.role == Role.candidate and user.candidate_id is not None:
            mine = await self.db.my_applications(user.candidate_id, ids)
            for d in data:
                d["my_application_id"] = mine.get(d["id"])
        return data

    async def _view(self, vacancy_id: int, user: CurrentUser) -> dict[str, Any]:
        row = await self.db.row(vacancy_id)
        assert row is not None
        return (await self._views([row], user))[0]

    # ---------- доступ ----------

    async def _own(self, vacancy_id: int, user: CurrentUser) -> Vacancy:
        """Вакансия своей компании (рекрутер). Чужая неотличима от несуществующей."""
        vacancy = await self.db.get(vacancy_id)
        if vacancy is None or user.company_id is None or vacancy.company_id != user.company_id:
            raise not_found("vacancy", vacancy_id)
        return vacancy

    async def _candidate_can_see(self, vacancy: Vacancy, user: CurrentUser) -> bool:
        if user.candidate_id is not None and await self.db.application_of(
            vacancy.id, user.candidate_id
        ):
            return True  # свой отклик — карточку видно и после снятия с публикации
        if vacancy.status != V.published:
            return False
        company = await self.db.company(vacancy.company_id)
        return company is not None and not company.blocked

    # ---------- лента и списки ----------

    @staticmethod
    def _conditions(user: CurrentUser, f: VacancyFilters) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        if user.role == Role.recruiter:
            conditions.append(Vacancy.company_id == (user.company_id or -1))
        else:
            conditions += [Vacancy.status == V.published.value, Company.blocked.is_(False)]
        if f.specialization:
            conditions.append(Vacancy.specialization == f.specialization)
        if f.grade:
            conditions.append(Vacancy.grade == f.grade)
        if f.work_format:
            conditions.append(Vacancy.work_format == f.work_format)
        for skill in split_skills(f.skills):
            # все перечисленные навыки — в обязательном или желательном стеке
            conditions.append(
                or_(
                    Vacancy.skills_required.contains([skill]),
                    Vacancy.skills_desired.contains([skill]),
                )
            )
        if f.salary_min:
            conditions.append(Vacancy.salary_to >= f.salary_min)
        needle = (f.q or "").strip()
        if needle:
            pattern = f"%{needle}%"
            conditions.append(
                or_(
                    Vacancy.title.ilike(pattern),
                    Vacancy.description.ilike(pattern),
                    Company.name.ilike(pattern),
                )
            )
        return conditions

    async def list_for(
        self,
        user: CurrentUser,
        filters: VacancyFilters,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """(страница вакансий, всего по фильтрам)."""
        if user.role not in (Role.candidate, Role.recruiter):
            return [], 0
        conditions = self._conditions(user, filters)
        if user.role == Role.recruiter:
            order = [Vacancy.created_at.desc(), Vacancy.id.desc()]
        else:
            shown_at = func.coalesce(Vacancy.published_at, Vacancy.created_at)
            order = [shown_at.desc(), Vacancy.id.desc()]
        total = await self.db.count(conditions)
        rows = await self.db.rows(conditions, order, limit=limit, offset=offset)
        return await self._views(rows, user), total

    async def get(self, vacancy_id: int, user: CurrentUser) -> dict[str, Any]:
        if user.role == Role.recruiter:
            await self._own(vacancy_id, user)
        else:
            vacancy = await self.db.get(vacancy_id)
            if vacancy is None or not await self._candidate_can_see(vacancy, user):
                raise not_found("vacancy", vacancy_id)
        return await self._view(vacancy_id, user)

    # ---------- CRUD рекрутера ----------

    async def _apply_fields(self, vacancy: Vacancy, body: VacancyCreate) -> None:
        required = clean_skills(body.skills_required)
        desired = [s for s in clean_skills(body.skills_desired) if s not in required]
        codes = required + desired
        known = await self.catalog.existing_skill_codes(codes)
        unknown = [c for c in codes if c not in known]
        if unknown:
            raise AppError(
                422,
                "unknown_skills",
                "Технологий нет в справочнике стека — выберите из списка",
                {"skills": unknown},
            )
        category = f"{body.specialization}:{body.grade}"
        if await self.catalog.category(category) is None:
            raise AppError(
                422,
                "unknown_category",
                "Такой категории нет в справочнике",
                {"fields": {"grade": "Выберите грейд из списка"}},
            )
        vacancy.title = body.title.strip()
        vacancy.description = body.description.strip()
        vacancy.team_description = body.team_description.strip()
        vacancy.specialization = str(body.specialization)
        vacancy.grade = str(body.grade)
        vacancy.category = category
        vacancy.skills_required = required
        vacancy.skills_desired = desired
        vacancy.work_format = str(body.work_format)
        vacancy.city = (body.city or "").strip() or None
        vacancy.salary_from = body.salary_from
        vacancy.salary_to = body.salary_to

    async def create(self, body: VacancyCreate, user: CurrentUser) -> dict[str, Any]:
        if user.company_id is None:
            raise AppError(404, "not_found", "Компания не найдена")
        await ensure_company_active(self.session, user.company_id)
        vacancy = Vacancy(company_id=user.company_id, status=V.draft.value, created_at=now_msk())
        await self._apply_fields(vacancy, body)
        self.session.add(vacancy)
        await self.session.commit()
        return await self._view(vacancy.id, user)

    async def update(
        self, vacancy_id: int, body: VacancyCreate, user: CurrentUser
    ) -> dict[str, Any]:
        vacancy = await self._own(vacancy_id, user)
        await self._apply_fields(vacancy, body)
        await self.session.commit()
        return await self._view(vacancy_id, user)

    async def set_published(
        self, vacancy_id: int, user: CurrentUser, published: bool
    ) -> dict[str, Any]:
        vacancy = await self._own(vacancy_id, user)
        current = VacancyStatus(vacancy.status)
        target = V.published if published else V.unpublished
        if not can_publish_transition(current, target):
            message = "Вакансия уже опубликована" if published else "Вакансия не опубликована"
            raise AppError(
                409,
                "invalid_transition",
                f"{message} (сейчас: «{VACANCY_STATUS_LABELS[current]}»)",
                {"from": current.value, "to": target.value},
            )
        if published:
            await ensure_company_active(self.session, vacancy.company_id)
        vacancy.status = target.value
        if published:
            vacancy.published_at = now_msk()
        await self.session.commit()
        return await self._view(vacancy_id, user)

    # ---------- проекция отклика ----------

    @staticmethod
    def _app_record(row: ApplicationRow) -> dict[str, Any]:
        app, vacancy, company_name = row
        return {
            "id": app.id,
            "vacancy_id": app.vacancy_id,
            "candidate_id": app.candidate_id,
            "vacancy_title": vacancy.title,
            "company_id": vacancy.company_id,
            "company_name": company_name,
            "cover_letter": app.cover_letter or "",
            "status": app.status,
            "contact_method": (
                {"type": app.contact_type, "value": app.contact_value}
                if app.contact_type and app.contact_value
                else None
            ),
            "invite_message": app.invite_message or None,
            "created_at": as_msk(app.created_at),
            "updated_at": as_msk(app.updated_at),
            "candidate": None,
            "candidate_contacts": None,
        }

    async def _app_views(self, rows: list[ApplicationRow], role: Role) -> list[dict[str, Any]]:
        """Отклики для API пачкой. Рекрутеру — карточка (категория, θ, темы теста) и контакты:
        кандидат откликнулся сам [ТЗ 2.1]. Кандидату — только сам отклик, а способ связи
        и сообщение рекрутера — пока его приглашают (после отказа их не видно)."""
        data = [self._app_record(r) for r in rows]
        if role != Role.recruiter:
            for d in data:
                if d["status"] != A.invited:
                    d["contact_method"] = None
                    d["invite_message"] = None
        if role == Role.recruiter:
            cands = await self.pool.records(list({d["candidate_id"] for d in data}))
            for d in data:
                cand = cands.get(d["candidate_id"])
                if cand is not None:
                    d["candidate"] = to_card(cand)
                    d["candidate_contacts"] = to_contacts(cand)
        return data

    async def _app_view(self, application_id: int, role: Role) -> dict[str, Any]:
        row = await self.db.application_row(application_id)
        assert row is not None
        return (await self._app_views([row], role))[0]

    # ---------- отклики ----------

    async def list_applications(self, user: CurrentUser) -> list[dict[str, Any]]:
        if user.role == Role.recruiter:
            condition = Vacancy.company_id == (user.company_id or -1)
        elif user.role == Role.candidate:
            condition = Application.candidate_id == (user.candidate_id or -1)
        else:
            return []
        return await self._app_views(await self.db.application_rows(condition), user.role)

    async def vacancy_applications(
        self, vacancy_id: int, user: CurrentUser
    ) -> list[dict[str, Any]]:
        await self._own(vacancy_id, user)
        rows = await self.db.application_rows(Application.vacancy_id == vacancy_id)
        return await self._app_views(rows, Role.recruiter)

    async def apply(self, vacancy_id: int, user: CurrentUser, cover_letter: str) -> dict[str, Any]:
        if user.candidate_id is None:
            raise AppError(404, "not_found", "Профиль соискателя не найден")
        vacancy = await self.db.get(vacancy_id)
        if vacancy is None or not await self._candidate_can_see(vacancy, user):
            raise not_found("vacancy", vacancy_id)
        existing = await self.db.application_of(vacancy_id, user.candidate_id)
        if existing is not None:
            raise self._already_applied(existing.id)
        now = now_msk()
        app = Application(
            vacancy_id=vacancy_id,
            candidate_id=user.candidate_id,
            cover_letter=cover_letter.strip(),
            status=A.new.value,
            created_at=now,
            updated_at=now,
        )
        self.session.add(app)
        try:
            await self.session.flush()
        except IntegrityError:
            # параллельный повторный отклик упёрся в уникальность (vacancy_id, candidate_id)
            await self.session.rollback()
            again = await self.db.application_of(vacancy_id, user.candidate_id)
            raise self._already_applied(again.id if again else None) from None
        cand = (await self.pool.records([user.candidate_id])).get(user.candidate_id) or {}
        company = await self.db.company(vacancy.company_id)
        company_name = company.name if company else ""
        await write_audit(
            self.session,
            user,
            "contacts_revealed",
            "application",
            app.id,
            f"Отклик: контакты {cand.get('pseudonym', 'кандидата')} открыты «{company_name}»",
            {
                "candidate_id": user.candidate_id,
                "company_id": vacancy.company_id,
                "vacancy_id": vacancy_id,
            },
        )
        await self.session.commit()
        await self._notify_recruiters(vacancy, app, cand)
        await notify_application_created(self.session, app.id)  # вебхук ATS компании
        return await self._app_view(app.id, Role.candidate)

    @staticmethod
    def _already_applied(application_id: int | None) -> AppError:
        return AppError(
            409,
            "already_applied",
            "Вы уже откликнулись на эту вакансию",
            {"application_id": application_id} if application_id else {},
        )

    async def update_application(
        self,
        application_id: int,
        user: CurrentUser,
        new_status: ApplicationStatus,
        contact: tuple[ContactMethodType, str] | None = None,
        message: str = "",
    ) -> dict[str, Any]:
        row = await self.db.application_row(application_id)
        if row is None or user.company_id is None or row[1].company_id != user.company_id:
            raise not_found("application", application_id)
        app, vacancy, company_name = row
        current = ApplicationStatus(app.status)
        if current == new_status:
            return await self._app_view(application_id, Role.recruiter)
        if not can_application_transition(current, new_status):
            raise AppError(
                409,
                "invalid_transition",
                f"Нельзя вернуть отклик из статуса «{APPLICATION_STATUS_LABELS[current]}» "
                f"в «{APPLICATION_STATUS_LABELS[new_status]}»",
                {"from": current.value, "to": new_status.value},
            )
        if new_status == A.invited:
            if contact is None or len(contact[1].strip()) < 2:
                raise AppError(
                    422,
                    "validation_error",
                    "Укажите способ связи — кандидат увидит его в отклике",
                    {"fields": {"contact_method": "Укажите контакт для связи"}},
                )
            app.contact_type = contact[0].value
            app.contact_value = contact[1].strip()
            app.invite_message = message.strip()
        app.status = new_status.value
        app.updated_at = now_msk()
        await self.session.commit()
        await self._notify_candidate(app, vacancy, company_name)
        return await self._app_view(application_id, Role.recruiter)

    # ---------- письма ----------

    async def _notify_recruiters(self, vacancy: Vacancy, app: Application, cand: Record) -> None:
        emails = await self.db.recruiter_emails(vacancy.company_id)
        if not emails:
            return
        name = cand.get("full_name") or cand.get("pseudonym") or "Кандидат"
        category = cand.get("category_label") or "категория не определена"
        link = f"{get_settings().public_frontend_url}/recruiter/vacancies/{vacancy.id}"
        letter = f"\n\nСопроводительное письмо:\n{app.cover_letter}" if app.cover_letter else ""
        contacts = ", ".join(
            v for v in (cand.get("email"), cand.get("phone"), cand.get("telegram")) if v
        )
        for to in emails:
            self.outbox.append(
                Mail(
                    to=to,
                    subject=f"Новый отклик на вакансию «{vacancy.title}»",
                    text=(
                        f"Здравствуйте!\n\n{name} ({category}) откликнулся на вакансию "
                        f"«{vacancy.title}».{letter}\n\n"
                        f"Контакты: {contacts}.\n\nОтклики: {link}\n— ФСП · Таланты"
                    ),
                )
            )

    async def _notify_candidate(self, app: Application, vacancy: Vacancy, company: str) -> None:
        cand = (await self.pool.records([app.candidate_id])).get(app.candidate_id) or {}
        if not cand.get("email"):
            return
        status = ApplicationStatus(app.status)
        link = f"{get_settings().public_frontend_url}/candidate/applications"
        extra = ""
        if status == A.invited and app.contact_type and app.contact_value:
            kind = CONTACT_TYPE_TEXT.get(ContactMethodType(app.contact_type), "контакт")
            extra = f"\n\nКак связаться с рекрутером ({kind}): {app.contact_value}"
            if app.invite_message:
                extra += f"\nСообщение рекрутера: {app.invite_message}"
        self.outbox.append(
            Mail(
                to=cand["email"],
                subject=f"Отклик на «{vacancy.title}»: {APPLICATION_STATUS_LABELS[status]}",
                text=(
                    f"Здравствуйте!\n\nВаш отклик на вакансию «{vacancy.title}» "
                    f"в компании «{company}»: {CANDIDATE_STATUS_TEXT[status]}.{extra}\n\n"
                    f"Мои отклики: {link}\n— ФСП · Таланты"
                ),
            )
        )


__all__ = [
    "APPLICATION_TRANSITIONS",
    "VACANCY_TRANSITIONS",
    "Mail",
    "VacancyFilters",
    "VacancyService",
]
