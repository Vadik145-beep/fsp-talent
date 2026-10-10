"""Письма: отправка через SMTP и интеграционный тест на настоящем Mailpit.

Интеграционный тест пропускается, если Mailpit недоступен (адрес — MAILPIT_URL / SMTP из
настроек; локально: SMTP localhost:11025, API http://localhost:18025).
"""

import asyncio
import os
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core import email as email_module
from app.core.config import get_settings
from tests.test_auth_helpers import (
    _cleanup_module,
    api,
    login,
    new_email,
    register,
    token_from_text,
)

__all__ = ["_cleanup_module", "api"]

MAILPIT_URL = os.environ.get("MAILPIT_URL", "http://localhost:18025")
MAILPIT_SMTP_HOST = os.environ.get("MAILPIT_SMTP_HOST", "localhost")
MAILPIT_SMTP_PORT = int(os.environ.get("MAILPIT_SMTP_PORT", "11025"))


def _mailpit_available() -> bool:
    try:
        return httpx.get(f"{MAILPIT_URL}/api/v1/messages", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def test_smtp_failure_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "smtp_host", "127.0.0.1")
    monkeypatch.setattr(get_settings(), "smtp_port", 1)  # никто не слушает
    monkeypatch.setattr(get_settings(), "smtp_timeout_sec", 2)
    assert asyncio.run(email_module.send_email_async("a@example.com", "s", "t")) is False


def test_build_message_has_text_and_html(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "smtp_from", "")
    monkeypatch.setattr(get_settings(), "smtp_user", "fsp.talent@yandex.ru")
    message = email_module.build_message("a@example.com", "Тема", "текст", "<p>html</p>")
    assert message["To"] == "a@example.com"
    # адрес отправителя = логин SMTP (Яндекс и Mail.ru иначе не примут), имя — название сайта
    assert message["From"].addresses[0].addr_spec == "fsp.talent@yandex.ru"
    assert message["From"].addresses[0].display_name == "ФСП · Таланты"
    assert message["Date"] and message["Message-ID"].endswith("@yandex.ru>")
    assert {part.get_content_type() for part in message.iter_parts()} == {
        "text/plain",
        "text/html",
    }


def test_html_built_from_text_when_not_given() -> None:
    text = (
        "Здравствуйте!\n\nПринять: https://stand.example/candidate/invitations/7.\n— ФСП · Таланты"
    )
    message = email_module.build_message("a@example.com", "Тема", text)
    html = message.get_body(("html",)).get_content()
    assert '<a href="https://stand.example/candidate/invitations/7"' in html  # точка не в ссылке
    assert "ФСП · Таланты" in html and "#402FFF" in html
    assert "— ФСП · Таланты" not in html  # подпись заменена шапкой и подвалом
    assert message.get_body(("plain",)).get_content().strip() == text


def test_html_escapes_user_text() -> None:
    html = email_module.text_to_html("<script>alert(1)</script>")
    assert "<script>" not in html and "&lt;script&gt;" in html


@pytest.mark.skipif(not _mailpit_available(), reason="Mailpit недоступен")
def test_registration_email_arrives_in_mailpit(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "smtp_host", MAILPIT_SMTP_HOST)
    monkeypatch.setattr(get_settings(), "smtp_port", MAILPIT_SMTP_PORT)
    email = new_email()
    register(api, email)

    message = None
    for _ in range(20):
        found = httpx.get(
            f"{MAILPIT_URL}/api/v1/search", params={"query": f"to:{email}"}, timeout=5
        ).json()
        if found["messages"]:
            message = found["messages"][0]
            break
        time.sleep(0.25)
    assert message is not None, "письмо не пришло в Mailpit"
    assert message["Subject"] == "Подтвердите почту"
    full = httpx.get(f"{MAILPIT_URL}/api/v1/message/{message['ID']}", timeout=5).json()
    link_prefix = f"{get_settings().public_frontend_url}/verify-email?token="
    assert link_prefix in full["Text"]

    token = token_from_text(full["Text"])
    assert api.post("/api/auth/verify-email", json={"token": token}).status_code == 200
    assert login(api, email).status_code == 200
