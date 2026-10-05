"""Регистрация, вход, подтверждение почты, токены, ФСП ID (OIDC)."""

from typing import Literal, Self

from pydantic import ConfigDict, EmailStr, Field, model_validator

from app.common.enums import Role
from app.common.schemas import ApiModel, OutModel
from app.users.schemas import ME_EXAMPLE, Me


class CompanyRegistration(ApiModel):
    """Рекрутер при регистрации создаёт компанию или вступает в существующую по коду."""

    name: str | None = Field(default=None, min_length=2, max_length=200)
    inn: str | None = Field(default=None, pattern=r"^\d{10}(\d{2})?$")
    invite_code: str | None = Field(default=None, description="Код приглашения в компанию")

    @model_validator(mode="after")
    def _name_or_code(self) -> Self:
        if not self.name and not self.invite_code:
            raise ValueError("Укажите название новой компании или код приглашения")
        return self


class RegisterRequest(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email": "new.candidate@example.com",
                    "password": "S3cure-pass",
                    "full_name": "Иван Петров",
                    "role": "candidate",
                    "consent_processing": True,
                    "consent_version": "2026-10-01",
                },
                {
                    "email": "new.hr@example.com",
                    "password": "S3cure-pass",
                    "full_name": "Мария Соколова",
                    "role": "recruiter",
                    "consent_processing": True,
                    "consent_version": "2026-10-01",
                    "company": {"name": "ООО «Пример»", "inn": "7701234567"},
                },
            ]
        }
    )

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=200)
    role: Literal[Role.candidate, Role.recruiter]
    consent_processing: bool = Field(description="Согласие на обработку ПДн — обязательно true")
    consent_version: str = "2026-10-01"
    company: CompanyRegistration | None = Field(
        default=None, description="Обязательно для роли recruiter"
    )

    @model_validator(mode="after")
    def _check(self) -> Self:
        if not self.consent_processing:
            raise ValueError("Без согласия на обработку персональных данных регистрация невозможна")
        if self.role == Role.recruiter and self.company is None:
            raise ValueError("Рекрутеру нужно указать компанию")
        return self


class RegisterResponse(OutModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "user_id": 101,
                    "email": "new.candidate@example.com",
                    "status": "pending_verification",
                    "message": "Письмо со ссылкой отправлено. Ссылка действует 24 часа.",
                }
            ]
        }
    )

    user_id: int
    email: str
    status: Literal["pending_verification"] = "pending_verification"
    message: str


class VerifyEmailRequest(ApiModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"token": "demo-verify-token"}]})

    token: str = Field(min_length=8)


class ResendVerificationRequest(ApiModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"email": "candidate@example.com"}]})

    email: EmailStr


class LoginRequest(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"email": "candidate@example.com", "password": "demo1234"}]}
    )

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(OutModel):
    """Access-токен в теле; refresh — в httpOnly cookie `refresh_token`."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "access_token": "demo.candidate.1",
                    "token_type": "bearer",
                    "expires_in": 900,
                    "user": ME_EXAMPLE,
                }
            ]
        }
    )

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Срок жизни access-токена, секунд")
    user: Me


class PasswordResetRequest(ApiModel):
    email: EmailStr


class PasswordResetConfirm(ApiModel):
    token: str = Field(min_length=8)
    new_password: str = Field(min_length=8, max_length=128)


class FspAuthorizeUrl(OutModel):
    """Ссылка на Keycloak (realm `fsp`) для входа или привязки через ФСП ID."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "authorize_url": "http://localhost:18180/realms/fsp/protocol/openid-connect/auth?client_id=fsp-talent&response_type=code&code_challenge_method=S256&...",
                    "state": "b1f0c2",
                    "purpose": "login",
                }
            ]
        }
    )

    authorize_url: str
    state: str
    purpose: Literal["login", "link"]


class FspCodeExchange(ApiModel):
    """Код авторизации из Keycloak (OIDC Authorization Code + PKCE)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "code": "kc-auth-code",
                    "state": "b1f0c2",
                    "code_verifier": "pkce-verifier-43-128-chars-xxxxxxxxxxxxxxxxxxxxxxx",
                    "redirect_uri": "http://localhost:15173/auth/fsp-callback",
                }
            ]
        }
    )

    code: str
    state: str
    code_verifier: str = Field(min_length=43, max_length=128)
    redirect_uri: str
