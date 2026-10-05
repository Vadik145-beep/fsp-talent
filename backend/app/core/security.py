"""Текущий пользователь, JWT access-токены и проверка роли (RBAC).

Как определяется пользователь:
1. `Authorization: Bearer <jwt>` — основной способ. Токен подписан HS256 (`JWT_SECRET`),
   живёт `ACCESS_TOKEN_TTL_MIN` минут; роль и связи (кандидат/рекрутер/компания) берутся из БД
   на каждый запрос, поэтому блокировка и смена роли действуют сразу.
2. Если Bearer нет и `DEMO_AUTH_ENABLED=true` — запасной режим для прототипа и заглушек:
   `X-Demo-Role: candidate | recruiter | admin` и необязательный `X-Demo-User-Id: <id>`
   (по умолчанию — демо-аккаунт роли из `demo_accounts.json`).

Пока загрузчик демо-данных (трек 2b) не слит, в БД нет пользователей из фикстур. Поэтому в
демо-режиме пользователь, которого нет в БД, берётся из `data/seed/users.json` (и его
кандидат/рекрутер — из фикстур). id созданных через API пользователей не пересекаются с id
фикстур: при старте последовательности сдвигаются за максимальный id фикстур
(см. `app/auth/bootstrap.py`). Неверный или просроченный Bearer — всегда 401, на демо-заголовки
не откатываемся.
"""

import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

import jwt
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common import fixtures
from app.common.enums import Role
from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import AppError

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "fsp-talent"


class CurrentUser(BaseModel):
    user_id: int
    role: Role
    email: str
    full_name: str
    candidate_id: int | None = None
    recruiter_id: int | None = None
    company_id: int | None = None
    email_verified: bool = True
    blocked: bool = False
    # откуда взят пользователь: БД или фикстуры (только демо-режим, до загрузчика 2b)
    source: Literal["db", "fixture"] = "db"


# --- JWT ---------------------------------------------------------------------------------


def create_access_token(user: CurrentUser) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.user_id),
        "role": str(user.role),
        "typ": "access",
        "iss": JWT_ISSUER,
        "jti": secrets.token_hex(8),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_min),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int:
    """id пользователя из access-токена; 401 `token_expired` / `token_invalid`."""
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            options={"require": ["exp", "sub", "iat"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AppError(401, "token_expired", "Сессия истекла, обновите токен") from exc
    except jwt.InvalidTokenError as exc:
        raise AppError(401, "token_invalid", "Недействительный токен") from exc
    if payload.get("typ") != "access":
        raise AppError(401, "token_invalid", "Недействительный токен")
    try:
        return int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise AppError(401, "token_invalid", "Недействительный токен") from exc


# --- Пользователь из БД или фикстур -----------------------------------------------------


async def db_user(session: AsyncSession, user_id: int) -> CurrentUser | None:
    # импорт внутри: модели модулей импортируют app.core.*, а не наоборот
    from app.candidates.models import CandidateProfile
    from app.companies.models import Recruiter
    from app.users.models import User

    row = (
        await session.execute(
            select(User, CandidateProfile.id, Recruiter.id, Recruiter.company_id)
            .outerjoin(CandidateProfile, CandidateProfile.user_id == User.id)
            .outerjoin(Recruiter, Recruiter.user_id == User.id)
            .where(User.id == user_id)
        )
    ).first()
    if row is None:
        return None
    user, candidate_id, recruiter_id, company_id = row
    return CurrentUser(
        user_id=user.id,
        role=Role(user.role),
        email=user.email,
        full_name=user.full_name,
        candidate_id=candidate_id,
        recruiter_id=recruiter_id,
        company_id=company_id,
        email_verified=user.email_verified,
        blocked=user.blocked,
        source="db",
    )


def fixture_user(user_id: int) -> CurrentUser | None:
    """Пользователь из `data/seed` (демо-режим, пока его нет в БД)."""
    user = fixtures.by_id("users", user_id)
    if user is None:
        return None
    candidate = next(iter(fixtures.where("candidates", user_id=user_id)), None)
    recruiter = next(iter(fixtures.where("recruiters", user_id=user_id)), None)
    return CurrentUser(
        user_id=user_id,
        role=Role(user["role"]),
        email=user["email"],
        full_name=user["full_name"],
        candidate_id=candidate["id"] if candidate else None,
        recruiter_id=recruiter["id"] if recruiter else None,
        company_id=recruiter["company_id"] if recruiter else None,
        email_verified=bool(user.get("email_verified", True)),
        blocked=bool(user.get("blocked", False)),
        source="fixture",
    )


async def resolve_user(session: AsyncSession, user_id: int) -> CurrentUser | None:
    """Пользователь по id: БД, а в демо-режиме — запасной вариант из фикстур."""
    user = await db_user(session, user_id)
    if user is None and get_settings().demo_auth_enabled:
        user = fixture_user(user_id)
    return user


def _default_user_id(role: Role) -> int | None:
    for account in fixtures.load("demo_accounts"):
        if account.get("role") == role and account.get("is_default"):
            return int(account["user_id"])
    return None


# --- Зависимости FastAPI ----------------------------------------------------------------

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="JWT access-токен из `POST /api/auth/login` (живёт 15 минут)",
)


async def get_optional_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
    x_demo_role: Annotated[
        Role | None,
        Header(
            description=(
                "Демо-режим (DEMO_AUTH_ENABLED=true), если нет Bearer: роль текущего пользователя"
            )
        ),
    ] = None,
    x_demo_user_id: Annotated[
        int | None,
        Header(description="Демо-режим: id пользователя (по умолчанию — демо-аккаунт роли)"),
    ] = None,
) -> CurrentUser | None:
    user: CurrentUser | None
    if credentials is not None:
        user_id = decode_access_token(credentials.credentials)
        user = await resolve_user(session, user_id)
        if user is None:
            raise AppError(401, "token_invalid", "Пользователь не найден")
    elif x_demo_role is not None and get_settings().demo_auth_enabled:
        user_id_or_none = (
            x_demo_user_id if x_demo_user_id is not None else _default_user_id(x_demo_role)
        )
        if user_id_or_none is None:
            return None
        user = await resolve_user(session, user_id_or_none)
        if user is None or user.role != x_demo_role:
            raise AppError(
                401,
                "unauthorized",
                "Пользователь не найден или роль не совпадает",
                {"user_id": user_id_or_none, "role": x_demo_role},
            )
    else:
        return None
    if user.blocked:
        raise AppError(403, "user_blocked", "Учётная запись заблокирована")
    return user


async def get_current_user(
    user: Annotated[CurrentUser | None, Depends(get_optional_user)],
) -> CurrentUser:
    if user is None:
        raise AppError(401, "unauthorized", "Требуется вход")
    return user


def require_role(*roles: Role) -> Callable[..., Awaitable[CurrentUser]]:
    async def dependency(
        user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if user.role not in roles:
            raise AppError(
                403,
                "forbidden",
                "Недостаточно прав",
                {"required_roles": list(roles), "role": user.role},
            )
        return user

    return dependency


AnyUser = Annotated[CurrentUser, Depends(get_current_user)]
CandidateUser = Annotated[CurrentUser, Depends(require_role(Role.candidate))]
RecruiterUser = Annotated[CurrentUser, Depends(require_role(Role.recruiter))]
AdminUser = Annotated[CurrentUser, Depends(require_role(Role.admin))]
CandidateOrRecruiter = Annotated[CurrentUser, Depends(require_role(Role.candidate, Role.recruiter))]
