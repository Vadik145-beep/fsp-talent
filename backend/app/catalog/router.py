"""Справочники (публичные, без авторизации). Данные — из БД; изменения — в админке."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.schemas import (
    Category,
    DeclineReasonItem,
    Grade,
    SkillWithAliases,
    Specialization,
    Topic,
)
from app.catalog.service import CatalogDbService, CatalogService
from app.common.enums import SpecializationCode
from app.core.db import get_session
from app.nlp.skills_lexicon import skill_aliases

router = APIRouter(prefix="/catalog", tags=["catalog"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/specializations", response_model=list[Specialization], summary="Специализации")
async def list_specializations(session: SessionDep) -> Any:
    return await CatalogDbService(session).specializations()


@router.get("/grades", response_model=list[Grade], summary="Грейды")
async def list_grades(session: SessionDep) -> Any:
    return await CatalogDbService(session).grades()


@router.get(
    "/categories", response_model=list[Category], summary="Категории (специализация × грейд)"
)
async def list_categories(
    session: SessionDep, specialization: SpecializationCode | None = None
) -> Any:
    return await CatalogDbService(session).categories(specialization)


@router.get("/topics", response_model=list[Topic], summary="Темы теста")
async def list_topics(session: SessionDep, specialization: SpecializationCode | None = None) -> Any:
    return await CatalogDbService(session).topics(specialization)


@router.get("/skills", response_model=list[SkillWithAliases], summary="Справочник стека")
async def list_skills(
    session: SessionDep,
    specialization: SpecializationCode | None = None,
    q: str | None = Query(default=None, max_length=50, description="Поиск по названию"),
) -> Any:
    items = await CatalogDbService(session).skills(specialization, q)
    # синонимы и сленг — тот же словарь, что у разбора потребности и резюме
    return [{**s, "aliases": skill_aliases(s["id"], s["label"])} for s in items]


@router.get(
    "/decline-reasons",
    response_model=list[DeclineReasonItem],
    summary="Причины отказа от приглашения",
)
async def list_decline_reasons() -> Any:
    return CatalogService().decline_reasons()
