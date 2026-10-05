"""Ручки ФСП на БД: статус, привязка/отвязка через ФСП ID, вход, синхронизация, вебхук, T5.4.

Keycloak и реестр подменены фейками (tests/test_fsp_support.py); БД — настоящая (DATABASE_URL).
"""

import hashlib
import hmac
import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.fsp.oidc import get_keycloak_client
from app.fsp.registry import get_registry_client
from app.fsp.service import FspService, SyncReport, fsp_summaries
from app.fsp.settings import get_fsp_settings
from app.main import app
from tests.conftest import as_role
from tests.test_fsp_support import (
    FakeKeycloak,
    FakeRegistry,
    db_achievements,
    db_link,
    db_unlink,
    fsp_db,
    reset_baseline,
    run_db,
)

pytestmark = pytest.mark.usefixtures("fsp_db", "fakes")
_ = fsp_db  # фикстура подключается через usefixtures

CAND1 = as_role("candidate", 1)  # FSP-000001, есть история
CAND2 = as_role("candidate", 2)
CAND21 = as_role("candidate", 21)  # FSP-000031, без истории
CAND26 = as_role("candidate", 26)  # без ФСП ID
CALLBACK = "http://localhost:15173/auth/fsp-callback"


class Fakes:
    def __init__(self) -> None:
        self.registry = FakeRegistry()
        self.keycloak = FakeKeycloak()


@pytest.fixture
def fakes() -> Iterator[Fakes]:
    f = Fakes()
    app.dependency_overrides[get_registry_client] = lambda: f.registry.client()
    app.dependency_overrides[get_keycloak_client] = lambda: f.keycloak.client()
    yield f
    app.dependency_overrides.pop(get_registry_client, None)
    app.dependency_overrides.pop(get_keycloak_client, None)


@pytest.fixture
def restore() -> Iterator[None]:
    yield
    reset_baseline()


def start(client: TestClient, fakes: Fakes, purpose: str, fsp_id: str) -> dict[str, str]:
    """authorize-url (cookie со state) → «вход в Keycloak» → тело для обмена кода."""
    resp = client.get(
        "/api/auth/fsp/authorize-url", params={"purpose": purpose, "redirect_uri": CALLBACK}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["purpose"] == purpose
    state = fakes.keycloak.issue_code(body["authorize_url"], fsp_id)
    assert state == body["state"]
    return {"code": "code-1", "state": state, "redirect_uri": CALLBACK}


# ---------------------------------------------------------------- статус и T5.4


def test_status_with_history(client: TestClient) -> None:
    status = client.get("/api/fsp/status", headers=CAND1).json()
    assert status["linked"] and status["has_history"] and status["fsp_id"] == "FSP-000001"
    assert status["achievements_count"] == 7
    assert 0 < status["fsp_score"] <= 100
    assert {b["id"] for b in status["badges"]} >= {"international_winner", "participant_many"}
    assert all(b["verified"] for b in status["badges"])
    achs = client.get("/api/fsp/achievements", headers=CAND1).json()
    assert len(achs) == 7 and achs[0]["date"] >= achs[-1]["date"]
    assert {a["discipline"] for a in achs} <= {
        "product",
        "algorithmic",
        "cybersecurity",
        "uas",
        "robotics",
    }


def test_no_fsp_id_is_neutral(client: TestClient) -> None:
    status = client.get("/api/fsp/status", headers=CAND26).json()
    assert status["linked"] is False and status["fsp_score"] is None and status["badges"] == []
    assert "Нет данных ФСП" in status["message"]
    assert client.get("/api/fsp/achievements", headers=CAND26).json() == []
    sync = client.post("/api/fsp/sync", headers=CAND26)
    assert sync.status_code == 409 and sync.json()["code"] == "fsp_not_linked"
    unlink = client.delete("/api/auth/fsp-link", headers=CAND26)
    assert unlink.status_code == 409 and unlink.json()["code"] == "fsp_not_linked"


def test_linked_without_history_is_neutral(client: TestClient) -> None:
    status = client.get("/api/fsp/status", headers=CAND21).json()
    assert status["linked"] and status["fsp_id"] == "FSP-000031"
    assert status["has_history"] is False and status["fsp_score"] is None
    assert status["badges"] == [] and "не влияет на подбор" in status["message"]
    assert client.get("/api/fsp/achievements", headers=CAND21).json() == []
    synced = client.post("/api/fsp/sync", headers=CAND21)
    assert synced.status_code == 200 and synced.json()["has_history"] is False


def test_candidate_without_db_row_is_neutral(client: TestClient) -> None:
    # кандидат 30 есть в фикстурах, но не в БД: без 500, нейтрально
    status = client.get("/api/fsp/status", headers=as_role("candidate", 30))
    assert status.status_code == 200 and status.json()["linked"] is False


def test_summaries_for_ranking() -> None:
    async def q(s: AsyncSession) -> dict[int, Any]:
        return await fsp_summaries(s, [1, 21, 26, 999])

    summaries = run_db(q)
    assert summaries[1].fsp_score and summaries[1].badges and summaries[1].reason
    assert summaries[21].linked and summaries[21].fsp_score is None
    assert not summaries[26].linked and summaries[26].fsp_score is None
    assert not summaries[999].linked


# ---------------------------------------------------------------- authorize-url


def test_authorize_url_sets_state_cookie(client: TestClient, fakes: Fakes) -> None:
    resp = client.get("/api/auth/fsp/authorize-url", params={"purpose": "link"})
    assert resp.status_code == 200
    cookie = resp.headers["set-cookie"]
    assert "fsp_oidc_state=" in cookie and "HttpOnly" in cookie and "Path=/api/auth" in cookie
    assert "Max-Age=600" in cookie
    url = resp.json()["authorize_url"]
    assert url.startswith("http://kc-public.test/realms/fsp/protocol/openid-connect/auth?")
    assert "code_challenge_method=S256" in url and "code_verifier" not in url
    assert "auth%2Ffsp-callback" in url  # redirect_uri по умолчанию — фронт


def test_keycloak_down_gives_503_and_password_login_works(client: TestClient, fakes: Fakes) -> None:
    fakes.keycloak.down = True
    resp = client.get("/api/auth/fsp/authorize-url")
    assert resp.status_code == 503 and resp.json()["code"] == "keycloak_unavailable"
    login = client.post(
        "/api/auth/login", json={"email": "candidate@example.com", "password": "demo1234"}
    )
    assert login.status_code == 200


def test_keycloak_down_during_exchange(client: TestClient, fakes: Fakes) -> None:
    body = start(client, fakes, "login", "FSP-000001")
    fakes.keycloak.down = True
    resp = client.post("/api/auth/fsp/login", json=body)
    assert resp.status_code == 503 and resp.json()["code"] == "keycloak_unavailable"


# ---------------------------------------------------------------- вход


def test_login_linked_issues_session(client: TestClient, fakes: Fakes) -> None:
    body = start(client, fakes, "login", "FSP-000001")
    resp = client.post("/api/auth/fsp/login", json=body)
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["id"] == 1
    assert "refresh_token" in resp.cookies


def test_login_not_linked_404(client: TestClient, fakes: Fakes) -> None:
    body = start(client, fakes, "login", "FSP-000036")
    resp = client.post("/api/auth/fsp/login", json=body)
    assert resp.status_code == 404 and resp.json()["code"] == "fsp_account_not_linked"


def test_login_state_errors(client: TestClient, fakes: Fakes) -> None:
    body = start(client, fakes, "login", "FSP-000001")
    bad = client.post("/api/auth/fsp/login", json={**body, "state": "forged"})
    assert bad.status_code == 400 and bad.json()["details"]["reason"] == "state_mismatch"
    wrong_purpose = client.post("/api/auth/fsp-link", json=body, headers=CAND26)
    assert wrong_purpose.json()["details"]["reason"] == "purpose_mismatch"
    other_ru = client.post("/api/auth/fsp/login", json={**body, "redirect_uri": "http://evil/cb"})
    assert other_ru.json()["details"]["reason"] == "redirect_uri_mismatch"
    client.cookies.clear()
    missing = client.post("/api/auth/fsp/login", json=body)
    assert missing.status_code == 400 and missing.json()["details"]["reason"] == "state_missing"


def test_login_bad_code(client: TestClient, fakes: Fakes) -> None:
    body = start(client, fakes, "login", "FSP-000001")
    resp = client.post("/api/auth/fsp/login", json={**body, "code": "stolen"})
    assert resp.status_code == 400 and resp.json()["details"]["reason"] == "code_exchange_failed"


# ---------------------------------------------------------------- привязка и отвязка


@pytest.mark.usefixtures("restore")
def test_link_sync_unlink(client: TestClient, fakes: Fakes) -> None:
    body = start(client, fakes, "link", "FSP-000003")
    resp = client.post("/api/auth/fsp-link", json=body, headers=CAND26)
    assert resp.status_code == 200, resp.text
    status = resp.json()
    assert status["linked"] and status["fsp_id"] == "FSP-000003"
    assert status["achievements_count"] == 4 and status["fsp_score"] is not None
    link = db_link(26)
    assert link is not None and link.keycloak_sub == "sub-FSP-000003" and link.last_sync_at
    rows = db_achievements("FSP-000003")
    assert len(rows) == 4 and all(r.external_id.startswith("ACH-000003-") for r in rows)

    # повторная привязка того же ID — идемпотентна, дублей нет
    again = client.post(
        "/api/auth/fsp-link", json=start(client, fakes, "link", "FSP-000003"), headers=CAND26
    )
    assert again.status_code == 200 and len(db_achievements("FSP-000003")) == 4

    unlinked = client.delete("/api/auth/fsp-link", headers=CAND26)
    assert unlinked.status_code == 200 and unlinked.json()["linked"] is False
    assert db_link(26) is None and db_achievements("FSP-000003") == []
    assert client.get("/api/fsp/achievements", headers=CAND26).json() == []


@pytest.mark.usefixtures("restore")
def test_link_conflicts(client: TestClient, fakes: Fakes) -> None:
    taken = client.post(
        "/api/auth/fsp-link", json=start(client, fakes, "link", "FSP-000001"), headers=CAND26
    )
    assert taken.status_code == 409 and taken.json()["code"] == "fsp_id_taken"
    other = client.post(
        "/api/auth/fsp-link", json=start(client, fakes, "link", "FSP-000036"), headers=CAND1
    )
    assert other.status_code == 409 and other.json()["code"] == "fsp_already_linked"
    assert db_link(26) is None and db_link(1) is not None


@pytest.mark.usefixtures("restore")
def test_link_without_history(client: TestClient, fakes: Fakes) -> None:
    resp = client.post(
        "/api/auth/fsp-link", json=start(client, fakes, "link", "FSP-000036"), headers=CAND26
    )
    status = resp.json()
    assert resp.status_code == 200 and status["linked"] and status["has_history"] is False
    assert status["fsp_score"] is None and status["badges"] == []


@pytest.mark.usefixtures("restore")
def test_link_when_registry_down_then_refresh(client: TestClient, fakes: Fakes) -> None:
    fakes.registry.down = True
    resp = client.post(
        "/api/auth/fsp-link", json=start(client, fakes, "link", "FSP-000002"), headers=CAND26
    )
    # FSP-000002 уже у кандидата 2 — сначала освобождаем
    assert resp.status_code == 409
    db_unlink(2)
    resp = client.post(
        "/api/auth/fsp-link", json=start(client, fakes, "link", "FSP-000002"), headers=CAND26
    )
    assert resp.status_code == 200 and resp.json()["linked"]
    assert "недоступен" in resp.json()["message"]
    sync = client.post("/api/fsp/sync", headers=CAND26)
    assert sync.status_code == 503 and sync.json()["code"] == "fsp_registry_unavailable"
    fakes.registry.down = False
    sync = client.post("/api/fsp/sync", headers=CAND26)
    assert sync.status_code == 200 and sync.json()["achievements_count"] == 5


def test_registry_down_keeps_cache(client: TestClient, fakes: Fakes) -> None:
    fakes.registry.down = True
    assert client.post("/api/fsp/sync", headers=CAND1).status_code == 503
    status = client.get("/api/fsp/status", headers=CAND1).json()
    assert status["achievements_count"] == 7  # кэш не тронут


# ---------------------------------------------------------------- вебхук


def signed(payload: dict[str, Any], secret: str | None = None) -> tuple[bytes, dict[str, str]]:
    body = json.dumps(payload).encode()
    key = (secret or get_fsp_settings().webhook_secret).encode()
    sig = hmac.new(key, body, hashlib.sha256).hexdigest()
    return body, {"X-FSP-Signature": f"sha256={sig}", "Content-Type": "application/json"}


EVENT = {"event_id": "e1", "event": "participant.achievements_updated", "fsp_id": "FSP-000001"}


def test_webhook_valid_signature_resyncs(client: TestClient, fakes: Fakes) -> None:
    body, headers = signed({**EVENT, "sent_at": datetime.now(UTC).isoformat()})
    resp = client.post("/api/fsp/webhook", content=body, headers=headers)
    assert resp.status_code == 202, resp.text
    assert resp.json()["resynced"] is True and resp.json()["achievements_count"] == 7
    assert "/participants/FSP-000001/achievements" in fakes.registry.calls
    # повтор события не создаёт дублей
    client.post("/api/fsp/webhook", content=body, headers=headers)
    assert len(db_achievements("FSP-000001")) == 7


def test_webhook_bad_signature_401(client: TestClient, fakes: Fakes) -> None:
    body, headers = signed(EVENT, secret="wrong")
    resp = client.post("/api/fsp/webhook", content=body, headers=headers)
    assert resp.status_code == 401 and resp.json()["code"] == "invalid_signature"
    no_sig = client.post("/api/fsp/webhook", content=body)
    assert no_sig.status_code == 401
    assert fakes.registry.calls == []


def test_webhook_tampered_body_401(client: TestClient) -> None:
    body, headers = signed(EVENT)
    tampered = body.replace(b"FSP-000001", b"FSP-000002")
    assert client.post("/api/fsp/webhook", content=tampered, headers=headers).status_code == 401


def test_webhook_expired_and_ignored(client: TestClient, fakes: Fakes) -> None:
    old = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    body, headers = signed({**EVENT, "sent_at": old})
    resp = client.post("/api/fsp/webhook", content=body, headers=headers)
    assert resp.status_code == 401 and resp.json()["code"] == "webhook_expired"
    body, headers = signed({**EVENT, "fsp_id": "FSP-000025"})  # не привязан
    resp = client.post("/api/fsp/webhook", content=body, headers=headers)
    assert resp.status_code == 202 and resp.json()["status"] == "ignored"
    body, headers = signed({**EVENT, "event": "participant.profile_updated"})
    assert (
        client.post("/api/fsp/webhook", content=body, headers=headers).json()["resynced"] is False
    )
    body, headers = signed({"event": "x", "fsp_id": "bad"})
    assert client.post("/api/fsp/webhook", content=body, headers=headers).status_code == 422


# ---------------------------------------------------------------- пакетная синхронизация


def test_batch_sync_only_changed() -> None:
    reg = FakeRegistry()

    async def q(s: AsyncSession) -> SyncReport:
        return await FspService(s, reg.client()).sync_many(["FSP-000001", "FSP-000031"])

    report = run_db(q)  # в базе last_sync_at = 06.10 03:00, реестр — 01.10: ничего не менялось
    assert report.checked == 2 and report.updated == [] and len(report.unchanged) == 2
    reg.updated_at["FSP-000001"] = "2030-01-01T00:00:00Z"
    report = run_db(q)
    assert report.updated == ["FSP-000001"] and report.unchanged == ["FSP-000031"]
    assert len(db_achievements("FSP-000001")) == 7
    reg.down = True
    assert run_db(q).failed == ["FSP-000001", "FSP-000031"]


def test_service_sync_unknown_participant_clears_cache() -> None:
    class Gone(FakeRegistry):
        def __post_init__(self) -> None:
            super().__post_init__()
            self.people.pop("FSP-000031")

    async def q(s: AsyncSession) -> SyncReport:
        return await FspService(s, Gone().client()).sync_many(["FSP-000031"])

    assert run_db(q).not_found == ["FSP-000031"]
