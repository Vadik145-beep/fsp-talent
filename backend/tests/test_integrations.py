"""Интеграция с ATS (T12.2): API-токены, выгрузка, вебхуки на локальный тестовый сервер."""

import asyncio
import json
import threading
from collections.abc import Awaitable, Callable, Iterator
from datetime import timedelta
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.catalog.clock import now_msk
from app.core.config import get_settings
from app.integrations.settings import get_integration_settings
from app.integrations.webhooks import (
    deliver_pending,
    notify_application_created,
    notify_invitation_accepted,
    short_body,
    verify,
)
from app.seed.testkit import reseed_sync, sql_sync
from tests.conftest import ADMIN, CANDIDATE, RECRUITER, RECRUITER_C2, as_role

RECRUITER_NOT_ADMIN = as_role("recruiter", 42)


class Receiver:
    """Локальный HTTP-сервер — «ATS» компании: запоминает запросы, отвечает заданными кодами."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.codes: list[int] = []  # очередь ответов; пусто — 200
        receiver = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                receiver.requests.append(
                    {"path": self.path, "headers": dict(self.headers), "body": body}
                )
                code = receiver.codes.pop(0) if receiver.codes else 200
                self.send_response(code)
                self.end_headers()
                self.wfile.write(b"ok")

            def log_message(self, *args: Any) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/hooks/fsp"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


async def deliver_later(session: AsyncSession, days: int) -> Any:
    """Доставка вебхуков так, будто прошло days дней (для повторов с паузой)."""
    return await deliver_pending(session, now_msk() + timedelta(days=days))


def run_db[T](fn: Callable[[AsyncSession], Awaitable[T]]) -> T:
    async def go() -> T:
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                return await fn(session)
        finally:
            await engine.dispose()

    return asyncio.run(go())


@pytest.fixture(autouse=True)
def _fresh_db() -> Iterator[None]:
    reseed_sync()
    yield


@pytest.fixture(scope="module", autouse=True)
def _restore_db() -> Iterator[None]:
    yield
    reseed_sync()


@pytest.fixture
def receiver() -> Iterator[Receiver]:
    r = Receiver()
    yield r
    r.close()


def add_webhook(client: TestClient, url: str, events: list[str]) -> dict[str, Any]:
    res = client.post(
        "/api/companies/my/webhooks", json={"url": url, "events": events}, headers=RECRUITER
    )
    assert res.status_code == 201, res.text
    return dict(res.json())


def test_api_token_lifecycle_and_export(client: TestClient) -> None:
    assert (
        client.get("/api/companies/my/api-tokens", headers=RECRUITER_NOT_ADMIN).status_code == 403
    )
    issued = client.post(
        "/api/companies/my/api-tokens", json={"name": "Хантфлоу"}, headers=RECRUITER
    )
    assert issued.status_code == 201, issued.text
    token = issued.json()["token"]
    assert token.startswith("fspt_") and issued.json()["token_prefix"] == token[:12]
    listed = client.get("/api/companies/my/api-tokens", headers=RECRUITER).json()
    assert listed[0]["active"] is True and "token" not in listed[0]
    stored = sql_sync("SELECT token_hash FROM company_api_tokens")[0][0]
    assert token not in stored and len(stored) == 64

    export = client.get("/api/companies/ats/export", headers={"X-Api-Token": token})
    assert export.status_code == 200, export.text
    data = export.json()
    assert data["company"]["id"] == 1
    assert {v["id"] for v in data["vacancies"]} == {
        r[0] for r in sql_sync("SELECT id FROM vacancies WHERE company_id = 1")
    }
    for inv in data["invitations"]:
        has_contacts = "contacts" in (inv["candidate"] or {})
        assert has_contacts == (inv["status"] == "accepted")
    assert data["applications"] and all("contacts" in a["candidate"] for a in data["applications"])
    assert sql_sync("SELECT last_used_at IS NOT NULL FROM company_api_tokens")[0][0] is True
    since = client.get(
        "/api/companies/ats/export",
        params={"since": (now_msk() + timedelta(days=1)).isoformat()},
        headers={"X-Api-Token": token},
    ).json()
    assert since["vacancies"] == [] and since["invitations"] == []

    # чужой токен не открывает данные другой компании; отзыв — 401
    other = client.post(
        "/api/companies/my/api-tokens", json={"name": "C2"}, headers=RECRUITER_C2
    ).json()
    assert (
        client.get("/api/companies/ats/export", headers={"X-Api-Token": other["token"]}).json()[
            "company"
        ]["id"]
        == 2
    )
    assert (
        client.delete(f"/api/companies/my/api-tokens/{other['id']}", headers=RECRUITER).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/companies/my/api-tokens/{issued.json()['id']}", headers=RECRUITER
        ).status_code
        == 204
    )
    revoked = client.get("/api/companies/ats/export", headers={"X-Api-Token": token})
    assert revoked.status_code == 401 and revoked.json()["code"] == "invalid_api_token"
    assert client.get("/api/companies/ats/export").status_code == 401
    assert (
        client.get("/api/companies/ats/export", headers={"X-Api-Token": "fspt_wrong"}).status_code
        == 401
    )
    actions = [
        r[0]
        for r in sql_sync(
            "SELECT action FROM audit_log WHERE action LIKE 'api_token_%' ORDER BY id"
        )
    ]
    assert actions == ["api_token_issued", "api_token_issued", "api_token_revoked"]


def test_export_refused_for_blocked_company(client: TestClient) -> None:
    token = client.post(
        "/api/companies/my/api-tokens", json={"name": "ATS"}, headers=RECRUITER
    ).json()["token"]
    sql_sync("UPDATE companies SET blocked = true WHERE id = 1")
    res = client.get("/api/companies/ats/export", headers={"X-Api-Token": token})
    assert res.status_code == 403 and res.json()["code"] == "company_blocked"


def test_webhook_ping_signed(client: TestClient, receiver: Receiver) -> None:
    hook = add_webhook(client, receiver.url, ["invitation.accepted"])
    assert len(hook["secret"]) >= 16
    assert "secret" not in client.get("/api/companies/my/webhooks", headers=RECRUITER).json()[0]
    ping = client.post(f"/api/companies/my/webhooks/{hook['id']}/ping", headers=RECRUITER)
    assert ping.status_code == 200, ping.text
    assert ping.json()["status"] == "delivered" and ping.json()["attempts"] == 1
    assert len(receiver.requests) == 1
    req = receiver.requests[0]
    headers = {k.lower(): v for k, v in req["headers"].items()}
    assert req["path"] == "/hooks/fsp" and headers["x-fsp-event"] == "ping"
    assert verify(
        hook["secret"], headers["x-fsp-timestamp"], req["body"], headers["x-fsp-signature"]
    )
    assert not verify(
        "wrong-secret-0000", headers["x-fsp-timestamp"], req["body"], headers["x-fsp-signature"]
    )
    body = json.loads(req["body"])
    assert body["event"] == "ping" and body["company_id"] == 1 and body["id"] == ping.json()["id"]
    log = client.get(
        f"/api/companies/my/webhooks/{hook['id']}/deliveries", headers=RECRUITER
    ).json()
    assert log[0]["status"] == "delivered" and log[0]["last_status_code"] == 200


def test_invitation_accepted_and_application_events(client: TestClient, receiver: Receiver) -> None:
    add_webhook(client, receiver.url, ["invitation.accepted"])
    only_apps = add_webhook(client, receiver.url + "/apps", ["application.created"])

    run_db(lambda s: notify_invitation_accepted(s, 8))  # приглашение 8 компании 1 — принято
    assert len(receiver.requests) == 1
    event = json.loads(receiver.requests[0]["body"])
    assert event["event"] == "invitation.accepted" and receiver.requests[0]["path"] == "/hooks/fsp"
    data = event["data"]
    assert data["invitation_id"] == 8 and data["status"] == "accepted"
    assert data["candidate"]["contacts"]["email"]  # после принятия контакты раскрыты
    assert "T" in data["accepted_at"]  # даты — ISO 8601

    app_id = sql_sync(
        "SELECT a.id FROM applications a JOIN vacancies v ON v.id = a.vacancy_id "
        "WHERE v.company_id = 1 ORDER BY a.id LIMIT 1"
    )[0][0]
    run_db(lambda s: notify_application_created(s, app_id))
    assert len(receiver.requests) == 2
    second = json.loads(receiver.requests[1]["body"])
    assert receiver.requests[1]["path"] == "/hooks/fsp/apps"
    assert second["event"] == "application.created" and second["data"]["application_id"] == app_id
    statuses = sql_sync(
        "SELECT status FROM webhook_deliveries WHERE endpoint_id = :e", {"e": only_apps["id"]}
    )
    assert statuses == [("delivered",)]
    # события другой компании сюда не попадают
    run_db(lambda s: notify_invitation_accepted(s, 11))  # приглашение компании 2
    assert len(receiver.requests) == 2


def test_retry_then_delivered_then_failed(client: TestClient, receiver: Receiver) -> None:
    hook = add_webhook(client, receiver.url, ["invitation.accepted"])
    receiver.codes = [500]
    run_db(lambda s: notify_invitation_accepted(s, 8))
    row = sql_sync(
        "SELECT status, attempts, last_status_code, next_attempt_at > now() FROM webhook_deliveries"
    )
    assert row == [("pending", 1, 500, True)]
    # до срока повтора ничего не уходит
    assert run_db(lambda s: deliver_pending(s)) == {"attempted": 0, "delivered": 0}
    later = now_msk() + timedelta(hours=1)
    assert run_db(lambda s: deliver_pending(s, later)) == {"attempted": 1, "delivered": 1}
    assert sql_sync("SELECT status, attempts FROM webhook_deliveries") == [("delivered", 2)]
    assert len(receiver.requests) == 2
    assert receiver.requests[0]["body"] == receiver.requests[1]["body"]  # то же событие

    # адрес всегда отвечает 503 — после всех попыток статус failed
    max_attempts = get_integration_settings().webhook_max_attempts
    receiver.codes = [503] * (max_attempts + 2)
    client.post(f"/api/companies/my/webhooks/{hook['id']}/ping", headers=RECRUITER)
    for step in range(max_attempts):
        run_db(partial(deliver_later, days=step + 1))
    ping = sql_sync("SELECT status, attempts FROM webhook_deliveries WHERE event = 'ping'")
    assert ping == [("failed", max_attempts)]


def test_unreachable_url_is_retried(client: TestClient) -> None:
    hook = add_webhook(client, "http://127.0.0.1:9/nowhere", ["invitation.accepted"])
    res = client.post(f"/api/companies/my/webhooks/{hook['id']}/ping", headers=RECRUITER).json()
    assert res["status"] == "pending" and res["last_error"] and res["last_status_code"] is None


def test_webhook_validation_and_access(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    bad = client.post(
        "/api/companies/my/webhooks",
        json={"url": "ftp://x.example.com", "events": ["ping"]},
        headers=RECRUITER,
    )
    assert bad.status_code == 422
    bad_url = client.post(
        "/api/companies/my/webhooks",
        json={"url": "ftp://x.example.com/h", "events": ["application.created"]},
        headers=RECRUITER,
    )
    assert bad_url.status_code == 422 and bad_url.json()["code"] == "invalid_webhook_url"
    monkeypatch.setattr(get_integration_settings(), "allow_private_urls", False)
    private = client.post(
        "/api/companies/my/webhooks",
        json={"url": "http://127.0.0.1:8000/h", "events": ["application.created"]},
        headers=RECRUITER,
    )
    assert private.status_code == 422 and private.json()["code"] == "invalid_webhook_url"
    monkeypatch.setattr(get_integration_settings(), "allow_private_urls", True)
    assert client.get("/api/companies/my/webhooks", headers=RECRUITER_NOT_ADMIN).status_code == 403
    assert client.get("/api/companies/my/webhooks", headers=CANDIDATE).status_code == 403
    assert client.get("/api/companies/my/webhooks", headers=ADMIN).status_code == 403
    hook = add_webhook(client, "https://ats.example.com/hooks", ["application.created"])
    assert (
        client.delete(f"/api/companies/my/webhooks/{hook['id']}", headers=RECRUITER_C2).status_code
        == 404
    )
    assert (
        client.delete(f"/api/companies/my/webhooks/{hook['id']}", headers=RECRUITER).status_code
        == 204
    )
    assert client.get("/api/companies/my/webhooks", headers=RECRUITER).json() == []


def test_short_body_strips_html() -> None:
    page = (
        "<!doctype html><html><head><title>405 Method Not Allowed</title>"
        "<style>body{color:red}</style></head><body><h1>Method Not Allowed</h1></body></html>"
    )
    assert short_body(page) == "405 Method Not Allowed"
    assert short_body("<p>Нет &amp; <b>доступа</b></p>") == "Нет & доступа"
    assert short_body('  {"detail":   "bad"}\n') == '{"detail": "bad"}'
    long = short_body("x" * 500)
    assert len(long) == 120 and long.endswith("…")
    assert short_body("") == ""
