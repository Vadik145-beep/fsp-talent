"""Регистрация, вход, подтверждение почты, refresh, выход, вход и привязка через ФСП ID."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Cookie, Query, Response, status

from app.auth.schemas import (
    FspAuthorizeUrl,
    FspCodeExchange,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.auth.service import AuthService
from app.common.schemas import MessageResponse
from app.core.config import get_settings
from app.core.errors import AppError, error_responses
from app.core.security import AnyUser, CandidateUser
from app.fsp.schemas import FspStatus
from app.fsp.service import FspService
from app.users.schemas import Me

router = APIRouter(prefix="/auth", tags=["auth"])
service = AuthService()
fsp_service = FspService()

REFRESH_COOKIE = "refresh_token"


def _set_refresh_cookie(response: Response, user_id: int) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        f"demo-refresh.{user_id}",
        httponly=True,
        samesite="lax",
        secure=get_settings().app_env != "dev",
        max_age=get_settings().refresh_token_ttl_days * 86400,
        path="/api/auth",
    )


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация по почте",
    description=(
        "Соискатель или рекрутер (рекрутер создаёт компанию или вступает по коду). "
        "Согласие на обработку ПДн обязательно. Отправляется письмо со ссылкой (24 ч)."
    ),
    responses=error_responses(
        (409, "email_taken", "Пользователь с такой почтой уже есть"),
        (404, "company_invite_not_found", "Код приглашения в компанию не найден"),
        422,
    ),
)
async def register(body: RegisterRequest) -> Any:
    return service.register(str(body.email))


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    summary="Подтвердить почту по токену из письма",
    responses=error_responses(
        (400, "token_invalid", "Ссылка недействительна"),
        (410, "token_expired", "Срок действия ссылки истёк, запросите новую"),
        422,
    ),
)
async def verify_email(body: VerifyEmailRequest) -> Any:
    return service.verify_email(body.token)


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Отправить письмо повторно",
    responses=error_responses((429, "too_many_requests", "Повторить можно через минуту"), 422),
)
async def resend_verification(body: ResendVerificationRequest) -> Any:
    return {"ok": True, "message": "Если почта зарегистрирована, письмо отправлено повторно"}


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Вход по почте и паролю",
    description="Access-токен в теле, refresh — в httpOnly cookie `refresh_token`.",
    responses=error_responses(
        (401, "invalid_credentials", "Неверная почта или пароль"),
        (403, "email_not_verified", "Подтвердите почту по ссылке из письма"),
        (403, "user_blocked", "Учётная запись заблокирована"),
        (429, "too_many_attempts", "Слишком много попыток, попробуйте через 15 минут"),
        422,
    ),
)
async def login(body: LoginRequest, response: Response) -> Any:
    token = service.login(str(body.email), body.password)
    _set_refresh_cookie(response, token["user"]["id"])
    return token


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Обновить access-токен по refresh-cookie",
    responses=error_responses((401, "invalid_refresh_token", "Сессия истекла, войдите снова")),
)
async def refresh(
    response: Response,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> Any:
    token = service.refresh(refresh_token)
    _set_refresh_cookie(response, token["user"]["id"])
    return token


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Выход",
    response_class=Response,
)
async def logout() -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth")
    return response


@router.get(
    "/me", response_model=Me, summary="Текущий пользователь", responses=error_responses(401)
)
async def me(user: AnyUser) -> Any:
    return service.me(user)


@router.post(
    "/password-reset/request",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Запросить сброс пароля",
    responses=error_responses(429, 422),
)
async def password_reset_request(body: PasswordResetRequest) -> Any:
    return {"ok": True, "message": "Если почта зарегистрирована, мы отправили ссылку для сброса"}


@router.post(
    "/password-reset/confirm",
    response_model=MessageResponse,
    summary="Задать новый пароль по токену",
    responses=error_responses(
        (400, "token_invalid", "Ссылка недействительна"),
        (410, "token_expired", "Срок действия ссылки истёк"),
        422,
    ),
)
async def password_reset_confirm(body: PasswordResetConfirm) -> Any:
    service.verify_email(body.token)
    return {"ok": True, "message": "Пароль изменён"}


# ---------- ФСП ID (Keycloak, OIDC Authorization Code + PKCE) ----------


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
