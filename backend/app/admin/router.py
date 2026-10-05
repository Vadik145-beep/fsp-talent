"""Кабинет администратора + приём жалоб от соискателей (`POST /api/reports`)."""

from typing import Annotated, Any

from fastapi import APIRouter, Query, Response, status

from app.admin.schemas import (
    AdminCompany,
    AdminDashboard,
    AdminUserUpdate,
    AuditEntry,
    CatalogLabelUpdate,
    CompanyAdminUpdate,
    CoverageCell,
    ItemDetail,
    ItemSummary,
    PlatformSettings,
    PlatformSettingsUpdate,
    RecalibrationResult,
    Report,
    ReportCreate,
    ReportUpdate,
    SkillUpsert,
    VacancyTestRequest,
    VacancyTestResult,
)
from app.admin.service import AdminService
from app.catalog.schemas import Grade, Skill, Specialization
from app.common.enums import GradeCode, ItemStatus, ReportStatus, Role, SpecializationCode
from app.common.schemas import Page
from app.core.errors import AppError, error_responses, not_found
from app.core.security import AdminUser, CandidateUser
from app.users.schemas import UserRecord

router = APIRouter(prefix="/admin", tags=["admin"])
reports_router = APIRouter(prefix="/reports", tags=["admin"])
service = AdminService()

AUTH = (401, 403)
TRANSITION = (409, "invalid_transition", "Действие недоступно в текущем статусе")
PageNum = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=200)]


@router.get(
    "/dashboard",
    response_model=AdminDashboard,
    summary="Дашборд платформы",
    responses=error_responses(*AUTH),
)
async def dashboard(user: AdminUser) -> Any:
    return service.dashboard()


# ---------- пользователи и компании ----------


@router.get(
    "/users",
    response_model=Page[UserRecord],
    summary="Пользователи: поиск и фильтры",
    responses=error_responses(*AUTH, 422),
)
async def list_users(
    user: AdminUser,
    q: Annotated[str | None, Query(max_length=100, description="Почта или ФИО")] = None,
    role: Role | None = None,
    blocked: bool | None = None,
    page: PageNum = 1,
    page_size: PageSize = 50,
) -> Any:
    return service.users(q, role, blocked, page, page_size)


@router.patch(
    "/users/{user_id}",
    response_model=UserRecord,
    summary="Сменить роль или заблокировать пользователя",
    description="Повысить до админа может только админ. Заглушка: не сохраняется.",
    responses=error_responses(
        *AUTH, 404, (409, "cannot_change_self", "Нельзя заблокировать или понизить себя"), 422
    ),
)
async def update_user(user_id: int, body: AdminUserUpdate, user: AdminUser) -> Any:
    return service.update_user(user_id, body, user.user_id)


@router.get(
    "/users/{user_id}/audit",
    response_model=list[AuditEntry],
    summary="Журнал действий по пользователю",
    responses=error_responses(*AUTH, 404),
)
async def user_audit(user_id: int, user: AdminUser) -> Any:
    return service.user_audit(user_id)


@router.get(
    "/companies",
    response_model=list[AdminCompany],
    summary="Компании со скорингом надёжности",
    responses=error_responses(*AUTH),
)
async def list_companies(user: AdminUser) -> Any:
    return service.companies()


@router.patch(
    "/companies/{company_id}",
    response_model=AdminCompany,
    summary="Заблокировать / разблокировать компанию",
    responses=error_responses(*AUTH, 404, 422),
)
async def update_company(company_id: int, body: CompanyAdminUpdate, user: AdminUser) -> Any:
    return service.update_company(company_id, body.blocked)


# ---------- справочники и настройки ----------


@router.get(
    "/settings",
    response_model=PlatformSettings,
    summary="Настройки: пороги θ, кулдауны, квота, веса ранжирования",
    responses=error_responses(*AUTH),
)
async def get_settings(user: AdminUser) -> Any:
    return service.settings()


@router.put(
    "/settings",
    response_model=PlatformSettings,
    summary="Изменить настройки платформы",
    description="Передаются только меняемые поля. Заглушка: не сохраняется.",
    responses=error_responses(*AUTH, 422),
)
async def update_settings(body: PlatformSettingsUpdate, user: AdminUser) -> Any:
    return service.update_settings(body)


@router.post(
    "/catalog/skills",
    response_model=Skill,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить технологию в справочник стека",
    responses=error_responses(*AUTH, (409, "skill_exists", "Такая технология уже есть"), 422),
)
async def create_skill(body: SkillUpsert, user: AdminUser) -> Any:
    if any(s["id"] == body.id for s in service.repo.skills()):
        raise AppError(409, "skill_exists", "Такая технология уже есть", {"id": body.id})
    return body.model_dump()


@router.put(
    "/catalog/skills/{skill_id}",
    response_model=Skill,
    summary="Изменить технологию",
    responses=error_responses(*AUTH, 404, 422),
)
async def update_skill(skill_id: str, body: SkillUpsert, user: AdminUser) -> Any:
    if not any(s["id"] == skill_id for s in service.repo.skills()):
        raise not_found("skill", skill_id)
    return body.model_dump()


@router.delete(
    "/catalog/skills/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Удалить технологию",
    responses=error_responses(
        *AUTH, 404, (409, "skill_in_use", "Технология используется в профилях или вакансиях")
    ),
)
async def delete_skill(skill_id: str, user: AdminUser) -> Response:
    if not any(s["id"] == skill_id for s in service.repo.skills()):
        raise not_found("skill", skill_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/catalog/specializations/{spec_id}",
    response_model=Specialization,
    summary="Изменить подпись или активность специализации (код фиксирован)",
    responses=error_responses(*AUTH, 404, 422),
)
async def update_specialization(
    spec_id: SpecializationCode, body: CatalogLabelUpdate, user: AdminUser
) -> Any:
    spec = service.repo.specialization(spec_id)
    if spec is None:
        raise not_found("specialization", spec_id)
    return {**spec, **body.model_dump(exclude_none=True)}


@router.patch(
    "/catalog/grades/{grade_id}",
    response_model=Grade,
    summary="Изменить подпись грейда (код фиксирован)",
    responses=error_responses(*AUTH, 404, 422),
)
async def update_grade(grade_id: GradeCode, body: CatalogLabelUpdate, user: AdminUser) -> Any:
    grade = service.repo.grade(grade_id)
    if grade is None:
        raise not_found("grade", grade_id)
    return {**grade, "label": body.label}


# ---------- банк задач ----------


@router.get(
    "/items",
    response_model=Page[ItemSummary],
    summary="Банк задач с метриками",
    responses=error_responses(*AUTH, 422),
)
async def list_items(
    user: AdminUser,
    specialization: SpecializationCode | None = None,
    topic: str | None = None,
    item_status: Annotated[ItemStatus | None, Query(alias="status")] = None,
    leak_flag: bool | None = None,
    page: PageNum = 1,
    page_size: PageSize = 50,
) -> Any:
    return service.items(specialization, topic, item_status, leak_flag, page, page_size)


@router.get(
    "/items/coverage",
    response_model=list[CoverageCell],
    summary="Покрытие банка: темы × грейды",
    responses=error_responses(*AUTH),
)
async def items_coverage(user: AdminUser) -> Any:
    return service.coverage()


@router.post(
    "/items/recalibrate",
    response_model=RecalibrationResult,
    summary="Пересчитать калибровку a, b по накопленным ответам",
    description="Заглушка: настоящий пересчёт — волна 3a (T4.9).",
    responses=error_responses(*AUTH, (409, "recalibration_running", "Пересчёт уже идёт")),
)
async def recalibrate(user: AdminUser) -> Any:
    return service.recalibrate()


@router.get(
    "/items/{item_id}",
    response_model=ItemDetail,
    summary="Шаблон: метрики и предпросмотр 3 вариантов",
    responses=error_responses(*AUTH, 404),
)
async def get_item(item_id: int, user: AdminUser) -> Any:
    return service.item(item_id)


@router.post(
    "/items/{item_id}/retire",
    response_model=ItemDetail,
    summary="Вывести шаблон из оборота",
    responses=error_responses(*AUTH, 404, TRANSITION),
)
async def retire_item(item_id: int, user: AdminUser) -> Any:
    return service.retire_item(item_id)


@router.post(
    "/items/{item_id}/approve",
    response_model=ItemDetail,
    summary="Одобрить черновик → пилот (непроверочный)",
    responses=error_responses(*AUTH, 404, TRANSITION),
)
async def approve_item(item_id: int, user: AdminUser) -> Any:
    return service.approve_item(item_id)


# ---------- задания из вакансий ----------


@router.get(
    "/vacancy-tests",
    response_model=list[VacancyTestResult],
    summary="Примеры: тесты, собранные из вакансий",
    responses=error_responses(*AUTH),
)
async def list_vacancy_tests(user: AdminUser) -> Any:
    return service.vacancy_tests()


@router.post(
    "/vacancy-tests",
    response_model=VacancyTestResult,
    summary="Текст вакансии → темы → тест с объяснением",
    description="Заглушка: возвращает ближайший пример. Настоящий разбор — волна 3c (T4.8).",
    responses=error_responses(
        *AUTH, 422, (503, "llm_unavailable", "LLM недоступна, работаем по словарю")
    ),
)
async def build_vacancy_test(body: VacancyTestRequest, user: AdminUser) -> Any:
    return service.build_vacancy_test(body)


# ---------- жалобы и журнал ----------


@router.get(
    "/reports",
    response_model=list[Report],
    summary="Очередь жалоб на работодателей",
    responses=error_responses(*AUTH, 422),
)
async def list_reports(
    user: AdminUser,
    report_status: Annotated[ReportStatus | None, Query(alias="status")] = None,
) -> Any:
    return service.reports(report_status)


@router.patch(
    "/reports/{report_id}",
    response_model=Report,
    summary="Обработать жалобу",
    responses=error_responses(*AUTH, 404, 422),
)
async def update_report(report_id: int, body: ReportUpdate, user: AdminUser) -> Any:
    return service.update_report(report_id, body)


@router.get(
    "/audit",
    response_model=Page[AuditEntry],
    summary="Журнал действий",
    description="Раскрытие контактов, смены грейда, блокировки, вывод шаблонов и т.д.",
    responses=error_responses(*AUTH, 422),
)
async def audit_log(
    user: AdminUser,
    action: str | None = None,
    target_type: str | None = None,
    page: PageNum = 1,
    page_size: PageSize = 50,
) -> Any:
    return service.audit(action, target_type, page, page_size)


@reports_router.post(
    "",
    response_model=Report,
    status_code=status.HTTP_201_CREATED,
    summary="Пожаловаться на работодателя (соискатель)",
    responses=error_responses(*AUTH, 404, 422),
)
async def create_report(body: ReportCreate, user: CandidateUser) -> Any:
    if user.candidate_id is None:
        raise AppError(404, "not_found", "Профиль кандидата не найден")
    return service.create_report(body, user.candidate_id)
