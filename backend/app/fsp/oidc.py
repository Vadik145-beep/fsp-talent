"""ФСП ID (Keycloak): OIDC Authorization Code + PKCE (S256).

Как устроено:
1. `GET /api/auth/fsp/authorize-url` — сервер генерирует `state`, `nonce` и `code_verifier`,
   кладёт их в подписанную httpOnly cookie на 10 минут (`fsp_oidc_state`, путь /api/auth)
   и отдаёт адрес входа Keycloak (публичный адрес — его открывает браузер) с `code_challenge`.
   code_verifier до браузера не доходит: JS его не видит, без cookie код бесполезен.
2. Keycloak возвращает браузер на `redirect_uri?code=…&state=…`, фронт отправляет code и state
   на `POST /api/auth/fsp/login` или `POST /api/auth/fsp-link`.
3. Сервер сверяет state с cookie, меняет code на токены по внутреннему адресу Keycloak
   (`code_verifier` из cookie) и проверяет ID-токен по JWKS: подпись RS256, `iss` (публичный
   адрес realm), `aud`/`azp` = клиент, срок, `nonce`; берёт claim `fsp_id`.

Ошибки: Keycloak недоступен → `KeycloakUnavailableError` (503 keycloak_unavailable), всё остальное →
`OidcError` с причиной (400 oidc_error, details.reason).
"""

import asyncio
import base64
import hashlib
import hmac
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlencode

import httpx
import jwt

from app.core.config import get_settings
from app.fsp.registry import FSP_ID_RE
from app.fsp.settings import get_fsp_settings

STATE_COOKIE = "fsp_oidc_state"
STATE_COOKIE_PATH = "/api/auth"
STATE_ALG = "HS256"
ID_TOKEN_ALGS = ["RS256"]
CLOCK_LEEWAY_SEC = 30

Purpose = Literal["login", "link"]


class KeycloakUnavailableError(Exception):
    """Keycloak не отвечает (сеть, таймаут, 5xx, нет JWKS)."""


class OidcError(Exception):
    """Ошибка протокола: state, обмен кода, ID-токен. reason — машинная причина."""

    def __init__(self, reason: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.details = details or {}


# ---------------------------------------------------------------- PKCE


def make_code_verifier() -> str:
    """Случайный code_verifier: 86 символов base64url (RFC 7636: 43–128)."""
    return secrets.token_urlsafe(64)


def code_challenge_s256(verifier: str) -> str:
    """BASE64URL(SHA256(verifier)) без '=' (RFC 7636, метод S256)."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


# ---------------------------------------------------------------- state в cookie


@dataclass(frozen=True)
class OidcState:
    state: str
    code_verifier: str
    nonce: str
    purpose: Purpose
    redirect_uri: str

    @classmethod
    def new(cls, purpose: Purpose, redirect_uri: str) -> "OidcState":
        return cls(
            state=secrets.token_urlsafe(32),
            code_verifier=make_code_verifier(),
            nonce=secrets.token_urlsafe(16),
            purpose=purpose,
            redirect_uri=redirect_uri,
        )


def _state_key() -> str:
    secret = get_fsp_settings().oidc_state_secret or get_settings().jwt_secret
    # отдельный ключ, чтобы cookie state нельзя было выдать за JWT сессии и наоборот
    return hmac.new(secret.encode(), b"fsp-oidc-state", hashlib.sha256).hexdigest()


def encode_state(st: OidcState, *, ttl_sec: int | None = None, now: float | None = None) -> str:
    issued = int(now if now is not None else time.time())
    ttl = ttl_sec if ttl_sec is not None else get_fsp_settings().oidc_state_ttl_sec
    payload = {
        "st": st.state,
        "cv": st.code_verifier,
        "nonce": st.nonce,
        "purpose": st.purpose,
        "ru": st.redirect_uri,
        "iat": issued,
        "exp": issued + ttl,
    }
    return jwt.encode(payload, _state_key(), algorithm=STATE_ALG)


def decode_state(
    cookie: str | None, state: str, purpose: Purpose, *, now: float | None = None
) -> OidcState:
    """Проверить cookie и state из запроса. Любое расхождение — OidcError."""
    if not cookie:
        raise OidcError("state_missing", "Попытка входа через ФСП ID не найдена, начните заново")
    try:
        payload = jwt.decode(
            cookie,
            _state_key(),
            algorithms=[STATE_ALG],
            options={"require": ["exp", "iat"], "verify_exp": now is None},
        )
    except jwt.ExpiredSignatureError as exc:
        raise OidcError(
            "state_expired", "Время входа через ФСП ID истекло, начните заново"
        ) from exc
    except jwt.PyJWTError as exc:
        raise OidcError(
            "state_invalid", "Попытка входа через ФСП ID повреждена, начните заново"
        ) from exc
    if now is not None and now > payload["exp"]:
        raise OidcError("state_expired", "Время входа через ФСП ID истекло, начните заново")
    if not hmac.compare_digest(str(payload.get("st", "")), state):
        raise OidcError("state_mismatch", "Параметр state не совпадает, начните вход заново")
    if payload.get("purpose") != purpose:
        raise OidcError(
            "purpose_mismatch",
            "Ссылка ФСП ID выдана для другого действия, начните заново",
            {"expected": purpose, "got": payload.get("purpose")},
        )
    return OidcState(
        state=payload["st"],
        code_verifier=payload["cv"],
        nonce=payload["nonce"],
        purpose=payload["purpose"],
        redirect_uri=payload["ru"],
    )


# ---------------------------------------------------------------- проверка ID-токена

KeyResolver = Callable[[str], Any]


@dataclass(frozen=True)
class FspIdentity:
    fsp_id: str
    sub: str
    claims: dict[str, Any]


class IdTokenVerifier:
    """Проверка ID-токена Keycloak. key_resolver: токен → ключ (по умолчанию JWKS realm)."""

    def __init__(self, issuer: str, client_id: str, key_resolver: KeyResolver) -> None:
        self.issuer = issuer
        self.client_id = client_id
        self.key_resolver = key_resolver

    def verify(self, id_token: str, nonce: str | None = None) -> FspIdentity:
        try:
            key = self.key_resolver(id_token)
        except jwt.PyJWKClientConnectionError as exc:
            raise KeycloakUnavailableError(f"JWKS недоступен: {exc}") from exc
        except jwt.PyJWTError as exc:
            raise OidcError(
                "id_token_invalid", "ID-токен ФСП ID не прошёл проверку", {"error": str(exc)}
            ) from exc
        try:
            claims: dict[str, Any] = jwt.decode(
                id_token,
                key,
                algorithms=ID_TOKEN_ALGS,
                audience=self.client_id,
                issuer=self.issuer,
                leeway=CLOCK_LEEWAY_SEC,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise OidcError(
                "id_token_expired", "Срок ID-токена ФСП ID истёк, войдите заново"
            ) from exc
        except jwt.PyJWTError as exc:
            raise OidcError(
                "id_token_invalid",
                "ID-токен ФСП ID не прошёл проверку",
                {"error": f"{type(exc).__name__}: {exc}"},
            ) from exc
        azp = claims.get("azp")
        if azp is not None and azp != self.client_id:
            raise OidcError("id_token_invalid", "ID-токен выдан другому приложению", {"azp": azp})
        if nonce is not None and not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
            raise OidcError(
                "id_token_invalid", "ID-токен не относится к этой попытке входа", {"error": "nonce"}
            )
        fsp_id = claims.get("fsp_id")
        if not isinstance(fsp_id, str) or not FSP_ID_RE.match(fsp_id):
            raise OidcError(
                "fsp_id_missing", "В учётной записи ФСП ID нет номера участника", {"fsp_id": fsp_id}
            )
        return FspIdentity(fsp_id=fsp_id, sub=str(claims["sub"]), claims=claims)


_jwk_clients: dict[str, jwt.PyJWKClient] = {}


def jwks_key_resolver(jwks_url: str, timeout: float) -> KeyResolver:
    """Ключи realm по JWKS; PyJWKClient кэширует их на 5 минут и сам перечитывает по новому kid."""
    client = _jwk_clients.get(jwks_url)
    if client is None:
        client = jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=300, timeout=int(timeout) or 1)
        _jwk_clients[jwks_url] = client

    def resolve(token: str) -> Any:
        return client.get_signing_key_from_jwt(token).key

    return resolve


# ---------------------------------------------------------------- клиент Keycloak


def _realm_base(url: str, realm: str) -> str:
    """Адрес realm. Принимает и `http://host:port`, и `http://host:port/realms/<realm>`."""
    base = url.rstrip("/")
    suffix = f"/realms/{realm}"
    if base.endswith(suffix):
        base = base[: -len(suffix)]
    return f"{base}{suffix}"


class KeycloakClient:
    def __init__(
        self,
        *,
        public_url: str,
        internal_url: str,
        realm: str,
        client_id: str,
        timeout: float = 5.0,
        transport: httpx.AsyncBaseTransport | None = None,
        key_resolver: KeyResolver | None = None,
    ) -> None:
        self.public_realm = _realm_base(public_url, realm)
        self.internal_realm = _realm_base(internal_url, realm)
        self.client_id = client_id
        self.timeout = timeout
        self.transport = transport
        self.verifier = IdTokenVerifier(
            issuer=self.public_realm,
            client_id=client_id,
            key_resolver=key_resolver
            or jwks_key_resolver(f"{self.internal_realm}/protocol/openid-connect/certs", timeout),
        )

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout, connect=min(self.timeout, 3.0)),
            transport=self.transport,
        )

    def authorize_url(self, st: OidcState) -> str:
        query = urlencode(
            {
                "client_id": self.client_id,
                "response_type": "code",
                "scope": "openid",
                "redirect_uri": st.redirect_uri,
                "state": st.state,
                "nonce": st.nonce,
                "code_challenge": code_challenge_s256(st.code_verifier),
                "code_challenge_method": "S256",
            }
        )
        return f"{self.public_realm}/protocol/openid-connect/auth?{query}"

    async def check_available(self) -> None:
        """Быстрая проверка, что realm отвечает (discovery по внутреннему адресу)."""
        url = f"{self.internal_realm}/.well-known/openid-configuration"
        try:
            async with self._client() as client:
                response = await client.get(url)
        except httpx.HTTPError as exc:
            raise KeycloakUnavailableError(f"{type(exc).__name__}: {exc}") from exc
        if response.status_code != 200:
            raise KeycloakUnavailableError(f"discovery HTTP {response.status_code}")

    async def exchange_code(self, code: str, st: OidcState) -> dict[str, Any]:
        """Обмен кода на токены (внутренний адрес, PKCE code_verifier из cookie)."""
        url = f"{self.internal_realm}/protocol/openid-connect/token"
        form = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": st.redirect_uri,
            "client_id": self.client_id,
            "code_verifier": st.code_verifier,
        }
        try:
            async with self._client() as client:
                response = await client.post(url, data=form)
        except httpx.HTTPError as exc:
            raise KeycloakUnavailableError(f"{type(exc).__name__}: {exc}") from exc
        if response.status_code >= 500:
            raise KeycloakUnavailableError(f"token HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError as exc:
            raise OidcError("code_exchange_failed", "Keycloak вернул не JSON") from exc
        if response.status_code != 200 or "id_token" not in body:
            raise OidcError(
                "code_exchange_failed",
                "Не удалось завершить вход через ФСП ID, начните заново",
                {"error": body.get("error"), "error_description": body.get("error_description")},
            )
        return dict(body)

    async def identity_from_code(self, code: str, st: OidcState) -> FspIdentity:
        tokens = await self.exchange_code(code, st)
        # PyJWKClient синхронный (urllib) — уводим в поток, чтобы не блокировать цикл событий
        return await asyncio.to_thread(self.verifier.verify, tokens["id_token"], st.nonce)


def get_keycloak_client() -> KeycloakClient:
    """Зависимость FastAPI: клиент Keycloak из настроек (тесты подменяют её)."""
    settings = get_settings()
    return KeycloakClient(
        public_url=settings.keycloak_public_url,
        internal_url=settings.keycloak_internal_url,
        realm=settings.keycloak_realm,
        client_id=settings.keycloak_client_id,
        timeout=get_fsp_settings().keycloak_timeout_sec,
    )
