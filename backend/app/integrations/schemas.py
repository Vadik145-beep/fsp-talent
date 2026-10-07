"""Схемы интеграции с ATS: API-токены, вебхуки, доставки, выгрузка данных компании."""

from datetime import datetime
from typing import Any, Literal

from pydantic import ConfigDict, Field

from app.common.schemas import ApiModel, OutModel

WebhookEvent = Literal["invitation.accepted", "application.created"]


class ApiTokenCreate(ApiModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"name": "Хантфлоу"}]})

    name: str = Field(min_length=1, max_length=100, description="Для чего токен (подпись)")


class ApiToken(OutModel):
    """API-токен компании. Сам токен показывается один раз — при выпуске."""

    id: int
    name: str
    token_prefix: str = Field(description="Начало токена — чтобы узнать его в списке")
    active: bool
    created_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None


class ApiTokenIssued(ApiToken):
    token: str = Field(description="Токен целиком. Сохраните: больше он не показывается")


class WebhookCreate(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "url": "https://ats.example.com/hooks/fsp",
                    "events": ["invitation.accepted", "application.created"],
                }
            ]
        }
    )

    url: str = Field(min_length=8, max_length=500, description="http(s)-адрес приёма событий")
    events: list[WebhookEvent] = Field(min_length=1, description="На какие события подписаться")
    secret: str | None = Field(
        default=None,
        min_length=16,
        max_length=128,
        description="Секрет подписи HMAC; не передан — сгенерируем",
    )


class Webhook(OutModel):
    id: int
    url: str
    events: list[str]
    active: bool
    created_at: datetime


class WebhookCreated(Webhook):
    secret: str = Field(description="Секрет подписи. Показывается один раз — при создании")


class WebhookDeliveryOut(OutModel):
    """Попытка доставки события на адрес компании."""

    id: int
    endpoint_id: int
    event: str
    status: Literal["pending", "delivered", "failed"]
    attempts: int
    last_status_code: int | None = None
    last_error: str | None = None
    next_attempt_at: datetime | None = None
    delivered_at: datetime | None = None
    created_at: datetime
    payload: dict[str, Any]


class CompanyExport(OutModel):
    """Выгрузка данных компании для ATS (по API-токену)."""

    company: dict[str, Any]
    generated_at: datetime
    since: datetime | None = None
    vacancies: list[dict[str, Any]]
    invitations: list[dict[str, Any]] = Field(
        description="Контакты кандидата — только у принятых приглашений"
    )
    applications: list[dict[str, Any]] = Field(description="Отклики с контактами кандидатов")
