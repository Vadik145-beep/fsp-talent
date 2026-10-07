"""API-токены компании, адреса вебхуков и выгрузка данных в ATS (T12.2).

Управлять токенами и вебхуками может только администратор компании. Выпуск и отзыв токена,
добавление и удаление вебхука пишутся в журнал (audit_log).
"""

import hashlib
import ipaddress
import secrets
import socket
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.audit import write_audit
from app.candidates.repository import CandidateDb
from app.candidates.service import to_contacts
from app.catalog.clock import as_msk, now_msk
from app.common.fixtures import Record
from app.companies.antifraud import company_blocked_error
from app.companies.models import Company, Recruiter
from app.core.errors import AppError, not_found
from app.core.security import CurrentUser
from app.integrations.models import CompanyApiToken, WebhookDelivery, WebhookEndpoint
from app.integrations.schemas import ApiTokenCreate, WebhookCreate
from app.integrations.settings import get_integration_settings
from app.integrations.webhooks import EVENT_PING, emit
from app.invitations.models import Invitation
from app.vacancies.models import Application, Vacancy

TOKEN_PREFIX = "fspt_"


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def token_record(t: CompanyApiToken) -> Record:
    return {
        "id": t.id,
        "name": t.name,
        "token_prefix": t.token_prefix,
        "active": t.revoked_at is None,
        "created_at": as_msk(t.created_at),
        "last_used_at": as_msk(t.last_used_at),
        "revoked_at": as_msk(t.revoked_at),
    }


def webhook_record(w: WebhookEndpoint) -> Record:
    return {
        "id": w.id,
        "url": w.url,
        "events": list(w.events or []),
        "active": w.active,
        "created_at": as_msk(w.created_at),
    }


def delivery_record(d: WebhookDelivery) -> Record:
    return {
        "id": d.id,
        "endpoint_id": d.endpoint_id,
        "event": d.event,
        "status": d.status,
        "attempts": d.attempts,
        "last_status_code": d.last_status_code,
        "last_error": d.last_error,
        "next_attempt_at": as_msk(d.next_attempt_at),
        "delivered_at": as_msk(d.delivered_at),
        "created_at": as_msk(d.created_at),
        "payload": d.payload,
    }


def _is_private_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False  # не резолвится — доставка просто не удастся
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True
    return False


def validate_webhook_url(url: str) -> str:
    """http(s) и хост; на проде (`INTEGRATIONS_ALLOW_PRIVATE_URLS=false`) — не внутренняя сеть."""
    url = url.strip()
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise AppError(
            422,
            "invalid_webhook_url",
            "Адрес должен начинаться с http:// или https://",
            {"fields": {"url": "Укажите адрес вида https://ats.example.com/hooks"}},
        )
    if not get_integration_settings().allow_private_urls and _is_private_host(parts.hostname):
        raise AppError(
            422,
            "invalid_webhook_url",
            "Адреса внутренней сети и localhost запрещены",
            {"fields": {"url": "Нужен публичный адрес"}},
        )
    return url


class IntegrationService:
    def __init__(self, session: AsyncSession, user: CurrentUser) -> None:
        self.session = session
        self.user = user

    async def _company_admin(self) -> int:
        """id компании, если пользователь — её администратор; иначе 403."""
        recruiter = (
            await self.session.get(Recruiter, self.user.recruiter_id)
            if self.user.recruiter_id
            else None
        )
        if recruiter is None or not recruiter.is_company_admin:
            raise AppError(403, "forbidden", "Интеграциями управляет только администратор компании")
        return recruiter.company_id

    # ---------- токены ----------

    async def tokens(self) -> list[Record]:
        company_id = await self._company_admin()
        rows = await self.session.scalars(
            select(CompanyApiToken)
            .where(CompanyApiToken.company_id == company_id)
            .order_by(CompanyApiToken.id.desc())
        )
        return [token_record(t) for t in rows.all()]

    async def issue_token(self, body: ApiTokenCreate) -> Record:
        company_id = await self._company_admin()
        raw = TOKEN_PREFIX + secrets.token_urlsafe(32)
        token = CompanyApiToken(
            company_id=company_id,
            name=body.name.strip(),
            token_prefix=raw[:12],
            token_hash=hash_token(raw),
            created_by=self.user.user_id,
            created_at=now_msk(),
        )
        self.session.add(token)
        await self.session.flush()
        await write_audit(
            self.session,
            self.user,
            "api_token_issued",
            "company",
            company_id,
            f"Выпущен API-токен «{token.name}» ({token.token_prefix}…)",
            {"token_id": token.id},
        )
        await self.session.commit()
        return {**token_record(token), "token": raw}

    async def revoke_token(self, token_id: int) -> None:
        company_id = await self._company_admin()
        token = await self.session.get(CompanyApiToken, token_id)
        if token is None or token.company_id != company_id:
            raise not_found("api_token", token_id)
        if token.revoked_at is None:
            token.revoked_at = now_msk()
            await write_audit(
                self.session,
                self.user,
                "api_token_revoked",
                "company",
                company_id,
                f"Отозван API-токен «{token.name}» ({token.token_prefix}…)",
                {"token_id": token.id},
            )
            await self.session.commit()

    # ---------- вебхуки ----------

    async def webhooks(self) -> list[Record]:
        company_id = await self._company_admin()
        rows = await self.session.scalars(
            select(WebhookEndpoint)
            .where(WebhookEndpoint.company_id == company_id, WebhookEndpoint.active.is_(True))
            .order_by(WebhookEndpoint.id)
        )
        return [webhook_record(w) for w in rows.all()]

    async def create_webhook(self, body: WebhookCreate) -> Record:
        company_id = await self._company_admin()
        url = validate_webhook_url(body.url)
        secret = body.secret or secrets.token_hex(24)
        endpoint = WebhookEndpoint(
            company_id=company_id,
            url=url,
            secret=secret,
            events=sorted(set(body.events)),
            active=True,
            created_by=self.user.user_id,
            created_at=now_msk(),
        )
        self.session.add(endpoint)
        await self.session.flush()
        await write_audit(
            self.session,
            self.user,
            "webhook_created",
            "company",
            company_id,
            f"Добавлен вебхук {url}",
            {"webhook_id": endpoint.id, "events": endpoint.events},
        )
        await self.session.commit()
        return {**webhook_record(endpoint), "secret": secret}

    async def _own_webhook(self, webhook_id: int) -> WebhookEndpoint:
        company_id = await self._company_admin()
        endpoint = await self.session.get(WebhookEndpoint, webhook_id)
        if endpoint is None or endpoint.company_id != company_id or not endpoint.active:
            raise not_found("webhook", webhook_id)
        return endpoint

    async def delete_webhook(self, webhook_id: int) -> None:
        endpoint = await self._own_webhook(webhook_id)
        endpoint.active = False  # история доставок остаётся
        await write_audit(
            self.session,
            self.user,
            "webhook_deleted",
            "company",
            endpoint.company_id,
            f"Удалён вебхук {endpoint.url}",
            {"webhook_id": endpoint.id},
        )
        await self.session.commit()

    async def ping_webhook(self, webhook_id: int) -> Record:
        endpoint = await self._own_webhook(webhook_id)
        data = {"message": "Проверка адреса вебхука fsp-talent"}
        deliveries = await emit(
            self.session, endpoint.company_id, EVENT_PING, data, endpoint_ids=[endpoint.id]
        )
        return delivery_record(deliveries[0])

    async def deliveries(self, webhook_id: int, limit: int) -> list[Record]:
        endpoint = await self._own_webhook(webhook_id)
        rows = await self.session.scalars(
            select(WebhookDelivery)
            .where(WebhookDelivery.endpoint_id == endpoint.id)
            .order_by(WebhookDelivery.id.desc())
            .limit(limit)
        )
        return [delivery_record(d) for d in rows.all()]


# ---------- выгрузка по API-токену ----------


async def company_by_token(session: AsyncSession, raw: str | None) -> Company:
    """Компания по API-токену; 401 — нет/неверный/отозван, 403 — компания заблокирована."""
    if not raw or not raw.startswith(TOKEN_PREFIX):
        raise AppError(401, "invalid_api_token", "Нужен API-токен компании в заголовке X-Api-Token")
    token = await session.scalar(
        select(CompanyApiToken).where(CompanyApiToken.token_hash == hash_token(raw.strip()))
    )
    if token is None or token.revoked_at is not None:
        raise AppError(401, "invalid_api_token", "API-токен не найден или отозван")
    company = await session.get(Company, token.company_id)
    if company is None:
        raise AppError(401, "invalid_api_token", "API-токен не найден или отозван")
    if company.blocked:
        raise company_blocked_error(company.id)
    token.last_used_at = now_msk()
    await session.commit()
    return company


async def export_company(
    session: AsyncSession, company: Company, since: datetime | None
) -> dict[str, Any]:
    """Вакансии, приглашения и отклики компании (изменённые после `since`, если задан)."""
    vac_stmt = select(Vacancy).where(Vacancy.company_id == company.id).order_by(Vacancy.id)
    inv_stmt = select(Invitation).where(Invitation.company_id == company.id).order_by(Invitation.id)
    app_stmt = (
        select(Application, Vacancy.title)
        .join(Vacancy, Vacancy.id == Application.vacancy_id)
        .where(Vacancy.company_id == company.id)
        .order_by(Application.id)
    )
    if since is not None:
        vac_stmt = vac_stmt.where(or_(Vacancy.created_at >= since, Vacancy.published_at >= since))
        inv_stmt = inv_stmt.where(
            or_(Invitation.created_at >= since, Invitation.responded_at >= since)
        )
        app_stmt = app_stmt.where(
            or_(Application.created_at >= since, Application.updated_at >= since)
        )
    vacancies = (await session.scalars(vac_stmt)).all()
    invitations = (await session.scalars(inv_stmt)).all()
    applications = (await session.execute(app_stmt)).all()
    ids = {i.candidate_id for i in invitations} | {a.candidate_id for a, _ in applications}
    cands = await CandidateDb(session).records(list(ids))

    def candidate(cid: int, contacts: bool) -> dict[str, Any] | None:
        cand = cands.get(cid)
        if cand is None:
            return None
        block = {
            "id": cid,
            "pseudonym": cand["pseudonym"],
            "category": cand.get("category"),
            "stack": cand.get("stack") or [],
        }
        if contacts:
            block["contacts"] = to_contacts(cand)
        return block

    return {
        "company": {"id": company.id, "name": company.name, "inn": company.inn},
        "generated_at": now_msk(),
        "since": since,
        "vacancies": [
            {
                "id": v.id,
                "title": v.title,
                "category": v.category,
                "status": v.status,
                "salary_from": v.salary_from,
                "salary_to": v.salary_to,
                "published_at": as_msk(v.published_at),
            }
            for v in vacancies
        ],
        "invitations": [
            {
                "id": i.id,
                "status": i.status,
                "category": i.category,
                "need_id": i.need_id,
                "vacancy_id": i.vacancy_id,
                "salary_from": i.salary_from,
                "salary_to": i.salary_to,
                "created_at": as_msk(i.created_at),
                "responded_at": as_msk(i.responded_at),
                "decline_reason": i.decline_reason,
                "candidate": candidate(i.candidate_id, i.status == "accepted"),
            }
            for i in invitations
        ],
        "applications": [
            {
                "id": a.id,
                "vacancy_id": a.vacancy_id,
                "vacancy_title": title,
                "status": a.status,
                "created_at": as_msk(a.created_at),
                "candidate": candidate(a.candidate_id, True),
            }
            for a, title in applications
        ],
    }
