"""Пользователи и согласия 152-ФЗ."""

from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field

from app.common import fixtures
from app.common.enums import ConsentType, GradeStatusCode, Role
from app.common.schemas import ApiModel, OutModel


class UserRecord(OutModel):
    """Пользователь платформы (запись `users.json`, она же строка списка в админке)."""

    model_config = ConfigDict(json_schema_extra=fixtures.first_example("users"))

    id: int
    email: str
    role: Role
    full_name: str
    email_verified: bool
    blocked: bool = False
    created_at: datetime
    last_login_at: datetime | None = None
    grade_status: GradeStatusCode | None = Field(
        default=None,
        description=(
            "Только у соискателя: confirmed — грейд подтверждён тестом, unconfirmed — "
            "заявлен, но тест не пройден, none — грейда нет; у остальных ролей null"
        ),
    )
    grade_label: str | None = Field(
        default=None, description="Категория (подтверждённая или заявленная), «Backend · Middle»"
    )


ME_EXAMPLE: dict[str, Any] = {
    "id": 1,
    "email": "candidate@example.com",
    "role": "candidate",
    "full_name": "Алексей Смирнов",
    "email_verified": True,
    "fsp_id": "FSP-000001",
    "candidate_id": 1,
    "recruiter_id": None,
    "company_id": None,
}


class Me(OutModel):
    """Текущий пользователь (`GET /api/auth/me`)."""

    model_config = ConfigDict(json_schema_extra={"examples": [ME_EXAMPLE]})

    id: int
    email: str
    role: Role
    full_name: str
    email_verified: bool
    fsp_id: str | None = Field(default=None, pattern=r"^FSP-\d{6}$")
    candidate_id: int | None = None
    recruiter_id: int | None = None
    company_id: int | None = None


class Consent(OutModel):
    """Согласие пользователя: версия текста и даты хранятся [ТЗ 3.5]."""

    model_config = ConfigDict(json_schema_extra=fixtures.first_example("consents"))

    id: int
    user_id: int
    type: ConsentType
    version: str = Field(examples=["2026-10-01"])
    granted: bool
    granted_at: datetime | None = None
    revoked_at: datetime | None = None


class ConsentUpdate(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"granted": False, "version": "2026-10-01"}]}
    )

    granted: bool
    version: str = Field(default="2026-10-01", description="Версия текста согласия")
