"""Достижения ФСП (кэш реестра) и статус привязки ФСП ID."""

from datetime import date, datetime

from pydantic import ConfigDict, Field

from app.candidates.schemas import FspBadge
from app.common import fixtures
from app.common.enums import FspDiscipline, FspLevel
from app.common.schemas import OutModel


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
