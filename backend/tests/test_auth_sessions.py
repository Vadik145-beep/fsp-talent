"""Единая выдача сессии (`app.auth.sessions`) — её вызывает вход через ФСП ID (трек 2c)."""

from fastapi.testclient import TestClient

from tests.test_auth_helpers import _cleanup_module, api, bearer

__all__ = ["_cleanup_module", "api"]


def test_fsp_login_stub_uses_sync_issue_session(api: TestClient) -> None:
    """Синхронная `issue_session` (прежняя сигнатура) работает внутри async-эндпоинта."""
    body = {
        "code": "kc-auth-code",
        "state": "b1f0c2",
        "code_verifier": "v" * 43,
        "redirect_uri": "http://localhost:15173/auth/fsp-callback",
    }
    response = api.post("/api/auth/fsp/login", json=body)
    assert response.status_code == 200, response.text
    assert "refresh_token" in response.cookies
    token = response.json()["access_token"]
    me = api.get("/api/auth/me", headers=bearer(token))
    assert me.status_code == 200 and me.json()["id"] == response.json()["user"]["id"]
    refreshed = api.post("/api/auth/refresh")
    assert refreshed.status_code == 200, refreshed.text
