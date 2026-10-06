"""Единая выдача сессии (`app.auth.sessions`) — её вызывает вход через ФСП ID (трек 2c)."""

from fastapi.testclient import TestClient

from tests.test_auth_helpers import _cleanup_module, api, bearer

__all__ = ["_cleanup_module", "api"]


def test_issue_session_gives_working_access_and_refresh(api: TestClient) -> None:
    """`issue_session` (её вызывает вход через ФСП ID) выдаёт рабочий access и refresh-cookie."""
    from fastapi import Response

    from app.auth.sessions import REFRESH_COOKIE, issue_session

    response = Response()
    token = issue_session(response, 1)
    assert token["user"]["id"] == 1
    cookie = response.headers.get("set-cookie", "")
    assert cookie.startswith(f"{REFRESH_COOKIE}=") and "HttpOnly" in cookie
    me = api.get("/api/auth/me", headers=bearer(token["access_token"]))
    assert me.status_code == 200 and me.json()["id"] == 1
    api.cookies.set(REFRESH_COOKIE, cookie.split(";", 1)[0].split("=", 1)[1], path="/api/auth")
    refreshed = api.post("/api/auth/refresh")
    assert refreshed.status_code == 200, refreshed.text
