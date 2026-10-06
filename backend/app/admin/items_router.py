"""Админка: банк задач (метрики, предпросмотр вариантов, вывод из оборота, калибровка).

Отдельный файл, чтобы банк задач (волна 3a) развивался независимо от остальной админки.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.admin.router import AUTH, TRANSITION, PageNum, PageSize, service
from app.admin.schemas import CoverageCell, ItemDetail, ItemSummary, RecalibrationResult
from app.common.enums import ItemStatus, SpecializationCode
from app.common.schemas import Page
from app.core.errors import error_responses
from app.core.security import AdminUser

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/items",
    response_model=Page[ItemSummary],
    summary="Банк задач с метриками",
    responses=error_responses(*AUTH, 422),
)
async def list_items(
    user: AdminUser,
    specialization: SpecializationCode | None = None,
    topic: str | None = None,
    item_status: Annotated[ItemStatus | None, Query(alias="status")] = None,
    leak_flag: bool | None = None,
    page: PageNum = 1,
    page_size: PageSize = 50,
) -> Any:
    return service.items(specialization, topic, item_status, leak_flag, page, page_size)


@router.get(
    "/items/coverage",
    response_model=list[CoverageCell],
    summary="Покрытие банка: темы × грейды",
    responses=error_responses(*AUTH),
)
async def items_coverage(user: AdminUser) -> Any:
    return service.coverage()


@router.post(
    "/items/recalibrate",
    response_model=RecalibrationResult,
    summary="Пересчитать калибровку a, b по накопленным ответам",
    description="Заглушка: настоящий пересчёт — волна 3a (T4.9).",
    responses=error_responses(*AUTH, (409, "recalibration_running", "Пересчёт уже идёт")),
)
async def recalibrate(user: AdminUser) -> Any:
    return service.recalibrate()


@router.get(
    "/items/{item_id}",
    response_model=ItemDetail,
    summary="Шаблон: метрики и предпросмотр 3 вариантов",
    responses=error_responses(*AUTH, 404),
)
async def get_item(item_id: int, user: AdminUser) -> Any:
    return service.item(item_id)


@router.post(
    "/items/{item_id}/retire",
    response_model=ItemDetail,
    summary="Вывести шаблон из оборота",
    responses=error_responses(*AUTH, 404, TRANSITION),
)
async def retire_item(item_id: int, user: AdminUser) -> Any:
    return service.retire_item(item_id)


@router.post(
    "/items/{item_id}/approve",
    response_model=ItemDetail,
    summary="Одобрить черновик → пилот (непроверочный)",
    responses=error_responses(*AUTH, 404, TRANSITION),
)
async def approve_item(item_id: int, user: AdminUser) -> Any:
    return service.approve_item(item_id)
