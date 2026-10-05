"""Вакансии (лента кандидата / CRUD рекрутера) и отклики."""

from typing import Annotated, Any

from fastapi import APIRouter, Query, status

from app.common.enums import ApplicationStatus, GradeCode, SpecializationCode, WorkFormat
from app.core.errors import error_responses
from app.core.security import CandidateOrRecruiter, CandidateUser, RecruiterUser
from app.vacancies.schemas import (
    Application,
    ApplicationCreate,
    ApplicationStatusUpdate,
    Vacancy,
    VacancyCreate,
)
from app.vacancies.service import VacancyService

router = APIRouter(prefix="/vacancies", tags=["vacancies"])
applications_router = APIRouter(prefix="/applications", tags=["vacancies"])
service = VacancyService()

AUTH = (401, 403)
SALARY_ERROR = (422, "validation_error", "Ошибка валидации (в т.ч. salary_range_invalid: от > до)")


@router.get(
    "",
    response_model=list[Vacancy],
    summary="Вакансии",
    description=(
        "Кандидат — лента опубликованных вакансий с фильтрами (и `my_application_id`). "
        "Рекрутер — все вакансии своей компании в любом статусе."
    ),
    responses=error_responses(*AUTH, 422),
)
async def list_vacancies(
    user: CandidateOrRecruiter,
    specialization: SpecializationCode | None = None,
    grade: GradeCode | None = None,
    work_format: WorkFormat | None = None,
    skills: Annotated[list[str] | None, Query()] = None,
    salary_min: Annotated[int | None, Query(gt=0, description="Зарплата «до» не ниже")] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Any:
    return service.list_for(
        user,
        specialization=specialization,
        grade=grade,
        work_format=work_format,
        skills=skills,
        salary_min=salary_min,
        q=q,
    )


@router.post(
    "",
    response_model=Vacancy,
    status_code=status.HTTP_201_CREATED,
    summary="Создать вакансию (черновик)",
    description="Зарплата от–до обязательна [ТЗ 2.2 п.1]. Заглушка: не сохраняется.",
    responses=error_responses(*AUTH, SALARY_ERROR),
)
async def create_vacancy(body: VacancyCreate, user: RecruiterUser) -> Any:
    return service.create(body, user)


@router.get(
    "/{vacancy_id}",
    response_model=Vacancy,
    summary="Карточка вакансии",
    responses=error_responses(*AUTH, 404),
)
async def get_vacancy(vacancy_id: int, user: CandidateOrRecruiter) -> Any:
    return service.get(vacancy_id, user)


@router.put(
    "/{vacancy_id}",
    response_model=Vacancy,
    summary="Изменить вакансию своей компании",
    responses=error_responses(*AUTH, 404, SALARY_ERROR),
)
async def update_vacancy(vacancy_id: int, body: VacancyCreate, user: RecruiterUser) -> Any:
    return service.update(vacancy_id, body, user)


@router.post(
    "/{vacancy_id}/publish",
    response_model=Vacancy,
    summary="Опубликовать вакансию",
    responses=error_responses(*AUTH, 404, (409, "invalid_transition", "Вакансия уже опубликована")),
)
async def publish_vacancy(vacancy_id: int, user: RecruiterUser) -> Any:
    return service.set_published(vacancy_id, user, True)


@router.post(
    "/{vacancy_id}/unpublish",
    response_model=Vacancy,
    summary="Снять вакансию с публикации",
    responses=error_responses(*AUTH, 404, (409, "invalid_transition", "Вакансия не опубликована")),
)
async def unpublish_vacancy(vacancy_id: int, user: RecruiterUser) -> Any:
    return service.set_published(vacancy_id, user, False)


@router.get(
    "/{vacancy_id}/applications",
    response_model=list[Application],
    summary="Отклики на вакансию (рекрутер)",
    description="Контакты кандидата открыты сразу: он откликнулся сам [ТЗ 2.1].",
    responses=error_responses(*AUTH, 404),
)
async def vacancy_applications(vacancy_id: int, user: RecruiterUser) -> Any:
    return service.vacancy_applications(vacancy_id, user)


@router.post(
    "/{vacancy_id}/applications",
    response_model=Application,
    status_code=status.HTTP_201_CREATED,
    summary="Откликнуться на вакансию (кандидат)",
    responses=error_responses(
        *AUTH, 404, (409, "already_applied", "Вы уже откликнулись на эту вакансию"), 422
    ),
)
async def apply_to_vacancy(vacancy_id: int, body: ApplicationCreate, user: CandidateUser) -> Any:
    return service.apply(vacancy_id, user, body.cover_letter)


@applications_router.get(
    "",
    response_model=list[Application],
    summary="Отклики",
    description="Кандидат — свои отклики со статусами; рекрутер — все отклики своей компании.",
    responses=error_responses(*AUTH),
)
async def list_applications(user: CandidateOrRecruiter) -> Any:
    return service.list_applications(user)


@applications_router.patch(
    "/{application_id}",
    response_model=Application,
    summary="Сменить статус отклика (рекрутер)",
    responses=error_responses(*AUTH, 404, 422),
)
async def update_application(
    application_id: int, body: ApplicationStatusUpdate, user: RecruiterUser
) -> Any:
    new_status: ApplicationStatus = body.status
    return service.update_application(application_id, user, new_status)
