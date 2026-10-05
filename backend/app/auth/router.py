"""Регистрация, вход, подтверждение почты, refresh, выход. ФСП ID — в app/fsp/auth_router.py."""

from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.bootstrap import auth_lifespan
from app.auth.schemas import (
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.auth.service import AuthLinks, AuthService
from app.auth.sessions import REFRESH_COOKIE, clear_refresh_cookie, set_refresh_cookie
from app.common.schemas import MessageResponse
from app.core.db import get_session
from app.core.errors import error_responses
from app.core.security import AnyUser
from app.users.schemas import Me

router = APIRouter(prefix="/auth", tags=["auth"], lifespan=auth_lifespan)
# ссылки на Keycloak и заглушка входа через ФСП ID; импортируется модулем fsp
service = AuthLinks()

Db = Annotated[AsyncSession, Depends(get_session)]
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


def _client(request: Request) -> tuple[str | None, str | None]:
    """(User-Agent, IP) запроса — для журнала сессий и лимита попыток входа."""
    ip = request.client.host if request.client else None
    return request.headers.get("user-agent"), ip


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация по почте",
    description=(
        "Соискатель или рекрутер (рекрутер создаёт компанию или вступает по коду). "
        "Согласие на обработку ПДн обязательно — сохраняется с версией текста и датой. "
        "Отправляется письмо со ссылкой `/verify-email?token=...` (24 ч). Повторная регистрация "
        "неподтверждённой почты не меняет данные, а только отправляет письмо заново."
    ),
    responses=error_responses(
        (409, "email_taken", "Пользователь с такой почтой уже есть"),
        (404, "company_invite_not_found", "Код приглашения в компанию не найден"),
        422,
    ),
)
async def register(body: RegisterRequest, db: Db) -> Any:
    return await AuthService(db).register(body)


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
async def verify_email(body: VerifyEmailRequest, db: Db) -> Any:
    return await AuthService(db).verify_email(body.token)


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Отправить письмо повторно",
    description="Ответ одинаковый, есть такая почта или нет. Не чаще раза в минуту на почту.",
    responses=error_responses((429, "too_many_requests", "Повторить можно через минуту"), 422),
)
async def resend_verification(body: ResendVerificationRequest, db: Db) -> Any:
    return await AuthService(db).resend_verification(str(body.email))


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Вход по почте и паролю",
    description=(
        "Access-токен (JWT, 15 мин) в теле — передавать в `Authorization: Bearer <token>`; "
        "refresh — в httpOnly cookie `refresh_token`. Не больше 5 неудачных попыток "
        "за 15 минут на пару почта+IP."
    ),
    responses=error_responses(
        (401, "invalid_credentials", "Неверная почта или пароль"),
        (403, "email_not_verified", "Подтвердите почту по ссылке из письма"),
        (403, "user_blocked", "Учётная запись заблокирована"),
        (429, "too_many_attempts", "Слишком много попыток, попробуйте через 15 минут"),
        422,
    ),
)
async def login(body: LoginRequest, request: Request, response: Response, db: Db) -> Any:
    user_agent, ip = _client(request)
    service_ = AuthService(db)
    user = await service_.authenticate(str(body.email), body.password, ip)
    token_body, refresh_token = await service_.start_session(user, user_agent, ip)
    set_refresh_cookie(response, user.user_id, refresh_token)
    return token_body


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Обновить access-токен по refresh-cookie",
    description="Refresh-токен ротируется: старый перестаёт действовать, в cookie — новый.",
    responses=error_responses(
        (401, "invalid_refresh_token", "Сессия истекла, войдите снова"),
        (403, "user_blocked", "Учётная запись заблокирована"),
    ),
)
async def refresh(
    request: Request, response: Response, db: Db, refresh_token: RefreshCookie = None
) -> Any:
    user_agent, ip = _client(request)
    token_body, new_token = await AuthService(db).refresh(refresh_token, user_agent, ip)
    set_refresh_cookie(response, token_body["user"]["id"], new_token)
    return token_body


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Выход",
    description="Отзывает refresh-сессию из cookie и удаляет cookie.",
    response_class=Response,
)
async def logout(db: Db, refresh_token: RefreshCookie = None) -> Response:
    await AuthService(db).logout(refresh_token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_refresh_cookie(response)
    return response


@router.get(
    "/me", response_model=Me, summary="Текущий пользователь", responses=error_responses(401)
)
async def me(user: AnyUser, db: Db) -> Any:
    return await AuthService(db).me(user)


@router.post(
    "/password-reset/request",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Запросить сброс пароля",
    description=(
        "Письмо со ссылкой `/reset-password?token=...` (60 мин). Ответ одинаковый, есть такая "
        "почта или нет. Не чаще раза в минуту на почту."
    ),
    responses=error_responses(429, 422),
)
async def password_reset_request(body: PasswordResetRequest, db: Db) -> Any:
    return await AuthService(db).request_password_reset(str(body.email))


@router.post(
    "/password-reset/confirm",
    response_model=MessageResponse,
    summary="Задать новый пароль по токену",
    description="Все refresh-сессии пользователя отзываются.",
    responses=error_responses(
        (400, "token_invalid", "Ссылка недействительна"),
        (410, "token_expired", "Срок действия ссылки истёк"),
        422,
    ),
)
async def password_reset_confirm(body: PasswordResetConfirm, db: Db) -> Any:
    return await AuthService(db).confirm_password_reset(body.token, body.new_password)
