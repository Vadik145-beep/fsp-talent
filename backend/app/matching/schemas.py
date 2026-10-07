"""Потребности работодателя, рекомендованные категории, ранжированная подборка."""

from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field

from app.candidates.schemas import CandidateCard
from app.common import fixtures
from app.common.enums import (
    CategoryRelation,
    GradeCode,
    NeedStatus,
    SpecializationCode,
    WorkFormat,
)
from app.common.schemas import ApiModel, OutModel, SalaryRangeMixin

NEED_CREATE_EXAMPLE: dict[str, Any] = {
    "title": "Senior Go-разработчик в платёжную команду",
    "raw_text": "нужен сеньор на Go в финтех, удалёнка, 300–400к",
    "specialization": "backend",
    "grade": "senior",
    "skills_required": ["go", "postgresql"],
    "skills_desired": ["kafka", "kubernetes"],
    "team_description": "Платёжный шлюз, 6 человек",
    "work_format": "remote",
    "city": None,
    "salary_from": 300000,
    "salary_to": 400000,
}


class NeedFields(SalaryRangeMixin):
    """Поля потребности (форма). Вилка обязательна, от ≤ до."""

    title: str = Field(min_length=3, max_length=200)
    raw_text: str | None = Field(default=None, max_length=3000, description="Свободный текст")
    specialization: SpecializationCode
    grade: GradeCode
    skills_required: list[str] = Field(default_factory=list, max_length=20)
    skills_desired: list[str] = Field(default_factory=list, max_length=20)
    team_description: str = Field(default="", max_length=2000)
    work_format: WorkFormat
    city: str | None = Field(default=None, max_length=100)


class NeedCreate(NeedFields):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [NEED_CREATE_EXAMPLE]})


class NeedUpdate(NeedCreate):
    """Изменение потребности: те же поля + статус (закрыть / вернуть в работу)."""

    status: NeedStatus = NeedStatus.active


class Need(NeedFields):
    """Потребность работодателя."""

    model_config = ConfigDict(extra="ignore", json_schema_extra=fixtures.first_example("needs"))

    id: int
    company_id: int
    recruiter_id: int
    category: str
    category_label: str
    status: NeedStatus
    candidates_count: int = Field(ge=0, description="Кандидатов в основной категории")
    created_at: datetime


class NeedParseRequest(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"text": "нужен сеньор на Go в финтех, удалёнка, 300–400к"}]
        }
    )

    text: str = Field(min_length=5, max_length=3000)


class NeedDraft(OutModel):
    """Черновик полей из свободного текста; любое поле может быть не распознано (null)."""

    title: str | None = None
    specialization: SpecializationCode | None = None
    grade: GradeCode | None = None
    skills_required: list[str] = Field(default_factory=list)
    skills_desired: list[str] = Field(default_factory=list)
    team_description: str | None = None
    work_format: WorkFormat | None = None
    city: str | None = None
    salary_from: int | None = None
    salary_to: int | None = None


class NeedParseResult(OutModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "draft": {
                        "title": "Senior Backend (Go)",
                        "specialization": "backend",
                        "grade": "senior",
                        "skills_required": ["go"],
                        "skills_desired": [],
                        "team_description": "финтех",
                        "work_format": "remote",
                        "city": None,
                        "salary_from": 300000,
                        "salary_to": 400000,
                    },
                    "parser": "rules",
                    "recognized_fields": [
                        "specialization",
                        "grade",
                        "skills_required",
                        "work_format",
                        "salary_from",
                        "salary_to",
                    ],
                    "unrecognized": ["финтех"],
                }
            ]
        }
    )

    draft: NeedDraft
    parser: str = Field(description="rules | llm")
    recognized_fields: list[str]
    unrecognized: list[str] = Field(default_factory=list)


class RecommendedCategory(OutModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "category": "backend:senior",
                    "label": "Backend · Senior",
                    "relation": "primary",
                    "candidates_count": 4,
                }
            ]
        }
    )

    category: str
    label: str
    relation: CategoryRelation
    candidates_count: int


class ScoreComponent(OutModel):
    """Полоска разбивки счёта: вклад фактора = value × weight."""

    factor: str = Field(examples=["stack"])
    label: str = Field(examples=["Совпадение стека"])
    value: float = Field(ge=0, le=1)
    weight: float = Field(ge=0)
    contribution: float = Field(ge=0)


class MatchedCandidate(OutModel):
    candidate: CandidateCard
    score: float = Field(ge=0, le=1)
    breakdown: list[ScoreComponent]
    reasons: list[str] = Field(description="2–4 причины «почему в подборке»")
    salary_fit: bool = Field(description="Минимум кандидата ≤ максимума вилки (без суммы)")
    invitation_status: str | None = None


class MatchFilters(OutModel):
    skills: list[str] = Field(default_factory=list)
    has_fsp: bool | None = None
    work_format: WorkFormat | None = None
    city: str | None = None


class MatchList(OutModel):
    """Подборка по потребности в выбранной категории; фильтры сужают, сброс возвращает."""

    need_id: int
    category: str
    category_label: str
    total_before_filters: int
    total: int
    filters: MatchFilters
    items: list[MatchedCandidate]
