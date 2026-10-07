"""Компании работодателей, рекрутеры, дашборд рекрутера."""

from datetime import datetime

from pydantic import ConfigDict, Field

from app.common import fixtures
from app.common.enums import InvitationStatus
from app.common.schemas import ApiModel, OutModel


class Company(OutModel):
    model_config = ConfigDict(json_schema_extra=fixtures.first_example("companies"))

    id: int
    name: str
    description: str
    industry: str = Field(examples=["Финтех"])
    website: str | None = None
    city: str | None = None
    contact_email: str
    contact_phone: str | None = None
    inn: str | None = None
    verified_domain: bool = Field(description="Почта рекрутеров на домене компании")
    trust_score: float = Field(ge=0, le=100, description="Скоринг надёжности (антифрод)")
    blocked: bool = False
    created_at: datetime


class MyCompany(Company):
    """Профиль своей компании в кабинете рекрутера."""

    invite_code: str | None = Field(
        default=None,
        description="Код приглашения рекрутеров в компанию — только администратору компании",
    )


class CompanyUpdate(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Северный код",
                    "description": "Разрабатываем платёжные сервисы.",
                    "industry": "Финтех",
                    "website": "https://severny-kod.example.com",
                    "city": "Москва",
                    "contact_email": "hr@example.com",
                    "contact_phone": "+7 900 000-10-00",
                }
            ]
        }
    )

    name: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=3000)
    industry: str = Field(default="", max_length=100)
    website: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=100)
    contact_email: str = Field(max_length=200)
    contact_phone: str | None = Field(default=None, max_length=32)


class Recruiter(OutModel):
    """Рекрутер компании (запись `recruiters.json`)."""

    model_config = ConfigDict(json_schema_extra=fixtures.first_example("recruiters"))

    id: int
    user_id: int
    company_id: int
    full_name: str
    position: str
    email: str
    phone: str | None = None
    telegram: str | None = None
    is_company_admin: bool = False


class RecruiterContacts(OutModel):
    """Контакты рекрутера — кандидат видит их после принятия приглашения."""

    full_name: str
    position: str
    email: str
    phone: str | None = None
    telegram: str | None = None


class NeedBrief(OutModel):
    id: int
    title: str
    category: str
    candidates_count: int


class ApplicationBrief(OutModel):
    id: int
    vacancy_id: int
    vacancy_title: str
    candidate_pseudonym: str
    created_at: datetime


class Quota(OutModel):
    """Квота активных приглашений рекрутера (T7.6)."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"limit": 20, "used": 7, "left": 13}]}
    )

    limit: int
    used: int = Field(description="Активные: отправлено + просмотрено")
    left: int


class RecruiterDashboard(OutModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "company_name": "Северный код",
                    "active_needs": [
                        {
                            "id": 1,
                            "title": "Backend-разработчик на Go",
                            "category": "backend:senior",
                            "candidates_count": 4,
                        }
                    ],
                    "invitations_by_status": {"sent": 3, "viewed": 2, "accepted": 1},
                    "quota": {"limit": 20, "used": 5, "left": 15},
                    "new_applications_count": 2,
                    "recent_applications": [],
                }
            ]
        }
    )

    company_name: str
    active_needs: list[NeedBrief]
    invitations_by_status: dict[InvitationStatus, int]
    quota: Quota
    new_applications_count: int
    recent_applications: list[ApplicationBrief]
