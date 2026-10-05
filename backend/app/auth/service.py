"""Авторизация — заглушки до волны 2 (argon2, JWT, письма, Keycloak).

Вход проверяет пару почта/пароль по `demo_accounts.json` и выдаёт токен вида
`demo.<role>.<user_id>`. Пока настоящего JWT нет, API принимает роль из `X-Demo-Role`.
"""

import secrets
from typing import Any
from urllib.parse import urlencode

from app.auth.repository import AuthRepository
from app.common.enums import Role
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import CurrentUser, resolve_user

ACCESS_TTL_SEC = 15 * 60


class AuthService:
    def __init__(self, repo: AuthRepository | None = None) -> None:
        self.repo = repo or AuthRepository()

    def me(self, user: CurrentUser) -> dict[str, Any]:
        record = self.repo.user(user.user_id) or {}
        fsp_id = None
        if user.candidate_id is not None:
            cand = self.repo.candidate(user.candidate_id) or {}
            fsp_id = cand.get("fsp_id")
        return {
            "id": user.user_id,
            "email": user.email,
            "role": user.role,
            "full_name": user.full_name,
            "email_verified": record.get("email_verified", True),
            "fsp_id": fsp_id,
            "candidate_id": user.candidate_id,
            "recruiter_id": user.recruiter_id,
            "company_id": user.company_id,
        }

    def register(self, email: str) -> dict[str, Any]:
        if self.repo.user_by_email(email):
            raise AppError(409, "email_taken", "Пользователь с такой почтой уже есть")
        return {
            "user_id": self.repo.next_user_id(),
            "email": email,
            "status": "pending_verification",
            "message": "Письмо со ссылкой отправлено. Ссылка действует 24 часа.",
        }

    def verify_email(self, token: str) -> dict[str, Any]:
        if token.startswith("expired"):
            raise AppError(410, "token_expired", "Срок действия ссылки истёк, запросите новую")
        if token.startswith("invalid"):
            raise AppError(400, "token_invalid", "Ссылка недействительна")
        return {"ok": True, "message": "Почта подтверждена, можно войти"}

    def login(self, email: str, password: str) -> dict[str, Any]:
        account = self.repo.demo_account(email)
        if account is None or account["password"] != password:
            raise AppError(401, "invalid_credentials", "Неверная почта или пароль")
        user = resolve_user(int(account["user_id"]))
        if user is None:
            raise AppError(401, "invalid_credentials", "Неверная почта или пароль")
        record = self.repo.user(user.user_id) or {}
        if not record.get("email_verified", True):
            raise AppError(403, "email_not_verified", "Подтвердите почту по ссылке из письма")
        if record.get("blocked"):
            raise AppError(403, "user_blocked", "Учётная запись заблокирована")
        return self.token_for(user)

    def token_for(self, user: CurrentUser) -> dict[str, Any]:
        return {
            "access_token": f"demo.{user.role}.{user.user_id}",
            "token_type": "bearer",
            "expires_in": ACCESS_TTL_SEC,
            "user": self.me(user),
        }

    def refresh(self, refresh_token: str | None) -> dict[str, Any]:
        if not refresh_token or not refresh_token.startswith("demo-refresh."):
            raise AppError(401, "invalid_refresh_token", "Сессия истекла, войдите снова")
        try:
            user_id = int(refresh_token.rsplit(".", 1)[1])
        except ValueError as exc:
            raise AppError(401, "invalid_refresh_token", "Сессия истекла, войдите снова") from exc
        user = resolve_user(user_id)
        if user is None:
            raise AppError(401, "invalid_refresh_token", "Сессия истекла, войдите снова")
        return self.token_for(user)

    def fsp_authorize_url(self, purpose: str, redirect_uri: str) -> dict[str, Any]:
        settings = get_settings()
        state = secrets.token_urlsafe(8)
        query = urlencode(
            {
                "client_id": settings.keycloak_client_id,
                "response_type": "code",
                "scope": "openid profile email",
                "redirect_uri": redirect_uri,
                "state": state,
                "code_challenge_method": "S256",
                "code_challenge": "<из PKCE на клиенте>",
            }
        )
        base = f"{settings.keycloak_public_url}/realms/{settings.keycloak_realm}"
        return {
            "authorize_url": f"{base}/protocol/openid-connect/auth?{query}",
            "state": state,
            "purpose": purpose,
        }

    def fsp_login(self) -> dict[str, Any]:
        """Заглушка: вход через ФСП ID = демо-соискатель."""
        account = next(a for a in self.repo.demo_accounts() if a["role"] == Role.candidate)
        user = resolve_user(int(account["user_id"]))
        assert user is not None
        return self.token_for(user)
