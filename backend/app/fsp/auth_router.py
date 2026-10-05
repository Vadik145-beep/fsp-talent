"""Вход и привязка через ФСП ID (Keycloak, OIDC Authorization Code + PKCE).

Пути остаются под /api/auth/*, но код живёт в модуле fsp, чтобы авторизация и ФСП
развивались независимо.
"""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, Response

from app.auth.router import _set_refresh_cookie
from app.auth.router import service as auth_service
from app.auth.schemas import FspAuthorizeUrl, FspCodeExchange, TokenResponse
from app.core.errors import AppError, error_responses
from app.core.security import CandidateUser
from app.fsp.schemas import FspStatus
from app.fsp.service import FspService

router = APIRouter(prefix="/auth", tags=["auth"])
service = auth_service
fsp_service = FspService()


@router.get(
    "/fsp/authorize-url",
    response_model=FspAuthorizeUrl,
    summary="Ссылка на вход/привязку через ФСП ID",
    responses=error_responses((503, "keycloak_unavailable", "Сервис ФСП ID недоступен"), 422),
)
async def fsp_authorize_url(
    purpose: Annotated[Literal["login", "link"], Query()] = "login",
    redirect_uri: str = "http://localhost:15173/auth/fsp-callback",
) -> Any:
    return service.fsp_authorize_url(purpose, redirect_uri)


@router.post(
    "/fsp/login",
    response_model=TokenResponse,
    summary="Вход через ФСП ID (обмен кода Keycloak на сессию)",
    description="Заглушка: возвращает сессию демо-соискателя. Настоящий OIDC — волна 2c.",
    responses=error_responses(
        (400, "oidc_error", "Ошибка обмена кода авторизации"),
        (404, "fsp_account_not_linked", "ФСП ID не привязан ни к одному профилю"),
        (503, "keycloak_unavailable", "Сервис ФСП ID недоступен"),
        422,
    ),
)
async def fsp_login(body: FspCodeExchange, response: Response) -> Any:
    token = service.fsp_login()
    _set_refresh_cookie(response, token["user"]["id"])
    return token


@router.post(
    "/fsp-link",
    response_model=FspStatus,
    summary="Привязать ФСП ID к профилю",
    description="Обмен кода Keycloak, claim `fsp_id` → профиль, синхронизация достижений.",
    responses=error_responses(
        401,
        403,
        (400, "oidc_error", "Ошибка обмена кода авторизации"),
        (409, "fsp_id_taken", "Этот ФСП ID уже привязан к другому профилю"),
        (503, "keycloak_unavailable", "Сервис ФСП ID недоступен"),
        422,
    ),
)
async def fsp_link(body: FspCodeExchange, user: CandidateUser) -> Any:
    if user.candidate_id is None:
        raise AppError(404, "not_found", "Профиль кандидата не найден")
    current = fsp_service.status(user.candidate_id)
    if current["linked"]:
        return current
    # заглушка: привязываем первый «свободный» ID без истории
    return fsp_service.status(user.candidate_id, fsp_id_override="FSP-000036")


@router.delete(
    "/fsp-link",
    response_model=FspStatus,
    summary="Отвязать ФСП ID",
    description="Достижения скрываются из профиля и выдачи; основной вход не меняется.",
    responses=error_responses(401, 403, (409, "fsp_not_linked", "ФСП ID не привязан")),
)
async def fsp_unlink(user: CandidateUser) -> Any:
    return fsp_service.unlinked()
