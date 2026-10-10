"""Отправка писем по SMTP (в разработке — Mailpit, на сервере — SMTP из .env).

`smtplib` блокирующий, поэтому из async-кода вызываем `send_email_async` — он уводит
отправку в отдельный поток. Тесты подменяют `send_email` (monkeypatch) — `send_email_async`
ищет её в модуле при каждом вызове.

Каждое письмо уходит в двух видах: текст и HTML в цветах ФСП. Если HTML не передан, он
собирается из текста: абзацы по пустой строке, ссылки становятся кликабельными.
"""

import asyncio
import logging
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from html import escape

from app.core.config import get_settings

logger = logging.getLogger("app.email")

DEFAULT_FROM = "noreply@fsp-talent.example.com"
URL_RE = re.compile(r"https?://[^\s<>\"]+[^\s<>\".,;:!?)»]")

# Брендбук ФСП: основной #402FFF, текст #1C1D22, фон #EDEDED
PRIMARY = "#402FFF"
INK = "#1C1D22"
MUTED = "#6B6C75"
BACKGROUND = "#EDEDED"
FONT = "Inter,Arial,Helvetica,sans-serif"


def sender_address() -> str:
    settings = get_settings()
    return settings.smtp_from or settings.smtp_user or DEFAULT_FROM


def _linkify(text: str) -> str:
    """Экранировать текст и сделать ссылки кликабельными."""
    out, pos = [], 0
    for m in URL_RE.finditer(text):
        out.append(escape(text[pos : m.start()]))
        url = escape(m.group(0))
        out.append(f'<a href="{url}" style="color:{PRIMARY}">{url}</a>')
        pos = m.end()
    out.append(escape(text[pos:]))
    return "".join(out).replace("\n", "<br>")


def layout_html(paragraphs: list[str], button: tuple[str, str] | None = None) -> str:
    """Письмо в цветах ФСП. `paragraphs` — обычный текст (экранируется здесь),
    `button` — (надпись, ссылка)."""
    body = "".join(
        f'<p style="margin:0 0 14px;line-height:1.5">{_linkify(p)}</p>' for p in paragraphs
    )
    if button:
        label, link = escape(button[0]), escape(button[1])
        body += (
            f'<p style="margin:22px 0"><a href="{link}" style="display:inline-block;'
            f"background:{PRIMARY};color:#ffffff;padding:12px 22px;border-radius:8px;"
            f'font-weight:600;text-decoration:none">{label}</a></p>'
            f'<p style="margin:0;color:{MUTED};font-size:13px;line-height:1.5">'
            f"Если кнопка не работает, откройте ссылку:<br>"
            f'<a href="{link}" style="color:{PRIMARY};word-break:break-all">{link}</a></p>'
        )
    return (
        f'<div style="background:{BACKGROUND};padding:24px 12px;font-family:{FONT};color:{INK}">'
        '<div style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:12px;'
        'overflow:hidden">'
        f'<div style="background:{PRIMARY};color:#ffffff;padding:16px 24px;font-weight:700;'
        'font-size:18px;letter-spacing:.3px">ФСП · Таланты</div>'
        f'<div style="padding:24px;font-size:15px">{body}</div>'
        f'<div style="padding:14px 24px;border-top:1px solid {BACKGROUND};color:{MUTED};'
        'font-size:12px">Платформа подбора IT-специалистов Федерации спортивного '
        "программирования. Письмо отправлено автоматически, отвечать на него не нужно.</div>"
        "</div></div>"
    )


def text_to_html(text: str) -> str:
    """HTML из текста письма: абзацы по пустой строке, подпись «— ФСП · Таланты» убираем
    (в HTML есть шапка и подвал)."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    paragraphs = [re.sub(r"\n?— ФСП · Таланты$", "", p).strip() for p in paragraphs]
    return layout_html([p for p in paragraphs if p])


def build_message(to: str, subject: str, text: str, html: str | None = None) -> EmailMessage:
    settings = get_settings()
    address = sender_address()
    message = EmailMessage()
    message["From"] = (
        formataddr((settings.smtp_from_name, address)) if settings.smtp_from_name else address
    )
    message["To"] = to
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=address.rsplit("@", 1)[-1])
    message.set_content(text)
    message.add_alternative(html if html is not None else text_to_html(text), subtype="html")
    return message


def _connect() -> smtplib.SMTP:
    settings = get_settings()
    if settings.smtp_ssl:
        return smtplib.SMTP_SSL(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout_sec,
            context=ssl.create_default_context(),
        )
    smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_sec)
    if settings.smtp_starttls:
        smtp.starttls(context=ssl.create_default_context())
    return smtp


def send_email(to: str, subject: str, text: str, html: str | None = None) -> None:
    """Отправить письмо синхронно. Ошибки SMTP пробрасываются вызывающему."""
    settings = get_settings()
    message = build_message(to, subject, text, html)
    with _connect() as smtp:
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
    logger.info("Письмо «%s» отправлено на %s", subject, to)
    return True
