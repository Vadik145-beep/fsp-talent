"""Схемы админки банка задач, которых нет в `app.admin.schemas` (детектор утечек)."""

from datetime import datetime

from pydantic import Field

from app.common.schemas import OutModel


class LeakedItem(OutModel):
    """Шаблон, помеченный детектором и выведенный из оборота."""

    item_id: int
    code: str
    title: str
    n: int = Field(description="Ответов в окне детектора")
    observed_rate: float = Field(description="Доля верных: факт")
    expected_rate: float = Field(description="Доля верных: ожидание по IRT")
    z: float
    fast_correct: int = Field(description="Верных ответов подозрительно быстро")
    reasons: list[str] = Field(description="irt_drift | fast_correct")


class CandidateFlag(OutModel):
    """Аномалия кандидата: повод для ручной проверки, не автоматическое наказание."""

    candidate_id: int
    session_id: int
    suspicious_item_ids: list[int]
    lz: float = Field(description="Индекс согласия ответов l_z")
    reasons: list[str] = Field(description="fast_hard_correct | aberrant_pattern")


class LeakScanResult(OutModel):
    scanned_at: datetime
    answers_checked: int
    items_checked: int
    retired: list[LeakedItem]
    flagged_candidates: list[CandidateFlag]
