"""Текущий пользователь и RBAC: Bearer, демо-заголовки, роли, админ по умолчанию."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security import JWT_ALGORITHM, JWT_ISSUER
from tests.conftest import ADMIN, CANDIDATE, RECRUITER
from tests.test_auth_helpers import (
    Outbox,
    _cleanup_module,
    api,
    bearer,
    db_exec,
    login,
    outbox,
    verified_user,
)

__all__ = ["_cleanup_module", "api", "outbox"]


def _access(client: TestClient, outbox: Outbox, role: str = "candidate") -> str:
    email = verified_user(client, outbox, role)
    response = login(client, email)
    assert response.status_code == 200, response.text
    token: str = response.json()["access_token"]
    return token


def test_bearer_has_priority_over_demo_headers(api: TestClient, outbox: Outbox) -> None:
    token = _access(api, outbox)
    me = api.get("/api/auth/me", headers={**ADMIN, **bearer(token)})
    assert me.status_code == 200 and me.json()["role"] == "candidate"
    # с Bearer кандидата админка закрыта, хотя в заголовке X-Demo-Role: admin
    assert api.get("/api/admin/dashboard", headers={**ADMIN, **bearer(token)}).status_code == 403


def test_invalid_bearer_does_not_fall_back_to_demo(api: TestClient) -> None:
    response = api.get("/api/auth/me", headers={**ADMIN, **bearer("not-a-jwt")})
    assert response.status_code == 401 and response.json()["code"] == "token_invalid"


def test_expired_and_forged_tokens(api: TestClient) -> None:
    now = datetime.now(UTC)
    claims = {"sub": "48", "role": "admin", "typ": "access", "iss": JWT_ISSUER, "iat": now}
    expired = jwt.encode(
        {**claims, "exp": now - timedelta(seconds=1)},
        get_settings().jwt_secret,
        algorithm=JWT_ALGORITHM,
    )
    response = api.get("/api/auth/me", headers=bearer(expired))
    assert response.status_code == 401 and response.json()["code"] == "token_expired"

    forged = jwt.encode(
        {**claims, "exp": now + timedelta(minutes=5)}, "wrong-secret", algorithm=JWT_ALGORITHM
    )
    response = api.get("/api/auth/me", headers=bearer(forged))
    assert response.status_code == 401 and response.json()["code"] == "token_invalid"

    unsigned = jwt.encode({**claims, "exp": now + timedelta(minutes=5)}, "", algorithm="none")
    assert api.get("/api/auth/me", headers=bearer(unsigned)).status_code == 401


def test_demo_headers_disabled(
    api: TestClient, outbox: Outbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = _access(api, outbox)
    monkeypatch.setattr(get_settings(), "demo_auth_enabled", False)
    response = api.get("/api/auth/me", headers=CANDIDATE)
    assert response.status_code == 401 and response.json()["code"] == "unauthorized"
    # Bearer работает и без демо-режима
    assert api.get("/api/auth/me", headers=bearer(token)).status_code == 200
    # демо-учётки залиты сидом в БД (пароль захеширован) — входят обычным путём и без демо-режима
    demo = login(api, "candidate@example.com", "demo1234")
    assert demo.status_code == 200


def test_demo_headers_still_work(api: TestClient) -> None:
    for headers, role in ((CANDIDATE, "candidate"), (RECRUITER, "recruiter"), (ADMIN, "admin")):
        me = api.get("/api/auth/me", headers=headers)
        assert me.status_code == 200 and me.json()["role"] == role


def test_candidate_cannot_use_recruiter_and_admin_endpoints(
    api: TestClient, outbox: Outbox
) -> None:
    token = _access(api, outbox)
    for method, path in (
        ("GET", "/api/matching/needs"),
        ("GET", "/api/admin/dashboard"),
        ("PATCH", "/api/admin/users/1"),
    ):
        response = api.request(method, path, headers=bearer(token), json={"role": "admin"})
        assert response.status_code == 403, (method, path, response.text)
        assert response.json()["code"] == "forbidden"


def test_recruiter_cannot_use_candidate_endpoints(api: TestClient, outbox: Outbox) -> None:
    token = _access(api, outbox, "recruiter")
    response = api.get("/api/candidates/me/profile", headers=bearer(token))
    assert response.status_code == 403
    assert api.get("/api/matching/needs", headers=bearer(token)).status_code == 200


def test_no_auth_is_401(api: TestClient) -> None:
    assert api.get("/api/auth/me").status_code == 401


def test_default_admin_created_and_only_admin_can_promote(api: TestClient, outbox: Outbox) -> None:
    settings = get_settings()
    rows = db_exec(
        "SELECT role, email_verified, password_hash FROM users WHERE email = :e",
        {"e": settings.admin_email},
    )
    assert rows and rows[0][0] == "admin" and rows[0][1] and rows[0][2].startswith("scrypt$")

    response = login(api, settings.admin_email, settings.admin_password)
    assert response.status_code == 200, response.text
    admin_token = response.json()["access_token"]
    assert response.json()["user"]["role"] == "admin"
    assert api.get("/api/admin/dashboard", headers=bearer(admin_token)).status_code == 200
    promote = api.patch("/api/admin/users/1", headers=bearer(admin_token), json={"role": "admin"})
    assert promote.status_code == 200, promote.text

    recruiter_token = _access(api, outbox, "recruiter")
    denied = api.patch(
        "/api/admin/users/1", headers=bearer(recruiter_token), json={"role": "admin"}
    )
    assert denied.status_code == 403
