"""Кабинет администратора + приём жалоб от соискателей (`POST /api/reports`).

Всё на БД: дашборд, пользователи, компании, справочники, настройки и журнал —
`AdminDbService`; жалобы — `ReportService`. Каждое действие админа пишется в журнал.
"""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.db_service import AdminDbService
from app.admin.schemas import (
    AdminCompany,
    AdminDashboard,
    AdminUserUpdate,
    AuditEntry,
    CatalogLabelUpdate,
    CompanyAdminUpdate,
    LabelUpdate,
    PlatformSettings,
    PlatformSettingsUpdate,
    Report,
    ReportCreate,
    SkillUpsert,
    SpecializationCreate,
    TopicCreate,
)
from app.admin.service import AdminService, ReportDecision, ReportService
from app.catalog.schemas import Category, Grade, Skill, Specialization, Topic
from app.common.enums import GradeCode, ReportStatus, Role, SpecializationCode
from app.common.schemas import Page
from app.core.db import get_session
from app.core.errors import AppError, error_responses
from app.core.security import AdminUser, CandidateUser
from app.users.schemas import UserRecord

router = APIRouter(prefix="/admin", tags=["admin"])
reports_router = APIRouter(prefix="/reports", tags=["admin"])
service = AdminService()  # демо-примеры тестов из вакансий — для vacancy_tests_router
PERIOD_DAYS = {"7d": 7, "30d": 30, "all": None}

AUTH = (401, 403)
TRANSITION = (409, "invalid_transition", "Действие недоступно в текущем статусе")
PageNum = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=200)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get(
    "/dashboard",
    response_model=AdminDashboard,
    summary="Дашборд платформы",
    description=(
        "Из БД: пользователи по ролям (почта подтверждена), завершённые тесты за период и по "
        "дням, приглашения по статусам, конверсия «приглашение → принятие» (без отозванных), "
        "открытые жалобы, флаги утечек шаблонов. `period` ограничивает только тесты."
    ),
    responses=error_responses(*AUTH, 422),
)
async def dashboard(
    user: AdminUser,
    session: SessionDep,
    period: Annotated[
        Literal["7d", "30d", "all"], Query(description="Период для тестов: 7d | 30d | all")
    ] = "all",
) -> Any:
    return await AdminDbService(session, user).dashboard(PERIOD_DAYS[period])


# ---------- пользователи и компании ----------


@router.get(
    "/users",
    response_model=Page[UserRecord],
    summary="Пользователи: поиск и фильтры",
    responses=error_responses(*AUTH, 422),
)
async def list_users(
    user: AdminUser,
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=100, description="Почта или ФИО")] = None,
    role: Role | None = None,
    blocked: bool | None = None,
    page: PageNum = 1,
    page_size: PageSize = 50,
) -> Any:
    return await AdminDbService(session, user).users(q, role, blocked, page, page_size)


@router.patch(
    "/users/{user_id}",
    response_model=UserRecord,
    summary="Сменить роль или заблокировать пользователя",
    description=(
        "Повысить до админа может только админ. Роль «соискатель» или «рекрутер» назначается, "
        "только если у пользователя есть профиль соискателя / он состоит в компании. "
        "Действие пишется в журнал."
    ),
    responses=error_responses(
        *AUTH,
        404,
        (409, "cannot_change_self", "Нельзя заблокировать или понизить себя"),
        (409, "role_profile_missing", "Нет профиля для этой роли"),
        422,
    ),
)
async def update_user(
    user_id: int, body: AdminUserUpdate, user: AdminUser, session: SessionDep
) -> Any:
    return await AdminDbService(session, user).update_user(user_id, body)


@router.get(
    "/users/{user_id}/audit",
    response_model=list[AuditEntry],
    summary="Журнал действий по пользователю",
    responses=error_responses(*AUTH, 404),
)
async def user_audit(user_id: int, user: AdminUser, session: SessionDep) -> Any:
    return await AdminDbService(session, user).user_audit(user_id)


@router.get(
    "/companies",
    response_model=list[AdminCompany],
    summary="Компании со скорингом надёжности",
    description=(
        "Скоринг 0..100: 30 + 50 × доля отвеченных приглашений (нет данных — 50), "
        "+10 за подтверждённый домен, −15 за подтверждённую жалобу, −5 за жалобу в работе."
    ),
    responses=error_responses(*AUTH),
)
async def list_companies(user: AdminUser, session: SessionDep) -> Any:
    return await AdminDbService(session, user).companies()


@router.patch(
    "/companies/{company_id}",
    response_model=AdminCompany,
    summary="Заблокировать / разблокировать компанию",
    responses=error_responses(*AUTH, 404, 422),
)
async def update_company(
    company_id: int, body: CompanyAdminUpdate, user: AdminUser, session: SessionDep
) -> Any:
    return await AdminDbService(session, user).update_company(company_id, body.blocked)


# ---------- справочники и настройки ----------


@router.get(
    "/settings",
    response_model=PlatformSettings,
    summary="Настройки: пороги θ, кулдауны, квота, веса ранжирования",
    responses=error_responses(*AUTH),
)
async def get_settings(user: AdminUser, session: SessionDep) -> Any:
    return await AdminDbService(session, user).settings()


@router.put(
    "/settings",
    response_model=PlatformSettings,
    summary="Изменить настройки платформы",
    description="Передаются только меняемые поля. Изменение пишется в журнал.",
    responses=error_responses(
        *AUTH,
        422,
        (422, "invalid_thresholds", "Пороги θ должны возрастать"),
        (422, "invalid_weights", "Хотя бы один вес больше нуля"),
    ),
)
async def update_settings(
    body: PlatformSettingsUpdate, user: AdminUser, session: SessionDep
) -> Any:
    return await AdminDbService(session, user).update_settings(body)


@router.post(
    "/catalog/skills",
    response_model=Skill,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить технологию в справочник стека",
    responses=error_responses(
        *AUTH,
        (409, "skill_exists", "Такая технология уже есть"),
        422,
        (422, "unknown_specialization", "Нет такой специализации"),
    ),
)
async def create_skill(body: SkillUpsert, user: AdminUser, session: SessionDep) -> Any:
    return await AdminDbService(session, user).create_skill(body)


@router.put(
    "/catalog/skills/{skill_id}",
    response_model=Skill,
    summary="Изменить технологию",
    responses=error_responses(*AUTH, 404, 422),
)
async def update_skill(
    skill_id: str, body: SkillUpsert, user: AdminUser, session: SessionDep
) -> Any:
    return await AdminDbService(session, user).update_skill(skill_id, body)


@router.delete(
    "/catalog/skills/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Удалить технологию",
    responses=error_responses(
        *AUTH, 404, (409, "skill_in_use", "Технология используется в профилях или вакансиях")
    ),
)
async def delete_skill(skill_id: str, user: AdminUser, session: SessionDep) -> Response:
    await AdminDbService(session, user).delete_skill(skill_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/catalog/specializations",
    response_model=Specialization,
    status_code=status.HTTP_201_CREATED,
    summary="Вернуть специализацию в справочник (код из фиксированного списка)",
    description="Вместе со специализацией создаются её категории (× все грейды).",
    responses=error_responses(
        *AUTH, (409, "specialization_exists", "Такая специализация уже есть"), 422
    ),
)
async def create_specialization(
    body: SpecializationCreate, user: AdminUser, session: SessionDep
) -> Any:
    return await AdminDbService(session, user).create_specialization(body)


@router.patch(
    "/catalog/specializations/{spec_id}",
    response_model=Specialization,
    summary="Изменить подпись или активность специализации (код фиксирован)",
    description="Подписи категорий этой специализации пересобираются автоматически.",
    responses=error_responses(*AUTH, 404, 422),
)
async def update_specialization(
    spec_id: SpecializationCode, body: CatalogLabelUpdate, user: AdminUser, session: SessionDep
) -> Any:
    return await AdminDbService(session, user).update_specialization(spec_id, body)


@router.delete(
    "/catalog/specializations/{spec_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Удалить специализацию",
    description=(
        "Нельзя, если по ней есть кандидаты, вакансии, потребности, шаблоны задач, тесты "
        "или приглашения — тогда её можно скрыть (`active = false`)."
    ),
    responses=error_responses(
        *AUTH, 404, (409, "specialization_in_use", "Специализация используется")
    ),
)
async def delete_specialization(
    spec_id: SpecializationCode, user: AdminUser, session: SessionDep
) -> Response:
    await AdminDbService(session, user).delete_specialization(spec_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/catalog/grades/{grade_id}",
    response_model=Grade,
    summary="Изменить подпись грейда (код фиксирован)",
    description="Подписи категорий этого грейда пересобираются автоматически.",
    responses=error_responses(*AUTH, 404, 422),
)
async def update_grade(
    grade_id: GradeCode, body: CatalogLabelUpdate, user: AdminUser, session: SessionDep
) -> Any:
    return await AdminDbService(session, user).update_grade(grade_id, body.label)


@router.patch(
    "/catalog/categories/{category_id}",
    response_model=Category,
    summary="Изменить подпись категории",
    responses=error_responses(*AUTH, 404, 422),
)
async def update_category(
    category_id: str, body: LabelUpdate, user: AdminUser, session: SessionDep
) -> Any:
    return await AdminDbService(session, user).update_category(category_id, body.label)


@router.post(
    "/catalog/topics",
    response_model=Topic,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить тему теста",
    responses=error_responses(
        *AUTH,
        404,
        (409, "topic_exists", "Такая тема уже есть"),
        422,
        (422, "topic_code_invalid", "Код темы — <специализация>.<тема>"),
    ),
)
async def create_topic(body: TopicCreate, user: AdminUser, session: SessionDep) -> Any:
    return await AdminDbService(session, user).create_topic(body)


@router.patch(
    "/catalog/topics/{topic_id}",
    response_model=Topic,
    summary="Изменить подпись темы",
    responses=error_responses(*AUTH, 404, 422),
)
async def update_topic(
    topic_id: str, body: LabelUpdate, user: AdminUser, session: SessionDep
) -> Any:
    return await AdminDbService(session, user).update_topic(topic_id, body.label)


@router.delete(
    "/catalog/topics/{topic_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Удалить тему",
    responses=error_responses(*AUTH, 404, (409, "topic_in_use", "По теме есть шаблоны задач")),
)
async def delete_topic(topic_id: str, user: AdminUser, session: SessionDep) -> Response:
    await AdminDbService(session, user).delete_topic(topic_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- жалобы и журнал ----------


@router.get(
    "/reports",
    response_model=list[Report],
    summary="Очередь жалоб на работодателей",
    responses=error_responses(*AUTH, 422),
)
async def list_reports(
    user: AdminUser,
    session: SessionDep,
    report_status: Annotated[ReportStatus | None, Query(alias="status")] = None,
) -> Any:
    return await ReportService(session, user).queue(report_status)


@router.patch(
    "/reports/{report_id}",
    response_model=Report,
    summary="Обработать жалобу",
    description=(
        "new → in_review (взять в работу) → resolved (подтвердить) | rejected (отклонить). "
        "`block_company: true` вместе с resolved блокирует компанию: её рекрутеры получают 403 "
        "`company_blocked`, вакансии скрываются. Подтверждённая жалоба снижает скоринг компании."
    ),
    responses=error_responses(
        *AUTH,
        404,
        TRANSITION,
        422,
        (422, "block_requires_resolve", "Заблокировать компанию можно только при подтверждении"),
    ),
)
async def update_report(
    report_id: int, body: ReportDecision, user: AdminUser, session: SessionDep
) -> Any:
    return await ReportService(session, user).decide(report_id, body)


@router.get(
    "/audit",
    response_model=Page[AuditEntry],
    summary="Журнал действий",
    description="Раскрытие контактов, смены грейда, блокировки, вывод шаблонов и т.д.",
    responses=error_responses(*AUTH, 422),
)
async def audit_log(
    user: AdminUser,
    session: SessionDep,
    action: str | None = None,
    target_type: str | None = None,
    page: PageNum = 1,
    page_size: PageSize = 50,
) -> Any:
    return await AdminDbService(session, user).audit(action, target_type, page, page_size)


@reports_router.post(
    "",
    response_model=Report,
    status_code=status.HTTP_201_CREATED,
    summary="Пожаловаться на работодателя (соискатель)",
    description="Только на компанию, с которой был контакт: приглашение, отклик или задание.",
    responses=error_responses(
        *AUTH,
        (403, "no_contact_with_company", "Не было контакта с компанией"),
        404,
        (409, "report_exists", "Жалоба на эту компанию уже на рассмотрении"),
        422,
    ),
)
async def create_report(body: ReportCreate, user: CandidateUser, session: SessionDep) -> Any:
    if user.candidate_id is None:
        raise AppError(404, "not_found", "Профиль кандидата не найден")
    return await ReportService(session, user).create(body, user.candidate_id)
