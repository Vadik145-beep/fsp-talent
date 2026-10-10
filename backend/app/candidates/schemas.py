"""Схемы кандидата.

Правила видимости [ТЗ 2.1, 2.2 п.2]:
- `CandidateProfile` — полный профиль, видит только сам кандидат (и система).
- `CandidateCard` / `AnonymousCandidateProfile` — то, что видит рекрутер: псевдоним вместо ФИО,
  ни почты, ни телефона, ни мессенджеров, ни минимальной зарплаты.
- `CandidateContacts` — отдельный объект; рекрутер получает его только после принятия
  приглашения или отклика кандидата на вакансию его компании, иначе поле `contacts` = null.
"""

from datetime import date, datetime

from pydantic import ConfigDict, Field

from app.common import fixtures
from app.common.enums import (
    FspLevel,
    GradeCode,
    GradeStatusCode,
    InvitationStatus,
    LinkType,
    SpecializationCode,
    TopicLevel,
    WorkFormat,
)
from app.common.schemas import ApiModel, OutModel

GRADE_STATUS_DESCRIPTION = (
    "confirmed — грейд подтверждён тестом; unconfirmed — грейд заявлен соискателем, "
    "тест не пройден (в выдачу работодателю не попадает); none — грейда нет"
)


class ProfileLink(OutModel):
    type: LinkType
    url: str = Field(examples=["https://github.com/example-user"])


class TopicScore(OutModel):
    """Результат теста по теме (без правильных ответов)."""

    topic: str = Field(examples=["backend.databases"])
    label: str = Field(examples=["Базы данных и SQL"])
    score: float = Field(ge=0, le=1, description="Доля освоения темы 0..1")
    level: TopicLevel


class FspBadge(OutModel):
    """Бейдж по достижениям ФСП, всегда с отметкой «подтверждено ФСП»."""

    id: str = Field(examples=["national_prize"])
    title: str = Field(examples=["Призёр всероссийского соревнования"])
    level: FspLevel | None = None
    verified: bool = True


class PrivacySettings(ApiModel):
    """Что видно работодателю до принятия приглашения [ТЗ 2.1 Настройки]."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "show_city": True,
                    "show_experience": True,
                    "show_links": False,
                    "show_fsp_achievements": True,
                }
            ]
        }
    )

    show_city: bool = True
    show_experience: bool = True
    show_links: bool = False
    show_fsp_achievements: bool = True


class CandidateContacts(OutModel):
    """ФИО и контакты — только после принятия приглашения или отклика."""

    full_name: str
    email: str
    phone: str | None = None
    telegram: str | None = None


class CandidateProfile(OutModel):
    """Полный профиль кандидата (запись `candidates.json`). Видит только сам кандидат."""

    model_config = ConfigDict(json_schema_extra=fixtures.first_example("candidates"))

    id: int
    user_id: int
    pseudonym: str = Field(examples=["Кандидат #A7F2"])
    full_name: str
    email: str
    phone: str | None = None
    telegram: str | None = None
    city: str | None = None
    work_formats: list[WorkFormat]
    specialization: SpecializationCode | None = None
    grade: GradeCode | None = Field(default=None, description="null — тест ещё не пройден")
    category: str | None = Field(default=None, examples=["backend:middle"])
    category_label: str | None = Field(default=None, examples=["Backend · Middle"])
    theta: float | None = Field(default=None, description="Оценка уровня θ (IRT)")
    theta_se: float | None = Field(default=None, description="Стандартная ошибка θ")
    topic_scores: list[TopicScore] = Field(default_factory=list)
    stack: list[str] = Field(description="Коды технологий из справочника `skills`")
    roles_in_team: list[str] = Field(default_factory=list)
    experience_years: float = Field(ge=0, le=60)
    soft_skills: list[str] = Field(default_factory=list)
    about: str = ""
    links: list[ProfileLink] = Field(default_factory=list)
    min_salary: int | None = Field(
        default=None, ge=0, description="Минимальная зарплата, ₽. Видна только системе"
    )
    fsp_id: str | None = Field(default=None, pattern=r"^FSP-\d{6}$")
    fsp_score: float | None = Field(default=None, ge=0, le=100)
    fsp_badges: list[FspBadge] = Field(default_factory=list)
    privacy: PrivacySettings
    job_search_paused: bool = False
    publication_consent: bool = Field(description="Без согласия на публикацию — нет в поиске")
    freshness: float = Field(ge=0, le=1, description="Свежесть профиля (регулярные задания)")
    profile_completeness: int = Field(ge=0, le=100)
    last_test_at: datetime | None = None
    grade_changed_at: datetime | None = None
    grade_status: GradeStatusCode = Field(
        default=GradeStatusCode.none, description=GRADE_STATUS_DESCRIPTION
    )
    grade_confirmed_at: datetime | None = Field(
        default=None, description="Когда грейд подтверждён тестом (null — не подтверждён)"
    )
    declared_specialization: SpecializationCode | None = Field(
        default=None, description="Специализация, которую соискатель выбрал сам"
    )
    declared_grade: GradeCode | None = Field(
        default=None,
        description="Грейд, заявленный соискателем. Не официальный: в выдачу не пускает",
    )
    declared_at: datetime | None = None
    created_at: datetime


class DeclaredGradeUpdate(ApiModel):
    """Заявить грейд (онбординг): статус «грейд не подтверждён» до прохождения теста."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"specialization": "backend", "grade": "middle"}]}
    )

    specialization: SpecializationCode
    grade: GradeCode


class CandidateProfileUpdate(ApiModel):
    """Редактирование своего профиля [ТЗ 2.1]."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "full_name": "Алексей Смирнов",
                    "phone": "+7 900 000-00-01",
                    "telegram": "@example_alexey",
                    "city": "Казань",
                    "work_formats": ["remote", "hybrid"],
                    "stack": ["python", "fastapi", "postgresql", "docker"],
                    "roles_in_team": ["Разработчик", "Ревьюер кода"],
                    "experience_years": 3.5,
                    "soft_skills": ["Коммуникация", "Самостоятельность"],
                    "about": "Пишу бэкенд на Python, люблю базы данных.",
                    "links": [{"type": "github", "url": "https://github.com/example-alexey"}],
                    "min_salary": 180000,
                }
            ]
        }
    )

    full_name: str = Field(min_length=2, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    telegram: str | None = Field(default=None, max_length=64)
    city: str | None = Field(default=None, max_length=100)
    work_formats: list[WorkFormat] = Field(min_length=1)
    stack: list[str] = Field(default_factory=list, max_length=40)
    roles_in_team: list[str] = Field(default_factory=list, max_length=10)
    experience_years: float = Field(ge=0, le=60)
    soft_skills: list[str] = Field(default_factory=list, max_length=15)
    about: str = Field(default="", max_length=3000)
    links: list[ProfileLink] = Field(default_factory=list, max_length=10)
    min_salary: int | None = Field(default=None, ge=0, le=10_000_000)


class ParsedField(OutModel):
    value: str | float | list[str] | None
    confidence: float = Field(ge=0, le=1)


class ResumeParseResult(OutModel):
    """Предзаполнение формы из PDF-резюме; кандидат подтверждает поля [ТЗ 2.1]."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "resume_id": 1,
                    "filename": "resume.pdf",
                    "parser": "rules",
                    "fields": {
                        "full_name": {"value": "Алексей Смирнов", "confidence": 0.95},
                        "email": {"value": "alexey.smirnov@example.com", "confidence": 0.99},
                        "stack": {"value": ["python", "postgresql"], "confidence": 0.8},
                    },
                    "unmatched_skills": ["Tornado"],
                }
            ]
        }
    )

    resume_id: int
    filename: str
    parser: str = Field(description="rules | llm")
    fields: dict[str, ParsedField]
    unmatched_skills: list[str] = Field(default_factory=list)


# ---------- то, что видит рекрутер ----------


class CandidateCard(OutModel):
    """Обезличенная карточка кандидата в выдаче и списках рекрутера.

    НЕ содержит ФИО, почту, телефон, мессенджеры, минимальную зарплату.
    Город, стаж, ссылки и бейджи ФСП — только если кандидат разрешил (privacy).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "pseudonym": "Кандидат #A7F2",
                    "specialization": "backend",
                    "grade": "middle",
                    "category": "backend:middle",
                    "category_label": "Backend · Middle",
                    "theta": 0.42,
                    "stack": ["python", "fastapi", "postgresql"],
                    "work_formats": ["remote"],
                    "roles_in_team": ["Разработчик"],
                    "city": "Казань",
                    "experience_years": 3.5,
                    "has_fsp": True,
                    "fsp_score": 61.5,
                    "fsp_badges": [
                        {
                            "id": "national_prize",
                            "title": "Призёр всероссийского соревнования",
                            "level": "national",
                            "verified": True,
                        }
                    ],
                    "topic_scores": [],
                    "freshness": 0.7,
                }
            ]
        }
    )

    id: int
    pseudonym: str
    specialization: SpecializationCode | None
    grade: GradeCode | None
    category: str | None
    category_label: str | None
    theta: float | None
    stack: list[str]
    work_formats: list[WorkFormat]
    roles_in_team: list[str]
    city: str | None = Field(default=None, description="null, если кандидат скрыл")
    experience_years: float | None = Field(default=None, description="null, если скрыт")
    links: list[ProfileLink] | None = Field(default=None, description="null, если скрыты")
    has_fsp: bool = Field(description="Привязан ли ФСП ID (без самого ID)")
    fsp_score: float | None = None
    fsp_badges: list[FspBadge] = Field(default_factory=list)
    topic_scores: list[TopicScore] = Field(default_factory=list)
    freshness: float


class TestHistoryPoint(OutModel):
    date: date
    category: str
    theta: float


class AnonymousCandidateProfile(CandidateCard):
    """Обезличенный профиль для рекрутера (`/recruiter/candidates/:id`).

    `contacts` заполнено только после принятия приглашения компании рекрутера
    или отклика кандидата на её вакансию.
    """

    soft_skills: list[str] = Field(default_factory=list)
    test_history: list[TestHistoryPoint] = Field(default_factory=list)
    invitation_id: int | None = Field(default=None, description="Приглашение от этой компании")
    invitation_status: InvitationStatus | None = None
    contacts_visible: bool
    contacts: CandidateContacts | None = None
    can_invite: bool = Field(description="Можно ли отправить приглашение сейчас")
    fsp_profile_note: str | None = Field(
        default=None,
        description=(
            "Лучшее достижение ФСП по профильной для специализации кандидата дисциплине; "
            "null — профильных достижений нет или кандидат скрыл достижения"
        ),
        examples=[
            "Призёр всероссийского соревнования по программированию систем ИБ, 2025 — "
            "профильно для DevOps"
        ],
    )


class CandidateSettings(OutModel):
    """Экран «Настройки» кандидата."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "privacy": PrivacySettings.model_json_schema()["examples"][0],
                    "job_search_paused": False,
                    "publication_consent": True,
                    "fsp_linked": True,
                    "fsp_id": "FSP-000001",
                }
            ]
        }
    )

    privacy: PrivacySettings
    job_search_paused: bool
    publication_consent: bool
    fsp_linked: bool
    fsp_id: str | None = None


class JobSearchUpdate(ApiModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"paused": True}]})

    paused: bool = Field(description="true — «не ищу работу», профиль скрыт из выдачи")


class DashboardInvitation(OutModel):
    id: int
    company_name: str
    salary_from: int
    salary_to: int
    status: InvitationStatus
    created_at: datetime


class DashboardTask(OutModel):
    submission_id: int
    title: str
    company_name: str | None = None
    due_at: datetime


class CandidateDashboard(OutModel):
    """Главная кандидата: категория, новые приглашения, задание, полнота профиля."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "full_name": "Алексей Смирнов",
                    "category": "backend:middle",
                    "category_label": "Backend · Middle",
                    "grade": "middle",
                    "theta": 0.42,
                    "onboarding_completed": True,
                    "new_invitations_count": 2,
                    "recent_invitations": [],
                    "active_task": None,
                    "task_offers": [],
                    "profile_completeness": 85,
                    "fsp_linked": True,
                    "hints": ["Добавьте ссылку на GitHub — профиль станет полнее"],
                }
            ]
        }
    )

    full_name: str
    category: str | None
    category_label: str | None
    grade: GradeCode | None
    theta: float | None
    grade_status: GradeStatusCode = Field(
        default=GradeStatusCode.none, description=GRADE_STATUS_DESCRIPTION
    )
    grade_confirmed_at: datetime | None = None
    declared_specialization: SpecializationCode | None = None
    declared_grade: GradeCode | None = None
    onboarding_completed: bool
    new_invitations_count: int
    recent_invitations: list[DashboardInvitation]
    active_task: DashboardTask | None = Field(description="Задача недели с ближайшим сроком")
    task_offers: list[DashboardTask] = Field(
        description="Задачи недели на выбор (до трёх, от разных компаний)"
    )
    profile_completeness: int
    fsp_linked: bool
    hints: list[str]


class PublicationConsentUpdate(ApiModel):
    """Согласие на публикацию профиля работодателям [T2.4]."""

    model_config = ConfigDict(json_schema_extra={"examples": [{"granted": False}]})

    granted: bool = Field(description="false — отозвать: профиль сразу пропадает из выдачи")
