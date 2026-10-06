"""Схема экрана «Категория и грейд» в кабинете кандидата (T3.5).

Отдельный модуль: схемы теста (`app.testing.schemas`) сами импортируют схемы кандидата.
"""

from datetime import datetime

from pydantic import Field

from app.common.enums import GradeCode
from app.common.schemas import OutModel
from app.testing.schemas import GradeStatus


class GradeOption(OutModel):
    """Можно ли пройти тест на соседний грейд и с какой даты."""

    target_grade: GradeCode
    allowed: bool
    code: str = Field(
        description="allowed | grade_change_cooldown | failed_retry_cooldown",
        examples=["grade_change_cooldown"],
    )
    reason: str = Field(examples=["Грейд можно менять не чаще раза в 90 дней: …"])
    available_at: datetime | None = Field(
        default=None, description="Когда станет доступно (null — уже можно)"
    )


class CandidateGradeStatus(GradeStatus):
    """Статус грейда из БД: правила частоты попыток считает движок (`can_attempt`)."""

    lower: GradeOption | None = Field(default=None, description="Тест на грейд ниже")
    higher: GradeOption | None = Field(default=None, description="Тест на грейд выше")
