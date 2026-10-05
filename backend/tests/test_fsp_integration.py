"""Интеграция с настоящим Keycloak (realm fsp) и моком реестра: полный проход ФСП ID.

Authorization Code + PKCE через форму входа Keycloak (fsp.user02 / Fsp-demo-2026) →
`POST /api/auth/fsp-link` → достижения в БД → `POST /api/auth/fsp/login` выдаёт сессию.

Пропускается, если Keycloak (`KEYCLOAK_INTERNAL_URL`) или реестр (`FSP_REGISTRY_URL`) не отвечают.
Локально: KEYCLOAK_INTERNAL_URL=http://localhost:18180 FSP_REGISTRY_URL=http://localhost:18100.
"""

import html
import re
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.fsp.oidc import _realm_base
from tests.conftest import as_role
from tests.test_fsp_support import db_achievements, db_link, db_unlink, fsp_db

_ = fsp_db
CALLBACK = "http://localhost:15173/auth/fsp-callback"
USER, PASSWORD = "fsp.user02", "Fsp-demo-2026"


def _reachable() -> str | None:
    s = get_settings()
    checks = {
        "Keycloak": f"{_realm_base(s.keycloak_internal_url, s.keycloak_realm)}"
        "/.well-known/openid-configuration",
        "Keycloak (публичный адрес)": f"{_realm_base(s.keycloak_public_url, s.keycloak_realm)}"
        "/.well-known/openid-configuration",
        "реестр ФСП": f"{s.fsp_registry_url.rstrip('/')}/health",
    }
    for name, url in checks.items():
        try:
            if httpx.get(url, timeout=3).status_code != 200:
                return f"{name} отвечает не 200: {url}"
        except httpx.HTTPError:
            return f"{name} недоступен: {url}"
    return None


SKIP_REASON = _reachable()
pytestmark = [
    pytest.mark.skipif(SKIP_REASON is not None, reason=SKIP_REASON or ""),
    pytest.mark.usefixtures("fsp_db"),
]


def keycloak_login(browser: httpx.Client, authorize_url: str) -> dict[str, str]:
    """Как браузер: страница входа → форма → редирект на redirect_uri с code и state."""
    page = browser.get(authorize_url)
    if page.status_code in (302, 303):  # уже есть SSO-сессия Keycloak
        location = page.headers["location"]
    else:
        assert page.status_code == 200, page.text[:500]
        match = re.search(r'<form[^>]*id="kc-form-login"[^>]*action="([^"]+)"', page.text)
        assert match, "форма входа Keycloak не найдена"
        resp = browser.post(
            html.unescape(match.group(1)),
            data={"username": USER, "password": PASSWORD, "credentialId": ""},
        )
        assert resp.status_code in (302, 303), resp.text[:500]
        location = resp.headers["location"]
    assert location.startswith(CALLBACK), location
    query = {k: v[0] for k, v in parse_qs(urlparse(location).query).items()}
    return {"code": query["code"], "state": query["state"]}


def test_full_flow_link_then_login(client: TestClient) -> None:
    db_unlink(2)
    assert db_link(2) is None
    with httpx.Client(follow_redirects=False, timeout=10) as browser:
        # 1. привязка
        url = client.get(
            "/api/auth/fsp/authorize-url", params={"purpose": "link", "redirect_uri": CALLBACK}
        ).json()["authorize_url"]
        assert url.startswith(get_settings().keycloak_public_url)
        callback = keycloak_login(browser, url)
        linked = client.post("/api/auth/fsp-link", json=callback, headers=as_role("candidate", 2))
        assert linked.status_code == 200, linked.text
        body = linked.json()
        assert body["fsp_id"] == "FSP-000002" and body["achievements_count"] == 5
        assert body["fsp_score"] is not None and body["badges"]
        link = db_link(2)
        assert link is not None and link.keycloak_sub and link.last_sync_at
        assert len(db_achievements("FSP-000002")) == 5

        # 2. вход через ФСП ID (SSO-сессия Keycloak уже есть — форма не показывается)
        url = client.get(
            "/api/auth/fsp/authorize-url", params={"purpose": "login", "redirect_uri": CALLBACK}
        ).json()["authorize_url"]
        session = client.post("/api/auth/fsp/login", json=keycloak_login(browser, url))
        assert session.status_code == 200, session.text
        assert session.json()["user"]["id"] == 2
        assert "refresh_token" in session.cookies

        # 3. отвязка → вход через ФСП ID больше не работает
        assert (
            client.delete("/api/auth/fsp-link", headers=as_role("candidate", 2)).status_code == 200
        )
        url = client.get(
            "/api/auth/fsp/authorize-url", params={"purpose": "login", "redirect_uri": CALLBACK}
        ).json()["authorize_url"]
        denied = client.post("/api/auth/fsp/login", json=keycloak_login(browser, url))
        assert denied.status_code == 404 and denied.json()["code"] == "fsp_account_not_linked"
