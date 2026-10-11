"""Вакансии (лента кандидата / CRUD рекрутера) и отклики — на БД (E8)."""

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import ApplicationStatus, GradeCode, SpecializationCode, WorkFormat
from app.core import email as mailer
from app.core.db import get_session
from app.core.errors import error_responses
from app.core.security import CandidateOrRecruiter, CandidateUser, RecruiterUser
from app.vacancies.schemas import (
    Application,
    ApplicationCreate,
    ApplicationStatusUpdate,
    Vacancy,
    VacancyCreate,
)
from app.vacancies.service import VacancyFilters, VacancyService

router = APIRouter(prefix="/vacancies", tags=["vacancies"])
applications_router = APIRouter(prefix="/applications", tags=["vacancies"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
AUTH = (401, 403)
SALARY_ERROR = (
    422,
    "validation_error",
    "Ошибка валидации (в т.ч. salary_range_invalid: от > до; unknown_skills — стек не из "
    "справочника)",
)
TOTAL_HEADER = "X-Total-Count"


async def _send(to: str, subject: str, text: str) -> None:
    # модуль ищется при вызове — тесты подменяют app.core.email.send_email
    await mailer.send_email_async(to, subject, text)


def _flush_outbox(service: VacancyService, background: BackgroundTasks) -> None:
    """Письма уходят после ответа: недоступный SMTP не задерживает и не ломает запрос."""
    for mail in service.outbox:
        background.add_task(_send, mail.to, mail.subject, mail.text)
    service.outbox.clear()


@router.get(
    "",
    response_model=list[Vacancy],
    summary="Вакансии",
    description=(
        "Кандидат — лента опубликованных вакансий с фильтрами (и `my_application_id`). "
        "Рекрутер — все вакансии своей компании в любом статусе. `skills` — все перечисленные "
        "навыки (в обязательном или желательном стеке). Пагинация необязательна: `limit` и "
        "`offset`; всего по фильтрам — в заголовке `X-Total-Count`."
    ),
    responses=error_responses(*AUTH, 422),
)
async def list_vacancies(
    user: CandidateOrRecruiter,
    session: SessionDep,
    response: Response,
    specialization: SpecializationCode | None = None,
    grade: GradeCode | None = None,
    work_format: WorkFormat | None = None,
    skills: Annotated[list[str] | None, Query()] = None,
    salary_min: Annotated[
        int | None, Query(ge=0, description="Зарплата «до» не ниже (0 — без фильтра)")
    ] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100, description="Размер страницы")] = None,
    offset: Annotated[int, Query(ge=0, description="Сколько пропустить")] = 0,
) -> Any:
    filters = VacancyFilters(
        specialization=specialization,
        grade=grade,
        work_format=work_format,
        skills=skills,
        salary_min=salary_min,
        q=q,
    )
    items, total = await VacancyService(session).list_for(user, filters, limit=limit, offset=offset)
    response.headers[TOTAL_HEADER] = str(total)
    return items


@router.post(
    "",
    response_model=Vacancy,
    status_code=status.HTTP_201_CREATED,
    summary="Создать вакансию (черновик)",
    description=(
        "Зарплата от–до обязательна [ТЗ 2.2 п.1]. Стек — коды справочника. "
        "Вакансия создаётся черновиком своей компании."
    ),
    responses=error_responses(*AUTH, SALARY_ERROR),
)
async def create_vacancy(body: VacancyCreate, user: RecruiterUser, session: SessionDep) -> Any:
    return await VacancyService(session).create(body, user)


@router.get(
    "/{vacancy_id}",
    response_model=Vacancy,
    summary="Карточка вакансии",
    description=(
        "Рекрутер — только своей компании. Кандидат — опубликованная вакансия или та, "
        "на которую он уже откликнулся."
    ),
    responses=error_responses(*AUTH, 404),
)
async def get_vacancy(vacancy_id: int, user: CandidateOrRecruiter, session: SessionDep) -> Any:
    return await VacancyService(session).get(vacancy_id, user)


@router.put(
    "/{vacancy_id}",
    response_model=Vacancy,
    summary="Изменить вакансию своей компании",
    responses=error_responses(*AUTH, 404, SALARY_ERROR),
)
async def update_vacancy(
    vacancy_id: int, body: VacancyCreate, user: RecruiterUser, session: SessionDep
) -> Any:
    return await VacancyService(session).update(vacancy_id, body, user)


@router.post(
    "/{vacancy_id}/publish",
    response_model=Vacancy,
    summary="Опубликовать вакансию",
    description="Из черновика или снятой с публикации.",
    responses=error_responses(*AUTH, 404, (409, "invalid_transition", "Вакансия уже опубликована")),
)
async def publish_vacancy(vacancy_id: int, user: RecruiterUser, session: SessionDep) -> Any:
    return await VacancyService(session).set_published(vacancy_id, user, True)


@router.post(
    "/{vacancy_id}/unpublish",
    response_model=Vacancy,
    summary="Снять вакансию с публикации",
    responses=error_responses(*AUTH, 404, (409, "invalid_transition", "Вакансия не опубликована")),
)
async def unpublish_vacancy(vacancy_id: int, user: RecruiterUser, session: SessionDep) -> Any:
    return await VacancyService(session).set_published(vacancy_id, user, False)


@router.get(
    "/{vacancy_id}/applications",
    response_model=list[Application],
    summary="Отклики на вакансию (рекрутер)",
    description=(
        "Контакты кандидата открыты сразу: он откликнулся сам [ТЗ 2.1]. "
        "В карточке — категория кандидата и результат теста (θ, темы)."
    ),
    responses=error_responses(*AUTH, 404),
)
async def vacancy_applications(vacancy_id: int, user: RecruiterUser, session: SessionDep) -> Any:
    return await VacancyService(session).vacancy_applications(vacancy_id, user)


@router.post(
    "/{vacancy_id}/applications",
    response_model=Application,
    status_code=status.HTTP_201_CREATED,
    summary="Откликнуться на вакансию (кандидат)",
    description=(
        "Только на опубликованную вакансию, один раз. Компания сразу видит контакты кандидата "
        "(запись в audit_log), рекрутерам компании уходит письмо."
    ),
    responses=error_responses(
        *AUTH, 404, (409, "already_applied", "Вы уже откликнулись на эту вакансию"), 422
    ),
)
async def apply_to_vacancy(
    vacancy_id: int,
    body: ApplicationCreate,
    user: CandidateUser,
    session: SessionDep,
    background: BackgroundTasks,
) -> Any:
    service = VacancyService(session)
    result = await service.apply(vacancy_id, user, body.cover_letter)
    _flush_outbox(service, background)
    return result


@applications_router.get(
    "",
    response_model=list[Application],
    summary="Отклики",
    description="Кандидат — свои отклики со статусами; рекрутер — все отклики своей компании.",
    responses=error_responses(*AUTH),
)
async def list_applications(user: CandidateOrRecruiter, session: SessionDep) -> Any:
    return await VacancyService(session).list_applications(user)


@applications_router.patch(
    "/{application_id}",
    response_model=Application,
    summary="Сменить статус отклика (рекрутер)",
    description=(
        "`new → viewed → invited / rejected`; назад к `new`/`viewed` нельзя, `invited` ↔ "
        "`rejected` можно. Статус виден кандидату, ему уходит письмо. При переходе в `invited` "
        "обязателен `contact_method` (и необязательно `message`) — кандидат увидит их в отклике."
    ),
    responses=error_responses(
        *AUTH,
        404,
        (409, "invalid_transition", "Недопустимая смена статуса отклика"),
        422,
    ),
)
async def update_application(
    application_id: int,
    body: ApplicationStatusUpdate,
    user: RecruiterUser,
    session: SessionDep,
    background: BackgroundTasks,
) -> Any:
    new_status: ApplicationStatus = body.status
    service = VacancyService(session)
    contact = (body.contact_method.type, body.contact_method.value) if body.contact_method else None
    result = await service.update_application(
        application_id, user, new_status, contact, body.message
    )
    _flush_outbox(service, background)
    return result
