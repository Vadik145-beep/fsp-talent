"""Авторизация: регистрация с подтверждением почты, вход, refresh с ротацией, сброс пароля.

Правила безопасности:
- пароли — `hash_password` / `verify_password` (scrypt);
- токены почты и refresh — в БД только sha256;
- ответы на повторную отправку письма и сброс пароля не зависят от того, есть ли такая почта;
- неудачные входы считаются на пару почта+IP (в т.ч. для несуществующих почт), после
  `LOGIN_MAX_ATTEMPTS` за `LOGIN_WINDOW_MIN` минут — 429 даже с верным паролем.

Демо-режим (`DEMO_AUTH_ENABLED=true`): если почты нет в БД, вход проверяется по
`demo_accounts.json`, а пользователь берётся из фикстур (до загрузчика демо-данных 2b).
"""

import hmac
import secrets
from datetime import timedelta
from typing import Any
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.emails import send_password_reset_email, send_verification_email
from app.auth.passwords import hash_password, verify_password
from app.auth.repository import AuthRepository, utcnow
from app.auth.schemas import RegisterRequest
from app.candidates.schemas import PRIVACY_DEFAULTS
from app.common import fixtures
from app.common.enums import ConsentType, Role
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import CurrentUser, create_access_token, db_user, fixture_user

VERIFY_EMAIL = "verify_email"
RESET_PASSWORD = "reset_password"
LOGIN_FAILED = "login_failed"
RESEND_VERIFICATION = "resend_verification"
PASSWORD_RESET = "password_reset"

# хеш для выравнивания времени ответа, когда почты нет: verify_password отработает так же долго
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))

MSG_SENT = "Письмо со ссылкой отправлено. Ссылка действует 24 часа."
MSG_RESEND = "Если почта зарегистрирована и не подтверждена, письмо отправлено повторно"
MSG_RESET = "Если почта зарегистрирована, мы отправили ссылку для сброса"


def _invalid_credentials() -> AppError:
    return AppError(401, "invalid_credentials", "Неверная почта или пароль")


def _invalid_refresh() -> AppError:
    return AppError(401, "invalid_refresh_token", "Сессия истекла, войдите снова")


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AuthRepository(session)
        self.settings = get_settings()

    # --- текущий пользователь ---

    async def me(self, user: CurrentUser) -> dict[str, Any]:
        return {
            "id": user.user_id,
            "email": user.email,
            "role": user.role,
            "full_name": user.full_name,
            "email_verified": user.email_verified,
            "fsp_id": await self._fsp_id(user),
            "candidate_id": user.candidate_id,
            "recruiter_id": user.recruiter_id,
            "company_id": user.company_id,
        }

    async def _fsp_id(self, user: CurrentUser) -> str | None:
        if user.candidate_id is None:
            return None
        if user.source == "fixture":
            cand = fixtures.by_id("candidates", user.candidate_id) or {}
            return cand.get("fsp_id")
        from app.fsp.models import FspLink

        return (
            await self.session.execute(
                select(FspLink.fsp_id).where(FspLink.candidate_id == user.candidate_id)
            )
        ).scalar_one_or_none()

    async def token_body(self, user: CurrentUser) -> dict[str, Any]:
        """Тело TokenResponse: access-токен и профиль."""
        return {
            "access_token": create_access_token(user),
            "token_type": "bearer",
            "expires_in": self.settings.access_token_ttl_min * 60,
            "user": await self.me(user),
        }

    # --- регистрация и подтверждение почты ---

    async def register(self, body: RegisterRequest) -> dict[str, Any]:
        email = str(body.email).lower()
        existing = await self.repo.user_by_email(email)
        if existing is not None:
            if existing.email_verified:
                raise AppError(409, "email_taken", "Пользователь с такой почтой уже есть")
            # Повторная регистрация неподтверждённой почты: данные первой регистрации не меняем
            # (иначе чужой человек мог бы подменить пароль), только отправляем письмо заново.
            await self._send_verification(existing.id, existing.email, existing.full_name)
            return {"user_id": existing.id, "email": existing.email, "message": MSG_SENT}
        if self.settings.demo_auth_enabled and self.repo.fixture_user_by_email(email):
            raise AppError(409, "email_taken", "Пользователь с такой почтой уже есть")

        from app.companies.models import Company, Recruiter
        from app.users.models import Consent, User

        company: Company | None = None
        if body.role == Role.recruiter and body.company and body.company.invite_code:
            company = (
                await self.session.execute(
                    select(Company).where(Company.invite_code == body.company.invite_code.strip())
                )
            ).scalar_one_or_none()
            if company is None:
                raise AppError(
                    404, "company_invite_not_found", "Код приглашения в компанию не найден"
                )

        user = User(
            email=email,
            password_hash=hash_password(body.password),
            role=str(body.role),
            full_name=body.full_name.strip(),
            email_verified=False,
        )
        self.session.add(user)
        await self.session.flush()
        self.session.add(
            Consent(
                user_id=user.id,
                type=str(ConsentType.processing),
                version=body.consent_version,
                granted=True,
                granted_at=utcnow(),
            )
        )
        if body.role == Role.candidate:
            await self._create_candidate_profile(user.id)
        else:
            is_admin = company is None
            if company is None:
                assert body.company is not None and body.company.name
                company = Company(
                    name=body.company.name.strip(),
                    description="",
                    industry="",
                    contact_email=email,
                    inn=body.company.inn,
                    trust_score=50,
                    invite_code=await self._new_invite_code(),
                )
                self.session.add(company)
                await self.session.flush()
            self.session.add(
                Recruiter(user_id=user.id, company_id=company.id, is_company_admin=is_admin)
            )
        await self.session.flush()
        await self._send_verification(user.id, user.email, user.full_name, force=True)
        return {"user_id": user.id, "email": user.email, "message": MSG_SENT}

    async def _create_candidate_profile(self, user_id: int) -> None:
        """Минимальный профиль кандидата: псевдоним для обезличенной выдачи, остальное — позже."""
        from app.candidates.models import CandidateProfile

        taken = {c["pseudonym"] for c in fixtures.load("candidates")}
        for _ in range(20):
            pseudonym = f"Кандидат #{secrets.token_hex(2).upper()}"
            exists = (
                await self.session.execute(
                    select(CandidateProfile.id).where(CandidateProfile.pseudonym == pseudonym)
                )
            ).first()
            if pseudonym not in taken and exists is None:
                break
        else:
            pseudonym = f"Кандидат #{secrets.token_hex(4).upper()}"
        self.session.add(
            CandidateProfile(
                user_id=user_id,
                pseudonym=pseudonym,
                work_formats=[],
                topic_scores=[],
                roles_in_team=[],
                experience_years=0,
                soft_skills=[],
                about="",
                links=[],
                privacy=dict(PRIVACY_DEFAULTS),
                freshness=0,
            )
        )

    async def _new_invite_code(self) -> str:
        from app.companies.models import Company

        while True:
            code = secrets.token_hex(4).upper()
            found = (
                await self.session.execute(select(Company.id).where(Company.invite_code == code))
            ).first()
            if found is None:
                return code

    async def _send_verification(
        self, user_id: int, email: str, full_name: str, *, force: bool = False
    ) -> bool:
        """Новый токен подтверждения + письмо.

        Без `force` — не чаще раза в интервал (иначе молча пропуск); с `force` лимит уже
        проверил вызывающий.
        """
        interval = timedelta(seconds=self.settings.email_resend_interval_sec)
        if not force and await self.repo.throttle_count(RESEND_VERIFICATION, email, interval):
            return False
        await self.repo.throttle_add(RESEND_VERIFICATION, email, keep=interval)
        raw = await self.repo.create_email_token(
            user_id, VERIFY_EMAIL, timedelta(hours=self.settings.email_verify_ttl_hours)
        )
        await self.session.commit()
        return await send_verification_email(email, full_name, raw)

    async def resend_verification(self, email: str) -> dict[str, Any]:
        email = email.lower()
        interval = timedelta(seconds=self.settings.email_resend_interval_sec)
        # лимит считается по почте независимо от того, есть ли она в БД, — ответ не выдаёт её
        if await self.repo.throttle_count(RESEND_VERIFICATION, email, interval):
            raise AppError(429, "too_many_requests", "Повторить можно через минуту")
        user = await self.repo.user_by_email(email)
        if user is not None and not user.email_verified and not user.blocked:
            await self._send_verification(user.id, user.email, user.full_name, force=True)
        else:
            await self.repo.throttle_add(RESEND_VERIFICATION, email, keep=interval)
            await self.session.commit()
        return {"ok": True, "message": MSG_RESEND}

    async def verify_email(self, raw: str) -> dict[str, Any]:
        token = await self.repo.find_email_token(VERIFY_EMAIL, raw)
        if token is None:
            # совместимость с прототипом: «expired-…» показывает экран просроченной ссылки
            if self.settings.demo_auth_enabled and raw.startswith("expired"):
                raise AppError(410, "token_expired", "Срок действия ссылки истёк, запросите новую")
            raise AppError(400, "token_invalid", "Ссылка недействительна")
        user = await self.repo.user(token.user_id)
        if user is None:
            raise AppError(400, "token_invalid", "Ссылка недействительна")
        if token.used_at is not None:
            if user.email_verified:
                return {"ok": True, "message": "Почта уже подтверждена, можно войти"}
            raise AppError(400, "token_invalid", "Ссылка недействительна")
        if token.expires_at <= utcnow():
            raise AppError(410, "token_expired", "Срок действия ссылки истёк, запросите новую")
        token.used_at = utcnow()
        user.email_verified = True
        await self.session.commit()
        return {"ok": True, "message": "Почта подтверждена, можно войти"}

    # --- вход, refresh, выход ---

    async def authenticate(self, email: str, password: str, ip: str | None) -> CurrentUser:
        """Проверить пару почта/пароль с учётом лимита попыток; вернуть пользователя."""
        email = email.lower()
        key = f"{email}|{ip or '-'}"
        window = timedelta(minutes=self.settings.login_window_min)
        if await self.repo.throttle_count(LOGIN_FAILED, key, window) >= (
            self.settings.login_max_attempts
        ):
            raise AppError(
                429,
                "too_many_attempts",
                f"Слишком много попыток, попробуйте через {self.settings.login_window_min} минут",
            )

        user: CurrentUser | None = None
        record = await self.repo.user_by_email(email)
        if record is not None:
            if record.password_hash and verify_password(password, record.password_hash):
                user = await db_user(self.session, record.id)
        elif self.settings.demo_auth_enabled and (account := self.repo.demo_account(email)):
            verify_password(password, _DUMMY_HASH)
            if hmac.compare_digest(str(account["password"]).encode(), password.encode()):
                user = fixture_user(int(account["user_id"]))
        else:
            verify_password(password, _DUMMY_HASH)

        if user is None:
            await self.repo.throttle_add(LOGIN_FAILED, key, keep=window)
            await self.session.commit()
            raise _invalid_credentials()
        await self.repo.throttle_clear(LOGIN_FAILED, key)
        await self.session.commit()
        if user.blocked:
            raise AppError(403, "user_blocked", "Учётная запись заблокирована")
        if not user.email_verified:
            raise AppError(403, "email_not_verified", "Подтвердите почту по ссылке из письма")
        return user

    async def start_session(
        self, user: CurrentUser, user_agent: str | None = None, ip: str | None = None
    ) -> tuple[dict[str, Any], str]:
        """Новая refresh-сессия: (тело TokenResponse, refresh-токен для cookie)."""
        raw = await self.repo.create_refresh(
            user.user_id, timedelta(days=self.settings.refresh_token_ttl_days), user_agent, ip
        )
        if user.source == "db":
            record = await self.repo.user(user.user_id)
            if record is not None:
                record.last_login_at = utcnow()
        body = await self.token_body(user)
        await self.session.commit()
        return body, raw

    async def refresh(
        self, raw: str | None, user_agent: str | None, ip: str | None
    ) -> tuple[dict[str, Any], str]:
        """Ротация: старый refresh отзывается, выдаётся новый. Повтор старого — 401."""
        if not raw:
            raise _invalid_refresh()
        old = await self.repo.claim_refresh(raw)
        if old is None:
            await self.session.rollback()
            raise _invalid_refresh()
        from app.core.security import resolve_user

        user = await resolve_user(self.session, old.user_id)
        if user is None:
            await self.session.commit()
            raise _invalid_refresh()
        if user.blocked:
            await self.repo.revoke_all_refresh(user.user_id)
            await self.session.commit()
            raise AppError(403, "user_blocked", "Учётная запись заблокирована")
        return await self.start_session(user, user_agent, ip)

    async def logout(self, raw: str | None) -> None:
        if raw:
            await self.repo.claim_refresh(raw)
            await self.session.commit()

    # --- сброс пароля ---

    async def request_password_reset(self, email: str) -> dict[str, Any]:
        email = email.lower()
        interval = timedelta(seconds=self.settings.email_resend_interval_sec)
        if await self.repo.throttle_count(PASSWORD_RESET, email, interval):
            raise AppError(429, "too_many_requests", "Повторить можно через минуту")
        await self.repo.throttle_add(PASSWORD_RESET, email, keep=interval)
        user = await self.repo.user_by_email(email)
        raw: str | None = None
        if user is not None and not user.blocked:
            raw = await self.repo.create_email_token(
                user.id, RESET_PASSWORD, timedelta(minutes=self.settings.password_reset_ttl_min)
            )
        await self.session.commit()
        if user is not None and raw is not None:
            await send_password_reset_email(user.email, user.full_name, raw)
        return {"ok": True, "message": MSG_RESET}

    async def confirm_password_reset(self, raw: str, new_password: str) -> dict[str, Any]:
        token = await self.repo.find_email_token(RESET_PASSWORD, raw)
        if token is None or token.used_at is not None:
            raise AppError(400, "token_invalid", "Ссылка недействительна")
        if token.expires_at <= utcnow():
            raise AppError(410, "token_expired", "Срок действия ссылки истёк")
        user = await self.repo.user(token.user_id)
        if user is None:
            raise AppError(400, "token_invalid", "Ссылка недействительна")
        token.used_at = utcnow()
        user.password_hash = hash_password(new_password)
        user.email_verified = True  # ссылка из письма подтверждает владение почтой
        await self.repo.revoke_all_refresh(user.id)
        await self.repo.throttle_clear(LOGIN_FAILED, f"{user.email}|")
        await self.session.commit()
        return {"ok": True, "message": "Пароль изменён, войдите с новым паролем"}


class AuthLinks:
    """Ссылка на Keycloak и заглушка входа через ФСП ID — без БД.

    Модуль fsp (трек 2c) импортирует экземпляр как `app.auth.router.service`.
    """

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
        """Заглушка до трека 2c: вход через ФСП ID = демо-соискатель (только `user.id`)."""
        account = next(a for a in AuthRepository.demo_accounts() if a["role"] == Role.candidate)
        return {"user": {"id": int(account["user_id"])}}
