"""Достижения ФСП соискателя и вебхук реестра. Привязка ФСП ID — `/api/auth/fsp-link`."""

import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import AppError, error_responses
from app.core.security import CandidateUser, CurrentUser
from app.fsp.registry import RegistryClient, RegistryError, get_registry_client
from app.fsp.schemas import FspAchievement, FspStatus, FspWebhookAck, FspWebhookEvent
from app.fsp.service import WEBHOOK_EVENT_UPDATED, FspService, registry_app_error
from app.fsp.settings import get_fsp_settings

logger = logging.getLogger("app.fsp.router")

router = APIRouter(prefix="/fsp", tags=["fsp"])

Session = Annotated[AsyncSession, Depends(get_session)]
Registry = Annotated[RegistryClient, Depends(get_registry_client)]

SIGNATURE_HEADER = "X-FSP-Signature"


def _cid(user: CurrentUser) -> int:
    if user.candidate_id is None:
        raise AppError(404, "not_found", "Профиль кандидата не найден")
    return user.candidate_id


@router.get(
    "/status",
    response_model=FspStatus,
    summary="Статус привязки ФСП ID, ФСП-скор и бейджи",
    description=(
        "Данные из БД (кэш реестра). Без ФСП ID или без истории — нейтральное состояние "
        "без штрафа (T5.4): `fsp_score: null`, пустые бейджи и подсказка в `message`."
    ),
    responses=error_responses(401, 403, 404),
)
async def fsp_status(user: CandidateUser, session: Session) -> Any:
    return await FspService(session).status(_cid(user))


@router.get(
    "/achievements",
    response_model=list[FspAchievement],
    summary="Достижения ФСП (подтверждено ФСП)",
    description="Новые сверху. Пустой список, если ФСП ID не привязан или истории нет.",
    responses=error_responses(401, 403, 404),
)
async def fsp_achievements(user: CandidateUser, session: Session) -> Any:
    return await FspService(session).achievements(_cid(user))


@router.post(
    "/sync",
    response_model=FspStatus,
    summary="Обновить достижения из реестра ФСП",
    description="Кнопка «Обновить»: перечитывает достижения участника из реестра в кэш.",
    responses=error_responses(
        401,
        403,
        (409, "fsp_not_linked", "ФСП ID не привязан"),
        (503, "fsp_registry_unavailable", "Реестр ФСП недоступен, данные из кэша"),
    ),
)
async def fsp_sync(user: CandidateUser, session: Session, registry: Registry) -> Any:
    return await FspService(session, registry).refresh(_cid(user))


def verify_signature(body: bytes, signature: str | None, secret: str) -> bool:
    """HMAC-SHA256 тела общим секретом. Заголовок: `sha256=<hex>` или просто `<hex>`."""
    if not signature or not secret:
        return False
    provided = signature.strip()
    if provided.lower().startswith("sha256="):
        provided = provided[7:]
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided.lower())


@router.post(
    "/webhook",
    response_model=FspWebhookAck,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Вебхук реестра ФСП: достижения участника изменились",
    description=(
        "Реестр сообщает об изменении — платформа сразу перечитывает достижения участника. "
        "Тело подписывается HMAC-SHA256 общим секретом (`FSP_WEBHOOK_SECRET`), заголовок "
        "`X-FSP-Signature: sha256=<hex>`. Событие `participant.achievements_updated` → "
        "пересинхронизация; другие события и непривязанные ФСП ID принимаются и игнорируются. "
        "Повтор события безопасен: синхронизация заменяет кэш целиком, дублей нет."
    ),
    responses=error_responses(
        (401, "invalid_signature", "Неверная подпись вебхука"),
        (401, "webhook_expired", "Событие устарело (sent_at старше 5 минут)"),
        (422, "validation_error", "Неверное тело события"),
        (503, "fsp_registry_unavailable", "Реестр ФСП недоступен — повторите позже"),
        (503, "webhook_disabled", "Секрет вебхука не настроен"),
    ),
)
async def fsp_webhook(
    request: Request,
    session: Session,
    registry: Registry,
    x_fsp_signature: Annotated[
        str | None, Header(alias=SIGNATURE_HEADER, description="sha256=<hex HMAC тела>")
    ] = None,
) -> Any:
    settings = get_fsp_settings()
    if not settings.webhook_secret:
        raise AppError(503, "webhook_disabled", "Вебхук реестра ФСП не настроен")
    body = await request.body()
    if not verify_signature(body, x_fsp_signature, settings.webhook_secret):
        raise AppError(401, "invalid_signature", "Неверная подпись вебхука")
    try:
        event = FspWebhookEvent.model_validate(json.loads(body or b"null"))
    except (ValueError, ValidationError) as exc:
        details = (
            {"errors": exc.errors(include_url=False)} if isinstance(exc, ValidationError) else {}
        )
        raise AppError(422, "validation_error", "Неверное тело события", details) from exc
    if event.sent_at is not None:
        sent = event.sent_at if event.sent_at.tzinfo else event.sent_at.replace(tzinfo=UTC)
        if abs((datetime.now(UTC) - sent).total_seconds()) > settings.webhook_max_age_sec:
            raise AppError(401, "webhook_expired", "Событие вебхука устарело")
    ack: dict[str, Any] = {"event": event.event, "fsp_id": event.fsp_id}
    if event.event != WEBHOOK_EVENT_UPDATED:
        return {**ack, "resynced": False, "status": "ignored"}
    service = FspService(session, registry)
    try:
        link = await service.sync_fsp_id(event.fsp_id)
    except RegistryError as exc:
        raise registry_app_error(exc) from exc
    if link is None:
        return {**ack, "resynced": False, "status": "ignored"}
    count = len(await service.repo.achievements(event.fsp_id))
    logger.info("Вебхук ФСП %s (%s): %d достижений", event.fsp_id, event.event_id, count)
    return {**ack, "resynced": True, "achievements_count": count, "status": "resynced"}
