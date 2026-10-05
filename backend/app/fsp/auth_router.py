"""Вход и привязка через ФСП ID (Keycloak, OIDC Authorization Code + PKCE S256).

Пути остаются под /api/auth/*, но код живёт в модуле fsp, чтобы авторизация и ФСП
развивались независимо. Как устроен протокол — `app/fsp/oidc.py`.
"""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Cookie, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import FspAuthorizeUrl, TokenResponse
from app.auth.sessions import issue_session
from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import AppError, error_responses
from app.core.security import CandidateUser
from app.fsp.oidc import (
    STATE_COOKIE,
    STATE_COOKIE_PATH,
    FspIdentity,
    KeycloakClient,
    KeycloakUnavailableError,
    OidcError,
    OidcState,
    Purpose,
    decode_state,
    encode_state,
    get_keycloak_client,
)
from app.fsp.registry import RegistryClient, get_registry_client
from app.fsp.schemas import FspCodeExchange, FspStatus
from app.fsp.service import FspService
from app.fsp.settings import get_fsp_settings

router = APIRouter(prefix="/auth", tags=["auth"])

Session = Annotated[AsyncSession, Depends(get_session)]
Keycloak = Annotated[KeycloakClient, Depends(get_keycloak_client)]
Registry = Annotated[RegistryClient, Depends(get_registry_client)]
StateCookie = Annotated[str | None, Cookie(alias=STATE_COOKIE, include_in_schema=False)]

KEYCLOAK_UNAVAILABLE = (503, "keycloak_unavailable", "Сервис ФСП ID недоступен")
OIDC_ERROR = (
    400,
    "oidc_error",
    "Ошибка входа через ФСП ID: state истёк/подменён, код не принят или ID-токен не прошёл "
    "проверку (причина в details.reason)",
)


def keycloak_unavailable() -> AppError:
    return AppError(
        503,
        "keycloak_unavailable",
        "Сервис ФСП ID временно недоступен. Войдите по почте и паролю.",
    )


def _set_state_cookie(response: Response, value: str) -> None:
    response.set_cookie(
        STATE_COOKIE,
        value,
        max_age=get_fsp_settings().oidc_state_ttl_sec,
        httponly=True,
        samesite="lax",
        secure=get_settings().app_env != "dev",
        path=STATE_COOKIE_PATH,
    )


def _clear_state_cookie(response: Response) -> None:
    response.delete_cookie(STATE_COOKIE, path=STATE_COOKIE_PATH)


async def _identity(
    body: FspCodeExchange,
    cookie: str | None,
    purpose: Purpose,
    keycloak: KeycloakClient,
    response: Response,
) -> FspIdentity:
    """state из cookie → обмен кода → проверенный ID-токен. Cookie одноразовая."""
    _clear_state_cookie(response)
    try:
        st = decode_state(cookie, body.state, purpose)
        if body.redirect_uri is not None and body.redirect_uri != st.redirect_uri:
            raise OidcError("redirect_uri_mismatch", "redirect_uri не совпадает с authorize-url")
        return await keycloak.identity_from_code(body.code, st)
    except KeycloakUnavailableError as exc:
        raise keycloak_unavailable() from exc
    except OidcError as exc:
        raise AppError(
            400, "oidc_error", exc.message, {"reason": exc.reason, **exc.details}
        ) from exc


@router.get(
    "/fsp/authorize-url",
    response_model=FspAuthorizeUrl,
    summary="Ссылка на вход/привязку через ФСП ID",
    description=(
        "Генерирует state, nonce и PKCE code_verifier, хранит их в подписанной httpOnly cookie "
        "`fsp_oidc_state` (10 минут, путь /api/auth) и отдаёт адрес страницы входа Keycloak "
        "с `code_challenge` (S256). Если Keycloak не отвечает — 503, основной вход не затронут."
    ),
    responses=error_responses(KEYCLOAK_UNAVAILABLE, 422),
)
async def fsp_authorize_url(
    response: Response,
    keycloak: Keycloak,
    purpose: Annotated[Literal["login", "link"], Query()] = "login",
    redirect_uri: Annotated[
        str | None,
        Query(
            max_length=2048,
            description="Куда Keycloak вернёт браузер (по умолчанию <фронт>/auth/fsp-callback)",
        ),
    ] = None,
) -> Any:
    target = redirect_uri or f"{get_settings().public_frontend_url.rstrip('/')}/auth/fsp-callback"
    try:
        await keycloak.check_available()
    except KeycloakUnavailableError as exc:
        raise keycloak_unavailable() from exc
    st = OidcState.new(purpose, target)
    _set_state_cookie(response, encode_state(st))
    return {"authorize_url": keycloak.authorize_url(st), "state": st.state, "purpose": purpose}


@router.post(
    "/fsp/login",
    response_model=TokenResponse,
    summary="Вход через ФСП ID (обмен кода Keycloak на сессию)",
    description=(
        "Код и state из redirect_uri → проверка ID-токена → профиль с этим `fsp_id` → сессия. "
        "Вход работает только для уже привязанного ФСП ID."
    ),
    responses=error_responses(
        OIDC_ERROR,
        (404, "fsp_account_not_linked", "ФСП ID не привязан ни к одному профилю"),
        KEYCLOAK_UNAVAILABLE,
        422,
    ),
)
async def fsp_login(
    body: FspCodeExchange,
    response: Response,
    session: Session,
    keycloak: Keycloak,
    cookie: StateCookie = None,
) -> Any:
    identity = await _identity(body, cookie, "login", keycloak, response)
    user_id = await FspService(session).login_user_id(identity.fsp_id)
    return issue_session(response, user_id)


@router.post(
    "/fsp-link",
    response_model=FspStatus,
    summary="Привязать ФСП ID к профилю",
    description=(
        "Обмен кода Keycloak, claim `fsp_id` → привязка к текущему кандидату и сразу "
        "синхронизация достижений из реестра. Если реестр недоступен, привязка сохраняется, "
        "достижения подтянутся по кнопке «Обновить» (сообщение в `message`)."
    ),
    responses=error_responses(
        401,
        403,
        404,
        OIDC_ERROR,
        (409, "fsp_id_taken", "Этот ФСП ID уже привязан к другому профилю"),
        (409, "fsp_already_linked", "К профилю уже привязан другой ФСП ID"),
        KEYCLOAK_UNAVAILABLE,
        422,
    ),
)
async def fsp_link(
    body: FspCodeExchange,
    response: Response,
    user: CandidateUser,
    session: Session,
    keycloak: Keycloak,
    registry: Registry,
    cookie: StateCookie = None,
) -> Any:
    if user.candidate_id is None:
        raise AppError(404, "not_found", "Профиль кандидата не найден")
    identity = await _identity(body, cookie, "link", keycloak, response)
    service = FspService(session, registry)
    return await service.link(user.candidate_id, identity.fsp_id, identity.sub)


@router.delete(
    "/fsp-link",
    response_model=FspStatus,
    summary="Отвязать ФСП ID",
    description=(
        "Связь и кэш достижений удаляются: бейджи и ФСП-скор пропадают из профиля и выдачи. "
        "Основной вход не меняется."
    ),
    responses=error_responses(401, 403, 404, (409, "fsp_not_linked", "ФСП ID не привязан")),
)
async def fsp_unlink(user: CandidateUser, session: Session) -> Any:
    if user.candidate_id is None:
        raise AppError(404, "not_found", "Профиль кандидата не найден")
    return await FspService(session).unlink(user.candidate_id)
