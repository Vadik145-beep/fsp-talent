"""Регистрация → письмо → подтверждение → вход → me → refresh (ротация) → выход и ошибки входа."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from tests.test_auth_helpers import (
    PASSWORD,
    Outbox,
    _cleanup_module,
    api,
    bearer,
    db_exec,
    login,
    new_email,
    outbox,
    register,
    verified_user,
)

__all__ = ["_cleanup_module", "api", "outbox"]


def test_full_flow_candidate(api: TestClient, outbox: Outbox) -> None:
    email = new_email()
    created = register(api, email)
    assert created["status"] == "pending_verification"

    # письмо со ссылкой на фронт
    [message] = outbox.for_(email)
    link_prefix = f"{get_settings().public_frontend_url}/verify-email?token="
    assert link_prefix in message["text"] and link_prefix in message["html"]

    # пароль — хеш, согласие — с версией и датой, токен — только хеш
    [(password_hash, verified)] = db_exec(
        "SELECT password_hash, email_verified FROM users WHERE id = :id",
        {"id": created["user_id"]},
    )
    assert password_hash.startswith("scrypt$") and PASSWORD not in password_hash
    assert not verified
    [(ctype, version, granted, granted_at)] = db_exec(
        "SELECT type, version, granted, granted_at FROM consents WHERE user_id = :id",
        {"id": created["user_id"]},
    )
    assert (ctype, version, granted) == ("processing", "2026-10-01", True) and granted_at
    token = outbox.last_token(email)
    assert not db_exec("SELECT 1 FROM email_tokens WHERE token_hash = :t", {"t": token})

    # без подтверждения войти нельзя
    response = login(api, email)
    assert response.status_code == 403 and response.json()["code"] == "email_not_verified"

    response = api.post("/api/auth/verify-email", json={"token": token})
    assert response.status_code == 200, response.text
    again = api.post("/api/auth/verify-email", json={"token": token})
    assert again.status_code == 200  # повторный клик по ссылке — не ошибка

    response = login(api, email)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 15 * 60
    assert body["access_token"].count(".") == 2  # JWT
    first_refresh = response.cookies["refresh_token"]
    set_cookie = response.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "path=/api/auth" in set_cookie

    me = api.get("/api/auth/me", headers=bearer(body["access_token"]))
    assert me.status_code == 200, me.text
    me_body = me.json()
    assert me_body["email"] == email and me_body["role"] == "candidate"
    assert me_body["email_verified"] is True and me_body["candidate_id"] is not None
    assert me_body["id"] == created["user_id"] and me_body["fsp_id"] is None

    # refresh: ротация, старый токен больше не работает
    refreshed = api.post("/api/auth/refresh")
    assert refreshed.status_code == 200, refreshed.text
    second_refresh = refreshed.cookies["refresh_token"]
    assert second_refresh != first_refresh
    new_access = refreshed.json()["access_token"]
    assert api.get("/api/auth/me", headers=bearer(new_access)).status_code == 200

    api.cookies.clear()
    old = api.post("/api/auth/refresh", cookies={"refresh_token": first_refresh})
    assert old.status_code == 401 and old.json()["code"] == "invalid_refresh_token"

    # выход отзывает текущую сессию и удаляет cookie
    api.cookies.clear()
    out = api.post("/api/auth/logout", cookies={"refresh_token": second_refresh})
    assert out.status_code == 204
    assert 'refresh_token=""' in out.headers["set-cookie"] or "max-age=0" in (
        out.headers["set-cookie"].lower()
    )
    api.cookies.clear()
    after = api.post("/api/auth/refresh", cookies={"refresh_token": second_refresh})
    assert after.status_code == 401


def test_register_taken_and_consent_required(api: TestClient, outbox: Outbox) -> None:
    email = verified_user(api, outbox)
    body = {
        "email": email,
        "password": PASSWORD,
        "full_name": "Другой",
        "role": "candidate",
        "consent_processing": True,
    }
    taken = api.post("/api/auth/register", json=body)
    assert taken.status_code == 409 and taken.json()["code"] == "email_taken"
    upper = api.post("/api/auth/register", json={**body, "email": email.upper()})
    assert upper.status_code == 409
    no_consent = api.post(
        "/api/auth/register", json={**body, "email": new_email(), "consent_processing": False}
    )
    assert no_consent.status_code == 422


def test_reregister_unverified_keeps_first_password(
    api: TestClient, outbox: Outbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "email_resend_interval_sec", 0)
    email = new_email()
    first = register(api, email)
    second = register(api, email, password="Attacker-pass-2")
    assert second["user_id"] == first["user_id"]
    assert len(outbox.for_(email)) == 2
    api.post("/api/auth/verify-email", json={"token": outbox.last_token(email)})
    assert login(api, email, "Attacker-pass-2").status_code == 401
    assert login(api, email).status_code == 200


def test_recruiter_creates_company_and_colleague_joins_by_code(
    api: TestClient, outbox: Outbox
) -> None:
    owner = new_email()
    created = register(api, owner, "recruiter", company={"name": "ООО «Тест»", "inn": "7701234567"})
    [(company_id, code, is_admin)] = db_exec(
        "SELECT c.id, c.invite_code, r.is_company_admin FROM recruiters r "
        "JOIN companies c ON c.id = r.company_id WHERE r.user_id = :id",
        {"id": created["user_id"]},
    )
    assert code and is_admin

    colleague = new_email()
    joined = register(api, colleague, "recruiter", company={"invite_code": code})
    [(joined_company, joined_admin)] = db_exec(
        "SELECT company_id, is_company_admin FROM recruiters WHERE user_id = :id",
        {"id": joined["user_id"]},
    )
    assert joined_company == company_id and not joined_admin

    bad = api.post(
        "/api/auth/register",
        json={
            "email": new_email(),
            "password": PASSWORD,
            "full_name": "Тест",
            "role": "recruiter",
            "consent_processing": True,
            "company": {"invite_code": "NOPE0000"},
        },
    )
    assert bad.status_code == 404 and bad.json()["code"] == "company_invite_not_found"

    api.post("/api/auth/verify-email", json={"token": outbox.last_token(colleague)})
    token = login(api, colleague).json()["access_token"]
    me = api.get("/api/auth/me", headers=bearer(token)).json()
    assert me["role"] == "recruiter" and me["company_id"] == company_id
    assert me["recruiter_id"] is not None and me["candidate_id"] is None


def test_wrong_password_and_lockout(api: TestClient, outbox: Outbox) -> None:
    email = verified_user(api, outbox)
    limit = get_settings().login_max_attempts
    for _ in range(limit):
        bad = login(api, email, "wrong-password")
        assert bad.status_code == 401 and bad.json()["code"] == "invalid_credentials"
    locked = login(api, email)  # даже с верным паролем
    assert locked.status_code == 429 and locked.json()["code"] == "too_many_attempts"


def test_lockout_also_for_unknown_email(api: TestClient) -> None:
    email = new_email()
    for _ in range(get_settings().login_max_attempts):
        assert login(api, email, "x").status_code == 401
    assert login(api, email, "x").status_code == 429


def test_success_resets_failed_attempts(api: TestClient, outbox: Outbox) -> None:
    email = verified_user(api, outbox)
    limit = get_settings().login_max_attempts
    for _ in range(limit - 1):
        assert login(api, email, "wrong").status_code == 401
    assert login(api, email).status_code == 200
    for _ in range(limit - 1):
        assert login(api, email, "wrong").status_code == 401
    assert login(api, email).status_code == 200


def test_blocked_user(api: TestClient, outbox: Outbox) -> None:
    email = verified_user(api, outbox)
    response = login(api, email)
    access = response.json()["access_token"]
    refresh_token = response.cookies["refresh_token"]
    db_exec("UPDATE users SET blocked = true WHERE email = :e", {"e": email})

    blocked = login(api, email)
    assert blocked.status_code == 403 and blocked.json()["code"] == "user_blocked"
    me = api.get("/api/auth/me", headers=bearer(access))
    assert me.status_code == 403 and me.json()["code"] == "user_blocked"
    api.cookies.clear()
    refreshed = api.post("/api/auth/refresh", cookies={"refresh_token": refresh_token})
    assert refreshed.status_code == 403


def test_verification_token_expired_and_invalid(api: TestClient, outbox: Outbox) -> None:
    email = new_email()
    register(api, email)
    token = outbox.last_token(email)
    db_exec(
        "UPDATE email_tokens SET expires_at = now() - interval '1 minute' "
        "WHERE user_id = (SELECT id FROM users WHERE email = :e)",
        {"e": email},
    )
    expired = api.post("/api/auth/verify-email", json={"token": token})
    assert expired.status_code == 410 and expired.json()["code"] == "token_expired"
    invalid = api.post("/api/auth/verify-email", json={"token": "x" * 43})
    assert invalid.status_code == 400 and invalid.json()["code"] == "token_invalid"


def test_resend_verification(
    api: TestClient, outbox: Outbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    email = new_email()
    register(api, email)
    first_token = outbox.last_token(email)

    too_soon = api.post("/api/auth/resend-verification", json={"email": email})
    assert too_soon.status_code == 429 and too_soon.json()["code"] == "too_many_requests"

    monkeypatch.setattr(get_settings(), "email_resend_interval_sec", 0)
    resent = api.post("/api/auth/resend-verification", json={"email": email})
    assert resent.status_code == 202
    new_token = outbox.last_token(email)
    assert new_token != first_token
    # одинаковый ответ для неизвестной почты
    unknown = api.post("/api/auth/resend-verification", json={"email": new_email()})
    assert unknown.status_code == 202 and unknown.json() == resent.json()

    # старая ссылка погашена, новая работает
    assert api.post("/api/auth/verify-email", json={"token": first_token}).status_code == 400
    assert api.post("/api/auth/verify-email", json={"token": new_token}).status_code == 200


def test_password_reset(api: TestClient, outbox: Outbox, monkeypatch: pytest.MonkeyPatch) -> None:
    email = verified_user(api, outbox)
    old_session = login(api, email).cookies["refresh_token"]

    unknown = api.post("/api/auth/password-reset/request", json={"email": new_email()})
    response = api.post("/api/auth/password-reset/request", json={"email": email})
    assert response.status_code == 202 and unknown.status_code == 202
    assert response.json() == unknown.json()
    message = outbox.for_(email)[-1]
    assert f"{get_settings().public_frontend_url}/reset-password?token=" in message["text"]
    token = outbox.last_token(email)

    again = api.post("/api/auth/password-reset/request", json={"email": email})
    assert again.status_code == 429

    confirm = api.post(
        "/api/auth/password-reset/confirm", json={"token": token, "new_password": "New-pass-123"}
    )
    assert confirm.status_code == 200, confirm.text
    reused = api.post(
        "/api/auth/password-reset/confirm", json={"token": token, "new_password": "Other-pass-1"}
    )
    assert reused.status_code == 400

    assert login(api, email).status_code == 401
    assert login(api, email, "New-pass-123").status_code == 200
    # после смены пароля прежние сессии отозваны
    api.cookies.clear()
    assert api.post("/api/auth/refresh", cookies={"refresh_token": old_session}).status_code == 401


def test_password_reset_token_expired(
    api: TestClient, outbox: Outbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    email = verified_user(api, outbox)
    api.post("/api/auth/password-reset/request", json={"email": email})
    token = outbox.last_token(email)
    db_exec(
        "UPDATE email_tokens SET expires_at = now() - interval '1 minute' "
        "WHERE purpose = 'reset_password' AND user_id = (SELECT id FROM users WHERE email = :e)",
        {"e": email},
    )
    response = api.post(
        "/api/auth/password-reset/confirm", json={"token": token, "new_password": "New-pass-123"}
    )
    assert response.status_code == 410


def test_refresh_without_cookie(api: TestClient) -> None:
    response = api.post("/api/auth/refresh")
    assert response.status_code == 401 and response.json()["code"] == "invalid_refresh_token"
