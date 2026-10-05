"""Выдача сессии пользователю — единая точка для всех способов входа.

Сессия = JWT access (HS256, `ACCESS_TOKEN_TTL_MIN`) в теле ответа + refresh-токен в httpOnly
cookie `refresh_token` (path `/api/auth`, SameSite=Lax, Secure вне dev). В БД хранится только
sha256 refresh-токена (`refresh_sessions`); при refresh токен ротируется, при выходе отзывается.

Для входа через ФСП ID (модуль fsp):
- предпочтительно `await issue_session_async(response, user_id, session)` — в той же сессии БД;
- `issue_session(response, user_id)` — синхронная обёртка с прежней сигнатурой для
  совместимости: выполняет то же самое в отдельном потоке со своим подключением к БД.
"""

import asyncio
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth.service import AuthService
from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import AppError
from app.core.security import resolve_user

REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/api/auth"


def _run_with_own_session[T](work: Callable[[AsyncSession], Awaitable[T]]) -> T:
    """Выполнить async-работу с БД из синхронного кода (в т.ч. внутри работающего event loop).

    Отдельный поток со своим event loop и своим движком без пула: соединения основного
    движка привязаны к основному loop и в другом потоке не годятся.
    """

    async def runner() -> T:
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                return await work(session)
        finally:
            await engine.dispose()

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, runner()).result()


async def _new_session_for(
    session: AsyncSession, user_id: int, user_agent: str | None = None, ip: str | None = None
) -> tuple[dict[str, Any], str]:
    user = await resolve_user(session, user_id)
    if user is None:
        raise AppError(401, "invalid_credentials", "Пользователь не найден")
    if user.blocked:
        raise AppError(403, "user_blocked", "Учётная запись заблокирована")
    return await AuthService(session).start_session(user, user_agent, ip)


def set_refresh_cookie(response: Response, user_id: int, token: str | None = None) -> None:
    """Положить refresh-токен в httpOnly cookie.

    `token` — уже выданный refresh-токен. Без него (старый способ вызова) для `user_id`
    создаётся новая refresh-сессия.
    """
    if token is None:
        token = _run_with_own_session(lambda s: _new_session_for(s, user_id))[1]
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.refresh_token_ttl_days * 86400,
        path=REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )


async def issue_session_async(
    response: Response,
    user_id: int,
    session: AsyncSession | None = None,
    user_agent: str | None = None,
    ip: str | None = None,
) -> dict[str, Any]:
    """Создать сессию: тело в формате TokenResponse + refresh-cookie в `response`."""
    if session is None:
        async for own in get_session():
            return await issue_session_async(response, user_id, own, user_agent, ip)
        raise AssertionError("get_session не выдал сессию")  # pragma: no cover
    body, token = await _new_session_for(session, user_id, user_agent, ip)
    set_refresh_cookie(response, user_id, token)
    return body


def issue_session(response: Response, user_id: int) -> dict[str, Any]:
    """Синхронный вариант `issue_session_async` (прежняя сигнатура, для совместимости)."""
    body, token = _run_with_own_session(lambda s: _new_session_for(s, user_id))
    set_refresh_cookie(response, user_id, token)
    return body
