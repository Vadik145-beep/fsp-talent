"""Достижения ФСП (кэш реестра) и статус привязки ФСП ID."""

from datetime import date, datetime
from typing import Literal

from pydantic import ConfigDict, Field

from app.candidates.schemas import FspBadge
from app.common import fixtures
from app.common.enums import FspDiscipline, FspLevel
from app.common.schemas import ApiModel, OutModel


class FspAchievement(OutModel):
    """Достижение участника (наша версия API реестра ФСП, T5.1)."""

    model_config = ConfigDict(json_schema_extra=fixtures.first_example("fsp_achievements"))

    id: int
    fsp_id: str = Field(pattern=r"^FSP-\d{6}$")
    competition: str
    discipline: FspDiscipline
    level: FspLevel
    date: date
    place: int | None = Field(default=None, ge=1, description="Место; null — участие")
    diploma: str | None = Field(default=None, examples=["Диплом I степени"])
    team: str | None = None
    role: str | None = Field(default=None, examples=["Капитан, backend"])
    rating: float | None = None
    protocol_url: str | None = None
    verified: bool = Field(default=True, description="Подтверждено ФСП")


class FspStatus(OutModel):
    """Экран «Достижения ФСП»: привязка, скор, бейджи. Без истории — нейтрально (T5.4)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "linked": True,
                    "fsp_id": "FSP-000001",
                    "linked_at": "2026-09-20T10:00:00+03:00",
                    "last_sync_at": "2026-10-05T03:00:00+03:00",
                    "achievements_count": 3,
                    "fsp_score": 61.5,
                    "badges": [],
                    "has_history": True,
                    "message": None,
                },
                {
                    "linked": False,
                    "fsp_id": None,
                    "linked_at": None,
                    "last_sync_at": None,
                    "achievements_count": 0,
                    "fsp_score": None,
                    "badges": [],
                    "has_history": False,
                    "message": (
                        "Нет данных ФСП. Привяжите ФСП ID, если участвовали в соревнованиях."
                    ),
                },
            ]
        }
    )

    linked: bool
    fsp_id: str | None = None
    linked_at: datetime | None = None
    last_sync_at: datetime | None = None
    achievements_count: int = 0
    fsp_score: float | None = None
    badges: list[FspBadge] = Field(default_factory=list)
    has_history: bool
    message: str | None = None


class FspCodeExchange(ApiModel):
    """Код авторизации из Keycloak после входа через ФСП ID (OIDC Authorization Code + PKCE).

    `code_verifier` хранит сервер (подписанная httpOnly cookie, выданная вместе с authorize-url),
    поэтому поле необязательно и игнорируется — оставлено для совместимости с контрактом v0.
    `redirect_uri`, если передан, должен совпадать с тем, что был в authorize-url.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "code": "kc-auth-code",
                    "state": "b1f0c2",
                    "redirect_uri": "http://localhost:15173/auth/fsp-callback",
                }
            ]
        },
    )

    code: str = Field(min_length=1, max_length=4096)
    state: str = Field(min_length=1, max_length=512)
    code_verifier: str | None = Field(
        default=None,
        min_length=43,
        max_length=128,
        description="Не нужен: verifier хранит сервер. Игнорируется",
        deprecated=True,
    )
    redirect_uri: str | None = Field(default=None, max_length=2048)


class FspWebhookEvent(ApiModel):
    """Событие реестра ФСП (предложение для реальной интеграции, docs/integration/fsp.md §4).

    Тело подписывается HMAC-SHA256 общим секретом: заголовок `X-FSP-Signature: sha256=<hex>`.
    """

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [
                {
                    "event_id": "evt-000123",
                    "event": "participant.achievements_updated",
                    "fsp_id": "FSP-000001",
                    "updated_at": "2026-10-06T09:00:00Z",
                    "sent_at": "2026-10-06T09:00:05Z",
                }
            ]
        },
    )

    event_id: str | None = Field(default=None, max_length=128)
    event: str = Field(examples=["participant.achievements_updated"], max_length=64)
    fsp_id: str = Field(pattern=r"^FSP-\d{6}$")
    updated_at: datetime | None = None
    sent_at: datetime | None = Field(
        default=None, description="Когда реестр отправил событие; старше 5 минут — отклоняется"
    )


class FspWebhookAck(OutModel):
    """Ответ на вебхук: принято, пересинхронизирован ли участник."""

    accepted: bool = True
    event: str
    fsp_id: str
    resynced: bool = Field(description="false — событие не про изменения или ФСП ID не привязан")
    achievements_count: int | None = None
    status: Literal["resynced", "ignored"]
