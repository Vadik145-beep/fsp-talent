"""Кабинет администратора: дашборд, пользователи, компании, настройки, банк задач,
задания из вакансий, жалобы, журнал."""

from datetime import date, datetime
from typing import Any

from pydantic import ConfigDict, Field

from app.common import fixtures
from app.common.enums import (
    GradeCode,
    InvitationStatus,
    ItemFormat,
    ItemSource,
    ItemStatus,
    ReportReason,
    ReportStatus,
    Role,
    SpecializationCode,
)
from app.common.schemas import ApiModel, OutModel
from app.companies.schemas import Company
from app.testing.schemas import AnswerPayload, ItemView

# ---------- дашборд ----------


class DayCount(OutModel):
    date: date
    count: int


class LeakFlagBrief(OutModel):
    item_id: int
    title: str
    specialization: SpecializationCode
    leak_score: float


class AdminDashboard(OutModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "users_by_role": {"candidate": 40, "recruiter": 7, "admin": 2},
                    "tests_total": 52,
                    "tests_by_day": [{"date": "2026-10-01", "count": 4}],
                    "invitations_by_status": {"sent": 4, "accepted": 5},
                    "invite_to_accept_conversion": 0.31,
                    "leak_flags": [],
                    "open_reports": 2,
                }
            ]
        }
    )

    users_by_role: dict[Role, int]
    tests_total: int
    tests_by_day: list[DayCount]
    invitations_by_status: dict[InvitationStatus, int]
    invite_to_accept_conversion: float = Field(ge=0, le=1)
    leak_flags: list[LeakFlagBrief]
    open_reports: int


# ---------- пользователи и компании ----------


class AdminUserUpdate(ApiModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"blocked": True}]})

    role: Role | None = Field(default=None, description="Повысить до админа может только админ")
    blocked: bool | None = None


class AuditEntry(OutModel):
    """Запись журнала действий (запись `audit_log.json`)."""

    model_config = ConfigDict(json_schema_extra=fixtures.first_example("audit_log"))

    id: int
    at: datetime
    actor_user_id: int | None
    actor_role: Role | None
    action: str = Field(examples=["contacts_revealed"])
    target_type: str = Field(examples=["invitation"])
    target_id: int | None = None
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)


class AdminCompany(Company):
    recruiters_count: int
    invitations_sent: int
    response_rate: float = Field(ge=0, le=1, description="Доля приглашений с ответом")
    reports_count: int


class CompanyAdminUpdate(ApiModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"blocked": True}]})

    blocked: bool


# ---------- справочники и настройки ----------


class GradeThreshold(OutModel):
    """Пороги θ для грейдов в специализации: ниже junior_from — стажёр."""

    specialization: SpecializationCode
    junior_from: float
    middle_from: float
    senior_from: float


class RankingWeights(OutModel):
    stack: float = Field(ge=0)
    theta: float = Field(ge=0)
    fsp: float = Field(ge=0)
    freshness: float = Field(ge=0)
    salary: float = Field(ge=0)
    work_format: float = Field(ge=0)


class PlatformSettings(OutModel):
    """Настройки платформы (запись `platform_settings.json`, id = "default")."""

    model_config = ConfigDict(json_schema_extra=fixtures.first_example("platform_settings"))

    id: str = "default"
    grade_thresholds: list[GradeThreshold]
    grade_change_cooldown_days: int = Field(ge=0)
    retry_cooldown_days: int = Field(ge=0)
    invitation_quota: int = Field(ge=1)
    invitation_ttl_days: int = Field(ge=1)
    cat_se_stop: float = Field(gt=0)
    cat_max_items: int = Field(ge=1)
    exposure_max_share: float = Field(gt=0, le=1)
    ranking_weights: RankingWeights
    consent_version: str


class PlatformSettingsUpdate(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"invitation_quota": 25, "grade_change_cooldown_days": 90}]}
    )

    grade_thresholds: list[GradeThreshold] | None = None
    grade_change_cooldown_days: int | None = Field(default=None, ge=0, le=365)
    retry_cooldown_days: int | None = Field(default=None, ge=0, le=365)
    invitation_quota: int | None = Field(default=None, ge=1, le=500)
    invitation_ttl_days: int | None = Field(default=None, ge=1, le=60)
    cat_se_stop: float | None = Field(default=None, gt=0, le=2)
    cat_max_items: int | None = Field(default=None, ge=5, le=50)
    exposure_max_share: float | None = Field(default=None, gt=0, le=1)
    ranking_weights: RankingWeights | None = None


class SkillUpsert(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"id": "rust", "label": "Rust", "specializations": ["backend"]}]
        }
    )

    id: str = Field(pattern=r"^[a-z0-9_+.#-]+$", max_length=40)
    label: str = Field(min_length=1, max_length=60)
    specializations: list[SpecializationCode] = Field(min_length=1)


class CatalogLabelUpdate(ApiModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"label": "Data Science / ML"}]})

    label: str = Field(min_length=1, max_length=60)
    description: str | None = Field(default=None, max_length=500)
    active: bool | None = None


class SpecializationCreate(ApiModel):
    """Вернуть специализацию в справочник (коды фиксированы общими соглашениями)."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"id": "qa", "label": "QA", "description": "Тестирование"}]}
    )

    id: SpecializationCode
    label: str = Field(min_length=1, max_length=60)
    description: str = Field(default="", max_length=500)


class LabelUpdate(ApiModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"label": "Backend · Middle"}]})

    label: str = Field(min_length=1, max_length=120)


class TopicCreate(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"id": "backend.caching", "specialization": "backend", "label": "Кэширование"}
            ]
        }
    )

    id: str = Field(pattern=r"^[a-z_]+\.[a-z0-9_]+$", max_length=64)
    specialization: SpecializationCode
    label: str = Field(min_length=1, max_length=120)


# ---------- банк задач ----------


class ItemVariantPreview(ItemView):
    """Вариант шаблона для админа — с правильным ответом и seed."""

    seed: int
    correct_answer: AnswerPayload


class ItemSummary(OutModel):
    """Строка банка задач с метриками."""

    id: int
    code: str = Field(examples=["be-db-001"])
    title: str
    specialization: SpecializationCode
    topic: str
    topic_label: str
    target_grade: GradeCode
    format: ItemFormat
    a: float = Field(gt=0, description="Различающая сила (IRT)")
    b: float = Field(description="Сложность (IRT)")
    status: ItemStatus
    source: ItemSource
    exposures: int = Field(ge=0, description="Сколько раз показан")
    correct_rate: float | None = Field(default=None, ge=0, le=1)
    expected_correct_rate: float | None = Field(default=None, ge=0, le=1)
    leak_flag: bool
    leak_score: float = Field(ge=0, description="Насколько доля верных выше ожидаемой (z)")
    variants_count: int = Field(ge=1, description="Сколько различных вариантов даёт шаблон")
    created_at: datetime


class ItemDetail(ItemSummary):
    """Шаблон задачи (запись `items.json`) с предпросмотром 3 вариантов."""

    model_config = ConfigDict(json_schema_extra=fixtures.first_example("items"))

    description: str
    preview_variants: list[ItemVariantPreview]


class CoverageCell(OutModel):
    specialization: SpecializationCode
    topic: str
    topic_label: str
    grade: GradeCode
    active: int
    pilot: int


class CalibrationChange(OutModel):
    item_id: int
    a_before: float
    a_after: float
    b_before: float
    b_after: float


class RecalibrationResult(OutModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "started_at": "2026-10-06T12:00:00+03:00",
                    "items_recalibrated": 24,
                    "pilot_promoted": 2,
                    "changes": [
                        {
                            "item_id": 1,
                            "a_before": 1.1,
                            "a_after": 1.18,
                            "b_before": 0.2,
                            "b_after": 0.27,
                        }
                    ],
                }
            ]
        }
    )

    started_at: datetime
    items_recalibrated: int
    pilot_promoted: int
    changes: list[CalibrationChange]


class VacancyTestRequest(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "text": "Ищем Middle Python-разработчика: FastAPI, PostgreSQL, Redis, Docker.",
                    "specialization": None,
                }
            ]
        }
    )

    text: str = Field(min_length=20, max_length=20000)
    specialization: SpecializationCode | None = None


class DetectedTopic(OutModel):
    topic: str
    label: str
    matched_by: list[str] = Field(description="Слова из текста, по которым найдена тема")
    confidence: float = Field(ge=0, le=1)
    covered: bool = Field(description="Есть ли активные шаблоны по теме в банке")


class SelectedItem(OutModel):
    item_id: int
    code: str
    title: str
    topic: str
    reason: str


class ItemDraft(OutModel):
    """Черновик нового шаблона для темы, которой нет в банке (LLM или словарь тем)."""

    topic: str
    label: str
    title: str
    format: ItemFormat
    prompt: str
    status: ItemStatus = ItemStatus.draft


class VacancyTestResult(OutModel):
    """Задание из вакансии (запись `vacancy_tests.json`): темы → тест → объяснение."""

    model_config = ConfigDict(json_schema_extra=fixtures.first_example("vacancy_tests"))

    id: int
    vacancy_title: str
    vacancy_text: str
    specialization: SpecializationCode
    grade: GradeCode
    parser: str = Field(description="rules | llm")
    topics: list[DetectedTopic]
    items: list[SelectedItem]
    drafts: list[ItemDraft]
    explanation: list[str]


# ---------- жалобы ----------


class ReportCreate(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "company_id": 3,
                    "invitation_id": 12,
                    "reason": "fake_vacancy",
                    "text": "После принятия попросили оплатить обучение.",
                }
            ]
        }
    )

    company_id: int
    invitation_id: int | None = None
    vacancy_id: int | None = None
    reason: ReportReason
    text: str = Field(min_length=5, max_length=3000)


class Report(OutModel):
    """Жалоба кандидата на работодателя (запись `reports.json`)."""

    model_config = ConfigDict(json_schema_extra=fixtures.first_example("reports"))

    id: int
    company_id: int
    company_name: str
    reporter_candidate_id: int
    invitation_id: int | None = None
    vacancy_id: int | None = None
    reason: ReportReason
    text: str
    status: ReportStatus
    resolution: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None


class ReportUpdate(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"status": "resolved", "resolution": "Компания заблокирована"}]
        }
    )

    status: ReportStatus
    resolution: str | None = Field(default=None, max_length=2000)
