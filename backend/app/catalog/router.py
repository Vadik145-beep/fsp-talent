"""Справочники (публичные, без авторизации)."""

from typing import Any

from fastapi import APIRouter, Query

from app.catalog.schemas import (
    Category,
    DeclineReasonItem,
    Grade,
    Skill,
    Specialization,
    Topic,
)
from app.catalog.service import CatalogService
from app.common.enums import SpecializationCode

router = APIRouter(prefix="/catalog", tags=["catalog"])
service = CatalogService()


@router.get("/specializations", response_model=list[Specialization], summary="Специализации")
async def list_specializations() -> Any:
    return service.specializations()


@router.get("/grades", response_model=list[Grade], summary="Грейды")
async def list_grades() -> Any:
    return service.grades()


@router.get(
    "/categories", response_model=list[Category], summary="Категории (специализация × грейд)"
)
async def list_categories(specialization: SpecializationCode | None = None) -> Any:
    return service.categories(specialization)


@router.get("/topics", response_model=list[Topic], summary="Темы теста")
async def list_topics(specialization: SpecializationCode | None = None) -> Any:
    return service.topics(specialization)


@router.get("/skills", response_model=list[Skill], summary="Справочник стека")
async def list_skills(
    specialization: SpecializationCode | None = None,
    q: str | None = Query(default=None, max_length=50, description="Поиск по названию"),
) -> Any:
    return service.skills(specialization, q)


@router.get(
    "/decline-reasons",
    response_model=list[DeclineReasonItem],
    summary="Причины отказа от приглашения",
)
async def list_decline_reasons() -> Any:
    return service.decline_reasons()
