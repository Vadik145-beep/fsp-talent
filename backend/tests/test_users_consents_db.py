"""Согласия 152-ФЗ пользователя из БД: версия текста и даты сохраняются, отзыв фиксируется."""

from fastapi.testclient import TestClient

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


def test_consents_saved_in_db(api: TestClient, outbox: Outbox) -> None:
    email = verified_user(api, outbox)
    headers = bearer(login(api, email).json()["access_token"])

    consents = api.get("/api/users/me/consents", headers=headers).json()
    assert [(c["type"], c["granted"], c["version"]) for c in consents] == [
        ("processing", True, "2026-10-01")
    ]

    granted = api.put(
        "/api/users/me/consents/publication",
        json={"granted": True, "version": "2026-10-01"},
        headers=headers,
    )
    assert granted.status_code == 200 and granted.json()["granted_at"]
    revoked = api.put(
        "/api/users/me/consents/publication", json={"granted": False}, headers=headers
    )
    body = revoked.json()
    assert revoked.status_code == 200 and not body["granted"] and body["revoked_at"]

    [(granted_db, revoked_at)] = db_exec(
        "SELECT granted, revoked_at FROM consents c JOIN users u ON u.id = c.user_id "
        "WHERE u.email = :e AND c.type = 'publication'",
        {"e": email},
    )
    assert granted_db is False and revoked_at is not None

    forbidden = api.put(
        "/api/users/me/consents/processing", json={"granted": False}, headers=headers
    )
    assert forbidden.status_code == 409 and forbidden.json()["code"] == "consent_required"
