"""Общие помощники тестов авторизации (трек 2a). Тестов в модуле нет.

Тесты ходят в настоящую БД (DATABASE_URL) через общий `client`; письма перехватываются
подменой `app.core.email.send_email`. Пользователи тестов — с почтой `w2a-test-…@example.com`,
после модуля удаляются.
"""

import asyncio
import re
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core import email as email_module
from app.core.config import get_settings

TEST_EMAIL_PREFIX = "w2a-test-"
PASSWORD = "S3cure-pass-1"


def new_email() -> str:
    return f"{TEST_EMAIL_PREFIX}{uuid.uuid4().hex[:12]}@example.com"


def db_exec(sql: str, params: dict[str, Any] | None = None) -> list[Any]:
    """Выполнить SQL в тестовой БД отдельным подключением (свой event loop, без пула)."""

    async def run() -> list[Any]:
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                result = await conn.execute(text(sql), params or {})
                return list(result.all()) if result.returns_rows else []
        finally:
            await engine.dispose()

    return asyncio.run(run())


def cleanup_test_users() -> None:
    like = {"p": f"{TEST_EMAIL_PREFIX}%"}
    db_exec(
        "DELETE FROM refresh_sessions WHERE user_id IN (SELECT id FROM users WHERE email LIKE :p)",
        like,
    )
    db_exec("DELETE FROM auth_throttle_events WHERE key LIKE :p", like)
    db_exec("DELETE FROM users WHERE email LIKE :p", like)
    db_exec("DELETE FROM companies WHERE contact_email LIKE :p", like)


class Outbox:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    def __call__(self, to: str, subject: str, text: str, html: str | None = None) -> None:
        self.messages.append({"to": to, "subject": subject, "text": text, "html": html or ""})

    def for_(self, address: str) -> list[dict[str, str]]:
        return [m for m in self.messages if m["to"] == address]

    def last_token(self, address: str) -> str:
        messages = self.for_(address)
        assert messages, f"письмо на {address} не отправлено"
        return token_from_text(messages[-1]["text"])


def token_from_text(body: str) -> str:
    match = re.search(r"token=([A-Za-z0-9_\-]+)", body)
    assert match, body
    return match.group(1)


@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> Outbox:
    box = Outbox()
    monkeypatch.setattr(email_module, "send_email", box)
    return box


@pytest.fixture
def api(client: TestClient) -> Iterator[TestClient]:
    """Общий клиент с чистыми cookie до и после теста."""
    client.cookies.clear()
    yield client
    client.cookies.clear()


@pytest.fixture(scope="module", autouse=True)
def _cleanup_module() -> Iterator[None]:
    cleanup_test_users()
    yield
    cleanup_test_users()


def register(
    client: TestClient, email: str, role: str = "candidate", **extra: Any
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "email": email,
        "password": PASSWORD,
        "full_name": "Тест Тестов",
        "role": role,
        "consent_processing": True,
        "consent_version": "2026-10-01",
        **extra,
    }
    response = client.post("/api/auth/register", json=body)
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


def verified_user(client: TestClient, outbox: Outbox, role: str = "candidate") -> str:
    """Зарегистрировать и подтвердить пользователя; вернуть почту."""
    email = new_email()
    extra = {"company": {"name": "ООО «Тест»"}} if role == "recruiter" else {}
    register(client, email, role, **extra)
    response = client.post("/api/auth/verify-email", json={"token": outbox.last_token(email)})
    assert response.status_code == 200, response.text
    return email


def login(client: TestClient, email: str, password: str = PASSWORD) -> Any:
    return client.post("/api/auth/login", json={"email": email, "password": password})


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
