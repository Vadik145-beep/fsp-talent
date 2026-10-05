"""Регистрация, вход, подтверждение почты, refresh, выход. ФСП ID — в app/fsp/auth_router.py."""

from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Response, status

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
from app.auth.service import AuthService
from app.auth.sessions import clear_refresh_cookie, set_refresh_cookie
from app.common.schemas import MessageResponse
from app.core.errors import error_responses
from app.core.security import AnyUser
from app.users.schemas import Me

router = APIRouter(prefix="/auth", tags=["auth"])
service = AuthService()


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
    set_refresh_cookie(response, token["user"]["id"])
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
    set_refresh_cookie(response, token["user"]["id"])
    return token


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Выход",
    response_class=Response,
)
async def logout() -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_refresh_cookie(response)
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
