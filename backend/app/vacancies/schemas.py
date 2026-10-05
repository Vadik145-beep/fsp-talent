"""Вакансии и отклики [ТЗ 2.1]. Зарплата от–до обязательна; контакты кандидата
открываются компании сразу после отклика."""

from datetime import datetime

from pydantic import ConfigDict, Field

from app.candidates.schemas import CandidateCard, CandidateContacts
from app.common import fixtures
from app.common.enums import (
    ApplicationStatus,
    GradeCode,
    SpecializationCode,
    VacancyStatus,
    WorkFormat,
)
from app.common.schemas import ApiModel, OutModel, SalaryRangeMixin


class VacancyFields(SalaryRangeMixin):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=10000)
    specialization: SpecializationCode
    grade: GradeCode
    skills_required: list[str] = Field(default_factory=list, max_length=20)
    skills_desired: list[str] = Field(default_factory=list, max_length=20)
    work_format: WorkFormat
    city: str | None = Field(default=None, max_length=100)


class VacancyCreate(VacancyFields):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "title": "Middle Python-разработчик",
                    "description": "Развиваем сервис платежей. FastAPI, PostgreSQL, Kafka.",
                    "specialization": "backend",
                    "grade": "middle",
                    "skills_required": ["python", "fastapi", "postgresql"],
                    "skills_desired": ["kafka"],
                    "work_format": "hybrid",
                    "city": "Москва",
                    "salary_from": 200000,
                    "salary_to": 280000,
                }
            ]
        },
    )


class Vacancy(VacancyFields):
    """Вакансия (запись `vacancies.json`)."""

    model_config = ConfigDict(extra="ignore", json_schema_extra=fixtures.first_example("vacancies"))

    id: int
    company_id: int
    company_name: str
    category: str
    category_label: str
    status: VacancyStatus
    applications_count: int = 0
    created_at: datetime
    published_at: datetime | None = None
    my_application_id: int | None = Field(
        default=None, description="Для кандидата: id его отклика, если есть"
    )


class ApplicationCreate(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"cover_letter": "Здравствуйте! Есть опыт с FastAPI и PostgreSQL."}]
        }
    )

    cover_letter: str = Field(default="", max_length=3000)


class ApplicationRecord(OutModel):
    """Отклик (запись `applications.json`)."""

    model_config = ConfigDict(json_schema_extra=fixtures.first_example("applications"))

    id: int
    vacancy_id: int
    candidate_id: int
    vacancy_title: str
    company_id: int
    company_name: str
    cover_letter: str = ""
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime


class Application(ApplicationRecord):
    """Отклик в ответе API. Для рекрутера — карточка кандидата и контакты (откликнулся сам)."""

    candidate: CandidateCard | None = None
    candidate_contacts: CandidateContacts | None = None


class ApplicationStatusUpdate(ApiModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"status": "viewed"}]})

    status: ApplicationStatus
