"""Достижения ФСП соискателя. Привязка ФСП ID — в `auth` (`/api/auth/fsp-link`)."""

from typing import Any

from fastapi import APIRouter

from app.core.errors import AppError, error_responses
from app.core.security import CandidateUser, CurrentUser
from app.fsp.schemas import FspAchievement, FspStatus
from app.fsp.service import FspService

router = APIRouter(prefix="/fsp", tags=["fsp"])
service = FspService()


def _cid(user: CurrentUser) -> int:
    if user.candidate_id is None:
        raise AppError(404, "not_found", "Профиль кандидата не найден")
    return user.candidate_id


@router.get(
    "/status",
    response_model=FspStatus,
    summary="Статус привязки ФСП ID, ФСП-скор и бейджи",
    description="Без истории ФСП — нейтральное состояние без штрафа (T5.4).",
    responses=error_responses(401, 403, 404),
)
async def fsp_status(user: CandidateUser) -> Any:
    return service.status(_cid(user))


@router.get(
    "/achievements",
    response_model=list[FspAchievement],
    summary="Достижения ФСП (подтверждено ФСП)",
    description="Пустой список, если ФСП ID не привязан или истории нет.",
    responses=error_responses(401, 403, 404),
)
async def fsp_achievements(user: CandidateUser) -> Any:
    return service.achievements(_cid(user))


@router.post(
    "/sync",
    response_model=FspStatus,
    summary="Обновить достижения из реестра ФСП",
    description="Заглушка: синхронизация с `fsp-registry-mock` — волна 2c.",
    responses=error_responses(
        401,
        403,
        (409, "fsp_not_linked", "ФСП ID не привязан"),
        (503, "fsp_registry_unavailable", "Реестр ФСП недоступен, данные из кэша"),
    ),
)
async def fsp_sync(user: CandidateUser) -> Any:
    status = service.status(_cid(user))
    if not status["linked"]:
        raise AppError(409, "fsp_not_linked", "ФСП ID не привязан")
    return status
