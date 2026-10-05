"""Текущий пользователь и проверка роли.

До волны 2 (настоящая авторизация на JWT) пользователь определяется заголовками-заглушками:
- `X-Demo-Role: candidate | recruiter | admin` — роль;
- `X-Demo-User-Id: <id>` — необязательно, id пользователя из `data/seed/users.json`
  (по умолчанию — демо-аккаунт этой роли из `demo_accounts.json`).
"""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Header
from pydantic import BaseModel

from app.common import fixtures
from app.common.enums import Role
from app.core.config import get_settings
from app.core.errors import AppError


class CurrentUser(BaseModel):
    user_id: int
    role: Role
    email: str
    full_name: str
    candidate_id: int | None = None
    recruiter_id: int | None = None
    company_id: int | None = None


def _default_user_id(role: Role) -> int | None:
    for account in fixtures.load("demo_accounts"):
        if account.get("role") == role and account.get("is_default"):
            return int(account["user_id"])
    return None


def resolve_user(user_id: int) -> CurrentUser | None:
    user = fixtures.by_id("users", user_id)
    if user is None:
        return None
    role = Role(user["role"])
    candidate = next(iter(fixtures.where("candidates", user_id=user_id)), None)
    recruiter = next(iter(fixtures.where("recruiters", user_id=user_id)), None)
    return CurrentUser(
        user_id=user_id,
        role=role,
        email=user["email"],
        full_name=user["full_name"],
        candidate_id=candidate["id"] if candidate else None,
        recruiter_id=recruiter["id"] if recruiter else None,
        company_id=recruiter["company_id"] if recruiter else None,
    )


async def get_optional_user(
    x_demo_role: Annotated[
        Role | None,
        Header(description="Заглушка авторизации до волны 2: роль текущего пользователя"),
    ] = None,
    x_demo_user_id: Annotated[
        int | None,
        Header(description="Заглушка авторизации: id пользователя (по умолчанию — демо-аккаунт)"),
    ] = None,
) -> CurrentUser | None:
    if x_demo_role is None or not get_settings().demo_auth_enabled:
        return None
    user_id = x_demo_user_id if x_demo_user_id is not None else _default_user_id(x_demo_role)
    if user_id is None:
        return None
    user = resolve_user(user_id)
    if user is None or user.role != x_demo_role:
        raise AppError(
            401,
            "unauthorized",
            "Пользователь не найден или роль не совпадает",
            {"user_id": user_id, "role": x_demo_role},
        )
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
