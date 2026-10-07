"""Интеграция с ATS: API-токены, вебхуки (администратор компании) и выгрузка по токену.

Роутер без своего префикса: подключён внутрь роутера компаний (`/api/companies/...`).
"""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import error_responses
from app.core.security import RecruiterUser
from app.integrations.schemas import (
    ApiToken,
    ApiTokenCreate,
    ApiTokenIssued,
    CompanyExport,
    Webhook,
    WebhookCreate,
    WebhookCreated,
    WebhookDeliveryOut,
)
from app.integrations.service import IntegrationService, company_by_token, export_company

router = APIRouter(tags=["companies"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
api_token_header = APIKeyHeader(
    name="X-Api-Token",
    auto_error=False,
    description="API-токен компании (`POST /api/companies/my/api-tokens`)",
)
ADMIN_ONLY = (403, "forbidden", "Интеграциями управляет только администратор компании")
AUTH = (401, ADMIN_ONLY)


@router.get(
    "/my/api-tokens",
    response_model=list[ApiToken],
    summary="API-токены компании для ATS",
    responses=error_responses(*AUTH),
)
async def list_api_tokens(user: RecruiterUser, session: SessionDep) -> Any:
    return await IntegrationService(session, user).tokens()


@router.post(
    "/my/api-tokens",
    response_model=ApiTokenIssued,
    status_code=status.HTTP_201_CREATED,
    summary="Выпустить API-токен",
    description="Токен показывается один раз; в БД хранится только его хеш.",
    responses=error_responses(*AUTH, 422),
)
async def issue_api_token(body: ApiTokenCreate, user: RecruiterUser, session: SessionDep) -> Any:
    return await IntegrationService(session, user).issue_token(body)


@router.delete(
    "/my/api-tokens/{token_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Отозвать API-токен",
    responses=error_responses(*AUTH, 404),
)
async def revoke_api_token(token_id: int, user: RecruiterUser, session: SessionDep) -> Response:
    await IntegrationService(session, user).revoke_token(token_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/my/webhooks",
    response_model=list[Webhook],
    summary="Вебхуки компании",
    responses=error_responses(*AUTH),
)
async def list_webhooks(user: RecruiterUser, session: SessionDep) -> Any:
    return await IntegrationService(session, user).webhooks()


@router.post(
    "/my/webhooks",
    response_model=WebhookCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить вебхук",
    description=(
        "События: `invitation.accepted` (кандидат принял приглашение), `application.created` "
        "(новый отклик). Каждый запрос подписан: `X-FSP-Signature: sha256=<HMAC-SHA256(secret, "
        "X-FSP-Timestamp + '.' + тело)>`. Не 2xx — повтор с паузами до 5 попыток."
    ),
    responses=error_responses(
        *AUTH, 422, (422, "invalid_webhook_url", "Адрес должен начинаться с http:// или https://")
    ),
)
async def create_webhook(body: WebhookCreate, user: RecruiterUser, session: SessionDep) -> Any:
    return await IntegrationService(session, user).create_webhook(body)


@router.delete(
    "/my/webhooks/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Удалить вебхук",
    responses=error_responses(*AUTH, 404),
)
async def delete_webhook(webhook_id: int, user: RecruiterUser, session: SessionDep) -> Response:
    await IntegrationService(session, user).delete_webhook(webhook_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/my/webhooks/{webhook_id}/ping",
    response_model=WebhookDeliveryOut,
    summary="Проверить вебхук: отправить событие ping",
    responses=error_responses(*AUTH, 404),
)
async def ping_webhook(webhook_id: int, user: RecruiterUser, session: SessionDep) -> Any:
    return await IntegrationService(session, user).ping_webhook(webhook_id)


@router.get(
    "/my/webhooks/{webhook_id}/deliveries",
    response_model=list[WebhookDeliveryOut],
    summary="Журнал доставок вебхука",
    responses=error_responses(*AUTH, 404, 422),
)
async def webhook_deliveries(
    webhook_id: int,
    user: RecruiterUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Any:
    return await IntegrationService(session, user).deliveries(webhook_id, limit)


@router.get(
    "/ats/export",
    response_model=CompanyExport,
    summary="Выгрузка данных компании для ATS (по API-токену)",
    description=(
        "Авторизация — заголовок `X-Api-Token` (без входа пользователя). Вакансии, приглашения "
        "(контакты — только у принятых) и отклики с контактами. `since` — только изменённые "
        "после этого момента (для инкрементальной синхронизации)."
    ),
    responses=error_responses(
        (401, "invalid_api_token", "API-токен не найден или отозван"),
        (403, "company_blocked", "Компания заблокирована администратором платформы"),
        422,
    ),
)
async def ats_export(
    session: SessionDep,
    token: Annotated[str | None, Security(api_token_header)] = None,
    since: Annotated[
        datetime | None, Query(description="ISO-время, например 2026-10-01T00:00:00+03:00")
    ] = None,
) -> Any:
    company = await company_by_token(session, token)
    return await export_company(session, company, since)
