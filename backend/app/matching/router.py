"""Потребности работодателя и подборка кандидатов по категориям (рекрутер)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import WorkFormat
from app.core.db import get_session
from app.core.errors import AppError, error_responses
from app.core.security import CurrentUser, RecruiterUser
from app.matching.schemas import (
    MatchList,
    Need,
    NeedCreate,
    NeedParseRequest,
    NeedParseResult,
    NeedUpdate,
    RecommendedCategory,
)
from app.matching.service import NeedService
from app.nlp.need_parser import parse_need

router = APIRouter(prefix="/matching", tags=["matching"])

AUTH = (401, 403)
SessionDep = Annotated[AsyncSession, Depends(get_session)]
UNKNOWN_SKILLS = (422, "unknown_skills", "Технологий нет в справочнике стека")


def _company(user: CurrentUser) -> int:
    if user.company_id is None:
        raise AppError(404, "not_found", "Компания не найдена")
    return user.company_id


@router.post(
    "/needs/parse",
    response_model=NeedParseResult,
    summary="Разобрать свободный текст потребности в поля",
    description="Правила без LLM; с ключом LLM — точнее (трек 3c).",
    responses=error_responses(*AUTH, 422),
)
async def parse_need_text(body: NeedParseRequest, user: RecruiterUser) -> Any:
    return parse_need(body.text)


@router.get(
    "/needs",
    response_model=list[Need],
    summary="Потребности моей компании",
    responses=error_responses(*AUTH),
)
async def list_needs(user: RecruiterUser, session: SessionDep) -> Any:
    return await NeedService(session).list_needs(_company(user))


@router.post(
    "/needs",
    response_model=Need,
    status_code=status.HTTP_201_CREATED,
    summary="Создать потребность",
    description="Вилка от–до обязательна, от ≤ до. Стек — коды справочника `skills`.",
    responses=error_responses(
        *AUTH,
        (422, "validation_error", "Ошибка валидации (в т.ч. salary_range_invalid)"),
        UNKNOWN_SKILLS,
    ),
)
async def create_need(body: NeedCreate, user: RecruiterUser, session: SessionDep) -> Any:
    assert user.recruiter_id is not None
    return await NeedService(session).create_need(body, _company(user), user.recruiter_id)


@router.get(
    "/needs/{need_id}",
    response_model=Need,
    summary="Потребность",
    responses=error_responses(*AUTH, 404),
)
async def get_need(need_id: int, user: RecruiterUser, session: SessionDep) -> Any:
    return await NeedService(session).get_need(need_id, _company(user))


@router.put(
    "/needs/{need_id}",
    response_model=Need,
    summary="Изменить потребность",
    description="Те же поля, что при создании, плюс статус (`active` / `closed`).",
    responses=error_responses(*AUTH, 404, 422, UNKNOWN_SKILLS),
)
async def update_need(
    need_id: int, body: NeedUpdate, user: RecruiterUser, session: SessionDep
) -> Any:
    return await NeedService(session).update_need(need_id, _company(user), body)


@router.delete(
    "/needs/{need_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Удалить потребность",
    description="Отправленные по ней приглашения остаются (ссылка на потребность обнуляется).",
    responses=error_responses(*AUTH, 404),
)
async def delete_need(need_id: int, user: RecruiterUser, session: SessionDep) -> Response:
    await NeedService(session).delete_need(need_id, _company(user))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/needs/{need_id}/categories",
    response_model=list[RecommendedCategory],
    summary="Рекомендованные категории с числом кандидатов",
    description="Основная категория, грейд ±1 и смежные специализации.",
    responses=error_responses(*AUTH, 404),
)
async def need_categories(need_id: int, user: RecruiterUser, session: SessionDep) -> Any:
    service = NeedService(session)
    return await service.recommended_categories(await service.get_need(need_id, _company(user)))


@router.get(
    "/needs/{need_id}/candidates",
    response_model=MatchList,
    summary="Подборка: кандидаты категории с объяснением и разбивкой счёта",
    description=(
        "Кандидаты обезличены. Счёт = Σ value × weight по факторам (стек, тест, ФСП, свежесть, "
        "зарплата, формат), веса — из настроек платформы; сумма `contribution` равна `score`. "
        "Фильтры сужают подборку, `total_before_filters` — исходный размер; без фильтров "
        "возвращается исходный список."
    ),
    responses=error_responses(*AUTH, 404, 422),
)
async def need_candidates(
    need_id: int,
    user: RecruiterUser,
    session: SessionDep,
    category: Annotated[str | None, Query(examples=["backend:middle"])] = None,
    skills: Annotated[list[str] | None, Query()] = None,
    has_fsp: bool | None = None,
    work_format: WorkFormat | None = None,
    city: str | None = None,
) -> Any:
    service = NeedService(session)
    company_id = _company(user)
    need = await service.get_need(need_id, company_id)
    return await service.matches(
        need, company_id, category, skills or [], has_fsp, work_format, city
    )
