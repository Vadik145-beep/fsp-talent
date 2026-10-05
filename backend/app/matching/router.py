"""Потребности работодателя и подборка кандидатов по категориям (рекрутер)."""

from typing import Annotated, Any

from fastapi import APIRouter, Query, status

from app.common.enums import WorkFormat
from app.core.errors import AppError, error_responses
from app.core.security import CurrentUser, RecruiterUser
from app.matching.schemas import (
    MatchList,
    Need,
    NeedCreate,
    NeedParseRequest,
    NeedParseResult,
    RecommendedCategory,
)
from app.matching.service import MatchingService

router = APIRouter(prefix="/matching", tags=["matching"])
service = MatchingService()

AUTH = (401, 403)


def _company(user: CurrentUser) -> int:
    if user.company_id is None:
        raise AppError(404, "not_found", "Компания не найдена")
    return user.company_id


@router.post(
    "/needs/parse",
    response_model=NeedParseResult,
    summary="Разобрать свободный текст потребности в поля",
    description="Правила без LLM; с ключом LLM — точнее (волна 3c).",
    responses=error_responses(*AUTH, 422),
)
async def parse_need(body: NeedParseRequest, user: RecruiterUser) -> Any:
    return service.parse(body.text)


@router.get(
    "/needs",
    response_model=list[Need],
    summary="Потребности моей компании",
    responses=error_responses(*AUTH),
)
async def list_needs(user: RecruiterUser) -> Any:
    return service.list_needs(_company(user))


@router.post(
    "/needs",
    response_model=Need,
    status_code=status.HTTP_201_CREATED,
    summary="Создать потребность",
    description="Вилка от–до обязательна, от ≤ до. Заглушка: не сохраняется.",
    responses=error_responses(
        *AUTH, (422, "validation_error", "Ошибка валидации (в т.ч. salary_range_invalid)")
    ),
)
async def create_need(body: NeedCreate, user: RecruiterUser) -> Any:
    assert user.recruiter_id is not None
    return service.create_need(body, _company(user), user.recruiter_id)


@router.get(
    "/needs/{need_id}",
    response_model=Need,
    summary="Потребность",
    responses=error_responses(*AUTH, 404),
)
async def get_need(need_id: int, user: RecruiterUser) -> Any:
    return service.get_need(need_id, _company(user))


@router.get(
    "/needs/{need_id}/categories",
    response_model=list[RecommendedCategory],
    summary="Рекомендованные категории с числом кандидатов",
    description="Основная категория, грейд ±1 и смежные специализации.",
    responses=error_responses(*AUTH, 404),
)
async def need_categories(need_id: int, user: RecruiterUser) -> Any:
    return service.recommended_categories(service.get_need(need_id, _company(user)))


@router.get(
    "/needs/{need_id}/candidates",
    response_model=MatchList,
    summary="Подборка: кандидаты категории с объяснением и разбивкой счёта",
    description=(
        "Кандидаты обезличены. Фильтры сужают подборку, `total_before_filters` — исходный размер; "
        "без фильтров возвращается исходный список."
    ),
    responses=error_responses(*AUTH, 404, 422),
)
async def need_candidates(
    need_id: int,
    user: RecruiterUser,
    category: Annotated[str | None, Query(examples=["backend:middle"])] = None,
    skills: Annotated[list[str] | None, Query()] = None,
    has_fsp: bool | None = None,
    work_format: WorkFormat | None = None,
    city: str | None = None,
) -> Any:
    need = service.get_need(need_id, _company(user))
    return service.matches(need, category, skills or [], has_fsp, work_format, city)
