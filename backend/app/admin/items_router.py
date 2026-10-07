"""Админка: банк задач (метрики, предпросмотр вариантов, вывод из оборота, калибровка, утечки).

Отдельный файл, чтобы банк задач (волна 3a) развивался независимо от остальной админки.
Логика — `app.testing.items_admin.ItemsAdminService` (БД + движок теста).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.schemas import CoverageCell, ItemDetail, ItemSummary, RecalibrationResult
from app.common.enums import ItemStatus, SpecializationCode
from app.common.schemas import Page
from app.core.db import get_session
from app.core.errors import error_responses
from app.core.security import AdminUser
from app.testing.admin_schemas import LeakScanResult
from app.testing.items_admin import ItemsAdminService

router = APIRouter(prefix="/admin", tags=["admin"])

AUTH = (401, 403)
TRANSITION = (409, "invalid_transition", "Действие недоступно в текущем статусе")
PageNum = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=200)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get(
    "/items",
    response_model=Page[ItemSummary],
    summary="Банк задач с метриками",
    description=(
        "Показы, доля верных (факт и ожидание по IRT при θ без этой задачи), a, b, статус, "
        "флаг утечки. Шаблоны движка синхронизируются в БД автоматически."
    ),
    responses=error_responses(*AUTH, 422),
)
async def list_items(
    user: AdminUser,
    session: SessionDep,
    specialization: SpecializationCode | None = None,
    topic: str | None = None,
    item_status: Annotated[ItemStatus | None, Query(alias="status")] = None,
    leak_flag: bool | None = None,
    page: PageNum = 1,
    page_size: PageSize = 50,
) -> Any:
    return await ItemsAdminService(session, user).items(
        specialization, topic, item_status, leak_flag, page, page_size
    )


@router.get(
    "/items/coverage",
    response_model=list[CoverageCell],
    summary="Покрытие банка: темы × грейды",
    responses=error_responses(*AUTH),
)
async def items_coverage(user: AdminUser, session: SessionDep) -> Any:
    return await ItemsAdminService(session, user).coverage()


@router.post(
    "/items/recalibrate",
    response_model=RecalibrationResult,
    summary="Пересчитать калибровку a, b по накопленным ответам",
    description=(
        "T4.9: логистическая регрессия ответа на θ отвечавших (без этой задачи) для шаблонов "
        "с числом ответов не меньше `min_responses` (по умолчанию TESTING_CALIBRATION_MIN_RESPONSES"
        "=30). Пилотные шаблоны становятся рабочими по правилу активации движка "
        "(≥ 150 ответов, a ≥ 0,4, |b| ≤ 3,5, SE(b) ≤ 0,35). Изменения пишутся в журнал."
    ),
    responses=error_responses(*AUTH, (409, "recalibration_running", "Пересчёт уже идёт")),
)
async def recalibrate(
    user: AdminUser,
    session: SessionDep,
    min_responses: Annotated[int | None, Query(ge=1, le=100000)] = None,
) -> Any:
    return await ItemsAdminService(session, user).recalibrate(min_responses)


@router.post(
    "/items/leak-scan",
    response_model=LeakScanResult,
    summary="Запустить детектор утечек",
    description=(
        "T4.7: по каждому шаблону — доля верных против ожидаемой по IRT и быстрые верные "
        "ответы. Помеченные шаблоны выводятся из оборота, событие пишется в журнал. "
        "Плюс аномалии кандидатов (повод для ручной проверки). Детектор также запускается "
        "автоматически после каждой N-й завершённой сессии (TESTING_LEAK_SCAN_EVERY)."
    ),
    responses=error_responses(*AUTH),
)
async def leak_scan(user: AdminUser, session: SessionDep) -> Any:
    return await ItemsAdminService(session, user).leak_scan()


@router.get(
    "/items/{item_id}",
    response_model=ItemDetail,
    summary="Шаблон: метрики и предпросмотр 3 вариантов",
    description="Варианты генерирует движок из разных seed; у демо-записей — из фикстуры.",
    responses=error_responses(*AUTH, 404),
)
async def get_item(item_id: int, user: AdminUser, session: SessionDep) -> Any:
    return await ItemsAdminService(session, user).item(item_id)


@router.post(
    "/items/{item_id}/retire",
    response_model=ItemDetail,
    summary="Вывести шаблон из оборота",
    responses=error_responses(*AUTH, 404, TRANSITION),
)
async def retire_item(item_id: int, user: AdminUser, session: SessionDep) -> Any:
    return await ItemsAdminService(session, user).retire(item_id)


@router.post(
    "/items/{item_id}/approve",
    response_model=ItemDetail,
    summary="Одобрить черновик → пилот (непроверочный)",
    responses=error_responses(*AUTH, 404, TRANSITION),
)
async def approve_item(item_id: int, user: AdminUser, session: SessionDep) -> Any:
    return await ItemsAdminService(session, user).approve(item_id)
