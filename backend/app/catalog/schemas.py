"""Справочники: специализации, грейды, категории, темы, стек, причины отказа."""

from pydantic import ConfigDict, Field

from app.common import fixtures
from app.common.enums import DeclineReason, GradeCode, SpecializationCode
from app.common.schemas import OutModel


class Specialization(OutModel):
    model_config = ConfigDict(json_schema_extra=fixtures.first_example("specializations"))

    id: SpecializationCode
    label: str = Field(description="Подпись: Backend, Frontend, …")
    description: str
    active: bool = True


class Grade(OutModel):
    model_config = ConfigDict(json_schema_extra=fixtures.first_example("grades"))

    id: GradeCode
    label: str = Field(description="Стажёр, Junior, Middle, Senior")
    order: int = Field(ge=0, description="Порядок: 0 — стажёр, 3 — senior")


class Category(OutModel):
    """Категория = специализация × грейд, код `<spec>:<grade>`."""

    model_config = ConfigDict(json_schema_extra=fixtures.first_example("categories"))

    id: str = Field(pattern=r"^[a-z_]+:[a-z]+$", examples=["backend:middle"])
    specialization: SpecializationCode
    grade: GradeCode
    label: str = Field(examples=["Backend · Middle"])


class Topic(OutModel):
    """Тема теста внутри специализации."""

    model_config = ConfigDict(json_schema_extra=fixtures.first_example("topics"))

    id: str = Field(examples=["backend.databases"])
    specialization: SpecializationCode
    label: str


class Skill(OutModel):
    """Технология из справочника стека с привязкой к специализациям."""

    model_config = ConfigDict(json_schema_extra=fixtures.first_example("skills"))

    id: str = Field(examples=["python"])
    label: str = Field(examples=["Python"])
    specializations: list[SpecializationCode]


class DeclineReasonItem(OutModel):
    model_config = ConfigDict(json_schema_extra=fixtures.first_example("decline_reasons"))

    id: DeclineReason
    label: str
