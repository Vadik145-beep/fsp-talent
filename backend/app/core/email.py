"""Отправка писем по SMTP (в разработке — Mailpit, на сервере — SMTP из .env).

`smtplib` блокирующий, поэтому из async-кода вызываем `send_email_async` — он уводит
отправку в отдельный поток. Тесты подменяют `send_email` (monkeypatch) — `send_email_async`
ищет её в модуле при каждом вызове.
"""

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger("app.email")


def build_message(to: str, subject: str, text: str, html: str | None = None) -> EmailMessage:
    settings = get_settings()
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    if html is not None:
        message.add_alternative(html, subtype="html")
    return message


def send_email(to: str, subject: str, text: str, html: str | None = None) -> None:
    """Отправить письмо синхронно. Ошибки SMTP пробрасываются вызывающему."""
    settings = get_settings()
    message = build_message(to, subject, text, html)
    with smtplib.SMTP(
        settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_sec
    ) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)


async def send_email_async(to: str, subject: str, text: str, html: str | None = None) -> bool:
    """Отправить письмо в отдельном потоке. False — не отправилось (ошибка уже в логе).

    Регистрация и сброс пароля не должны падать из-за недоступного SMTP: пользователь
    может запросить письмо повторно.
    """
    try:
        await asyncio.to_thread(send_email, to, subject, text, html)
    except (OSError, smtplib.SMTPException) as exc:
        logger.error("Письмо на %s не отправлено: %s", to, exc)
        return False
    return True
