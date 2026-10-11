"""Исходящие вебхуки в ATS работодателя (T12.2).

Схема «outbox»: событие сначала записывается в `webhook_deliveries` (в той же транзакции, что
и само действие), потом отправляется POST-запросом на адрес компании. Не дошло (сеть, не 2xx) —
повтор с паузами 1 мин → 5 мин → 30 мин → 2 ч, всего `INTEGRATIONS_WEBHOOK_MAX_ATTEMPTS`
попыток, затем статус `failed`. Повторы шлёт `deliver_pending` (`python -m app.integrations`).

Запрос: тело — JSON `{"id", "event", "company_id", "created_at", "data"}`, заголовки
`X-FSP-Event`, `X-FSP-Delivery`, `X-FSP-Timestamp` и
`X-FSP-Signature: sha256=<hex HMAC-SHA256(secret, "<timestamp>." + тело)>`.
Получатель пересчитывает подпись своим секретом и сверяет время (защита от повтора).

Как встроить в чужой модуль (после коммита основного действия):
    from app.integrations.webhooks import notify_invitation_accepted, notify_application_created
    await notify_invitation_accepted(session, inv.id)     # invitations.accept
    await notify_application_created(session, app.id)     # vacancies.apply
Ошибки вебхука не ломают основное действие — только пишутся в лог.
"""

import hashlib
import hmac
import html
import json
import logging
import re
import time
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates.repository import CandidateDb
from app.candidates.service import to_contacts
from app.catalog.clock import as_msk, now_msk
from app.integrations.models import WebhookDelivery, WebhookEndpoint
from app.integrations.settings import get_integration_settings
from app.invitations.models import Invitation
from app.vacancies.models import Application, Vacancy

logger = logging.getLogger("app.integrations")

EVENT_INVITATION_ACCEPTED = "invitation.accepted"
EVENT_APPLICATION_CREATED = "application.created"
EVENT_PING = "ping"
EVENTS = {
    EVENT_INVITATION_ACCEPTED: "Кандидат принял приглашение (контакты раскрыты)",
    EVENT_APPLICATION_CREATED: "Новый отклик на вакансию",
}

PENDING, DELIVERED, FAILED = "pending", "delivered", "failed"


_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


def short_body(text: str, limit: int = 120) -> str:
    """Тело ответа ATS для журнала доставок: без HTML-тегов, в одну строку, не длиннее limit.

    У HTML-страницы ошибки (nginx, фреймворки) берём заголовок <title>, иначе — текст без тегов.
    """
    if "<" in text and ">" in text:
        title = _TITLE_RE.search(text)
        text = title.group(1) if title else _TAG_RE.sub(" ", _SCRIPT_RE.sub(" ", text))
    text = " ".join(html.unescape(text).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def sign(secret: str, timestamp: str, body: bytes) -> str:
    """Подпись тела вебхука: `sha256=<hex>` от `<timestamp>.<body>`."""
    mac = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256)
    return "sha256=" + mac.hexdigest()


def verify(secret: str, timestamp: str, body: bytes, signature: str) -> bool:
    """Проверка подписи на стороне получателя (пример для документации и тестов)."""
    return hmac.compare_digest(sign(secret, timestamp, body), signature)


def _default(value: Any) -> str:
    return value.isoformat() if isinstance(value, datetime | date) else str(value)


def _json(payload: dict[str, Any]) -> bytes:
    """Канонический JSON: ключи по алфавиту — тело повтора байт в байт как у первой попытки."""
    return json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=_default
    ).encode()


async def enqueue(
    session: AsyncSession,
    company_id: int,
    event: str,
    data: dict[str, Any],
    *,
    endpoint_ids: Sequence[int] | None = None,
) -> list[WebhookDelivery]:
    """Записать событие в очередь доставки для подходящих адресов компании. Без коммита."""
    stmt = select(WebhookEndpoint).where(
        WebhookEndpoint.company_id == company_id, WebhookEndpoint.active.is_(True)
    )
    if endpoint_ids is not None:
        stmt = stmt.where(WebhookEndpoint.id.in_(endpoint_ids))
    else:
        stmt = stmt.where(WebhookEndpoint.events.any(event))  # type: ignore[arg-type]
    endpoints = (await session.scalars(stmt)).all()
    now = now_msk()
    deliveries = []
    for endpoint in endpoints:
        delivery = WebhookDelivery(
            endpoint_id=endpoint.id,
            event=event,
            payload={},
            status=PENDING,
            attempts=0,
            next_attempt_at=now,
            created_at=now,
        )
        session.add(delivery)
        await session.flush()
        delivery.payload = {
            "id": delivery.id,
            "event": event,
            "company_id": company_id,
            "created_at": now.isoformat(),
            "data": json.loads(_json(data)),
        }
        deliveries.append(delivery)
    await session.flush()
    return deliveries


def _backoff(attempts: int) -> timedelta:
    pauses = get_integration_settings().webhook_backoff_sec or [60]
    return timedelta(seconds=pauses[min(attempts - 1, len(pauses) - 1)])


async def deliver(
    session: AsyncSession,
    delivery: WebhookDelivery,
    client: httpx.AsyncClient | None = None,
) -> bool:
    """Одна попытка доставки. Обновляет статус, без коммита. True — получатель ответил 2xx."""
    settings = get_integration_settings()
    endpoint = await session.get(WebhookEndpoint, delivery.endpoint_id)
    if endpoint is None or not endpoint.active:
        delivery.status = FAILED
        delivery.last_error = "Адрес вебхука удалён или выключен"
        delivery.next_attempt_at = None
        return False
    body = _json(delivery.payload)
    timestamp = str(int(time.time()))
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "fsp-talent-webhooks/1.0",
        "X-FSP-Event": delivery.event,
        "X-FSP-Delivery": str(delivery.id),
        "X-FSP-Timestamp": timestamp,
        "X-FSP-Signature": sign(endpoint.secret, timestamp, body),
    }
    own_client = client is None
    http = client or httpx.AsyncClient(timeout=settings.webhook_timeout_sec)
    ok, code, error = False, None, None
    try:
        response = await http.post(endpoint.url, content=body, headers=headers)
        code = response.status_code
        ok = 200 <= code < 300
        if not ok:
            detail = short_body(response.text)
            error = f"HTTP {code}: {detail}" if detail else f"HTTP {code}"
    except httpx.HTTPError as exc:
        error = f"{type(exc).__name__}: {exc}"[:500]
    finally:
        if own_client:
            await http.aclose()
    now = now_msk()
    delivery.attempts += 1
    delivery.last_status_code = code
    delivery.last_error = error
    if ok:
        delivery.status = DELIVERED
        delivery.delivered_at = now
        delivery.next_attempt_at = None
    elif delivery.attempts >= settings.webhook_max_attempts:
        delivery.status = FAILED
        delivery.next_attempt_at = None
    else:
        delivery.status = PENDING
        delivery.next_attempt_at = now + _backoff(delivery.attempts)
    if not ok:
        logger.warning(
            "webhook_failed",
            extra={"delivery_id": delivery.id, "url": endpoint.url, "error": error},
        )
    await session.flush()
    return ok


async def deliver_pending(
    session: AsyncSession, now: datetime | None = None, limit: int = 100
) -> dict[str, int]:
    """Отправить все доставки, у которых подошло время повтора. С коммитом."""
    due = (
        await session.scalars(
            select(WebhookDelivery)
            .where(
                WebhookDelivery.status == PENDING,
                WebhookDelivery.next_attempt_at <= (now or now_msk()),
            )
            .order_by(WebhookDelivery.id)
            .limit(limit)
        )
    ).all()
    delivered = 0
    async with httpx.AsyncClient(timeout=get_integration_settings().webhook_timeout_sec) as http:
        for delivery in due:
            delivered += await deliver(session, delivery, http)
    await session.commit()
    return {"attempted": len(due), "delivered": delivered}


async def emit(
    session: AsyncSession,
    company_id: int,
    event: str,
    data: dict[str, Any],
    *,
    endpoint_ids: Sequence[int] | None = None,
) -> list[WebhookDelivery]:
    """Записать событие и сразу попытаться доставить (неудачные уйдут в повтор). С коммитом."""
    deliveries = await enqueue(session, company_id, event, data, endpoint_ids=endpoint_ids)
    await session.commit()
    if deliveries:
        async with httpx.AsyncClient(
            timeout=get_integration_settings().webhook_timeout_sec
        ) as http:
            for delivery in deliveries:
                await deliver(session, delivery, http)
        await session.commit()
    return deliveries


# ---------- данные событий ----------


def _candidate_block(cand: dict[str, Any], *, with_contacts: bool) -> dict[str, Any]:
    block = {
        "id": cand["id"],
        "pseudonym": cand["pseudonym"],
        "specialization": cand.get("specialization"),
        "grade": cand.get("grade"),
        "category": cand.get("category"),
        "category_label": cand.get("category_label"),
        "stack": cand.get("stack") or [],
        "fsp_id": cand.get("fsp_id"),
    }
    if with_contacts:
        block["contacts"] = to_contacts(cand)
    return block


async def invitation_accepted_data(session: AsyncSession, invitation_id: int) -> dict[str, Any]:
    inv = await session.get(Invitation, invitation_id)
    if inv is None:
        raise LookupError(f"invitation {invitation_id}")
    cand = await CandidateDb(session).record(inv.candidate_id) or {}
    return {
        "invitation_id": inv.id,
        "status": inv.status,
        "accepted_at": as_msk(inv.responded_at),
        "recruiter_id": inv.recruiter_id,
        "need_id": inv.need_id,
        "vacancy_id": inv.vacancy_id,
        "category": inv.category,
        "salary_from": inv.salary_from,
        "salary_to": inv.salary_to,
        "candidate": _candidate_block(cand, with_contacts=True) if cand else None,
    }


async def application_created_data(session: AsyncSession, application_id: int) -> dict[str, Any]:
    row = (
        await session.execute(
            select(Application, Vacancy)
            .join(Vacancy, Vacancy.id == Application.vacancy_id)
            .where(Application.id == application_id)
        )
    ).first()
    if row is None:
        raise LookupError(f"application {application_id}")
    app, vacancy = row
    cand = await CandidateDb(session).record(app.candidate_id) or {}
    return {
        "application_id": app.id,
        "vacancy_id": vacancy.id,
        "vacancy_title": vacancy.title,
        "cover_letter": app.cover_letter,
        "created_at": as_msk(app.created_at),
        # контакты открываются сразу после отклика [ТЗ 2.1]
        "candidate": _candidate_block(cand, with_contacts=True) if cand else None,
        "company_id": vacancy.company_id,
    }


async def notify_invitation_accepted(session: AsyncSession, invitation_id: int) -> None:
    """Вебхук «приглашение принято». Вызывать после коммита принятия; не бросает исключений."""
    try:
        inv = await session.get(Invitation, invitation_id)
        if inv is not None:
            data = await invitation_accepted_data(session, invitation_id)
            await emit(session, inv.company_id, EVENT_INVITATION_ACCEPTED, data)
    except Exception:
        logger.exception("webhook_emit_failed", extra={"invitation_id": invitation_id})
        await session.rollback()


async def notify_application_created(session: AsyncSession, application_id: int) -> None:
    """Вебхук «новый отклик». Вызывать после коммита отклика; не бросает исключений."""
    try:
        data = await application_created_data(session, application_id)
        await emit(session, int(data.pop("company_id")), EVENT_APPLICATION_CREATED, data)
    except Exception:
        logger.exception("webhook_emit_failed", extra={"application_id": application_id})
        await session.rollback()
