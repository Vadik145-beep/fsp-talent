"""Приглашения: создание, статусы, отказ с причиной, раскрытие контактов, квота, подсказка.

Одна схема `Invitation` для обеих сторон; поля заполняются по роли:
- `candidate` (обезличенная карточка) — только рекрутеру;
- `candidate_contacts` — рекрутеру и только при статусе `accepted`;
- `recruiter_contacts` — кандидату и только при статусе `accepted`;
- `contact_method.value` и `task_text` — кандидату только при статусе `accepted`
  (до этого `null`; что вопрос к созвону есть — видно по `has_task_text`).
"""

from datetime import datetime

from pydantic import ConfigDict, Field

from app.candidates.schemas import CandidateCard, CandidateContacts
from app.common import fixtures
from app.common.enums import (
    ContactMethodType,
    DeclineReason,
    InvitationEventType,
    InvitationStatus,
    Role,
)
from app.common.schemas import ApiModel, OutModel, SalaryRangeMixin
from app.companies.schemas import Quota, RecruiterContacts


class ContactMethod(OutModel):
    type: ContactMethodType
    value: str | None = Field(
        default=None,
        max_length=200,
        examples=["@hr_severny_kod"],
        description="Кандидату — только после принятия, до этого null",
    )


class ContactMethodIn(ApiModel):
    type: ContactMethodType
    value: str = Field(min_length=2, max_length=200)


class InvitationCreate(SalaryRangeMixin):
    """Приглашение [ТЗ 2.2 п.1–2]: вилка обязательна, от ≤ до.

    Если максимум вилки ниже минимальной зарплаты кандидата — 422 `salary_below_expectations`
    (сумма кандидата не раскрывается).
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "candidate_id": 1,
                    "need_id": 1,
                    "vacancy_id": None,
                    "description": "Ищем бэкенд-разработчика в команду платёжного шлюза.",
                    "salary_from": 250000,
                    "salary_to": 320000,
                    "contact_method": {"type": "telegram", "value": "@hr_severny_kod"},
                    "task_text": None,
                }
            ]
        },
    )

    candidate_id: int
    need_id: int | None = None
    vacancy_id: int | None = None
    description: str = Field(min_length=10, max_length=3000)
    contact_method: ContactMethodIn
    task_text: str | None = Field(
        default=None, max_length=2000, description="Вопрос к созвону (необязательно)"
    )


class InvitationRecord(OutModel):
    """Хранимые поля приглашения."""

    model_config = ConfigDict(json_schema_extra=fixtures.first_example("invitations"))

    id: int
    candidate_id: int
    recruiter_id: int
    company_id: int
    company_name: str
    recruiter_name: str
    need_id: int | None = None
    vacancy_id: int | None = None
    category: str
    category_label: str
    description: str
    salary_from: int
    salary_to: int
    contact_method: ContactMethod
    task_text: str | None = Field(
        default=None, description="Кандидату — только после принятия, до этого null"
    )
    has_task_text: bool = Field(default=False, description="Есть ли вопрос к созвону")
    status: InvitationStatus
    decline_reason: DeclineReason | None = None
    decline_comment: str | None = None
    created_at: datetime
    viewed_at: datetime | None = None
    responded_at: datetime | None = None
    expires_at: datetime
    withdrawn_at: datetime | None = None


class Invitation(InvitationRecord):
    """Приглашение в ответе API (поля по роли — см. описание модуля)."""

    candidate: CandidateCard | None = Field(default=None, description="Только для рекрутера")
    candidate_contacts: CandidateContacts | None = Field(
        default=None, description="Рекрутеру после принятия"
    )
    recruiter_contacts: RecruiterContacts | None = Field(
        default=None, description="Кандидату после принятия"
    )
    decline_reason_label: str | None = None


class InvitationEvent(OutModel):
    """Журнал событий приглашения (запись `invitation_events.json`)."""

    model_config = ConfigDict(json_schema_extra=fixtures.first_example("invitation_events"))

    id: int
    invitation_id: int
    type: InvitationEventType
    at: datetime
    actor_role: Role | None = Field(default=None, description="null — система (истечение)")


class InvitationDetail(Invitation):
    events: list[InvitationEvent] = Field(default_factory=list)


class DeclineRequest(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"reason": "salary_too_low", "comment": "Рассматриваю от 300 тысяч"}]
        }
    )

    reason: DeclineReason
    comment: str | None = Field(default=None, max_length=1000)


class MarketHint(OutModel):
    """Рыночная подсказка зарплаты по категории (T7.7)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "category": "backend:middle",
                    "category_label": "Backend · Middle",
                    "median_accepted_from": 220000,
                    "median_accepted_to": 290000,
                    "acceptance_probability": 0.64,
                    "sample_size": 12,
                    "message": "В категории «Backend · Middle» обычно принимают от 220 000 ₽",
                }
            ]
        }
    )

    category: str
    category_label: str
    median_accepted_from: int | None
    median_accepted_to: int | None
    acceptance_probability: float | None = Field(default=None, ge=0, le=1)
    sample_size: int
    message: str


class InvitationQuota(Quota):
    """Квота + подсказка, если исчерпана."""

    hint: str | None = None


class InvitationCounters(OutModel):
    """Счётчики для бейджей в кабинете (T7.8).

    Кандидат: `new` — полученные и ещё не открытые, `active` — ждут ответа.
    Рекрутер: `new` — ответы кандидатов (просмотр, принятие, отказ), которые он ещё не открывал,
    `active` — приглашения компании, ждущие ответа.
    """

    model_config = ConfigDict(json_schema_extra={"examples": [{"new": 2, "active": 5}]})

    new: int = Field(ge=0)
    active: int = Field(ge=0)
