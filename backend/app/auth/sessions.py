"""Выдача сессии пользователю — единая точка для всех способов входа.

Вход по паролю (модуль auth) и вход через ФСП ID (модуль fsp) вызывают только эти функции.
Трек 2a меняет их реализацию (JWT access + refresh в httpOnly cookie), сигнатуры сохраняет.
"""

from typing import Any

from fastapi import Response

from app.auth.service import AuthService
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import resolve_user

REFRESH_COOKIE = "refresh_token"


def set_refresh_cookie(response: Response, user_id: int) -> None:
    """Положить refresh-токен пользователя в httpOnly cookie."""
    response.set_cookie(
        REFRESH_COOKIE,
        f"demo-refresh.{user_id}",
        httponly=True,
        samesite="lax",
        secure=get_settings().app_env != "dev",
        max_age=get_settings().refresh_token_ttl_days * 86400,
        path="/api/auth",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth")


def issue_session(response: Response, user_id: int) -> dict[str, Any]:
    """Создать сессию: тело ответа в формате TokenResponse + refresh-cookie."""
    user = resolve_user(user_id)
    if user is None:
        raise AppError(401, "invalid_credentials", "Пользователь не найден")
    token = AuthService().token_for(user)
    set_refresh_cookie(response, user_id)
    return token
