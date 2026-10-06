"""Запись в журнал действий (audit_log). Коммит — за вызывающим."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import AuditLog
from app.catalog.clock import now_msk
from app.core.security import CurrentUser


async def write_audit(
    session: AsyncSession,
    actor: CurrentUser | None,
    action: str,
    target_type: str,
    target_id: int | None,
    summary: str,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        at=now_msk(),
        actor_user_id=actor.user_id if actor else None,
        actor_role=str(actor.role) if actor else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        summary=summary,
        details=details or {},
    )
    session.add(entry)
    await session.flush()
    return entry
