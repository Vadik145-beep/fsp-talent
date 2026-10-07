"""Антифрод работодателя (E12, T10.6): блокировка компании и проверки для других модулей.

Заблокированная компания (админ подтвердил жалобу с блокировкой или заблокировал вручную):
- её рекрутеры не могут отправлять приглашения, публиковать вакансии, создавать задания
  и пользоваться API-токенами — ответ 403 `company_blocked`;
- её вакансии скрыты из ленты соискателя, её задания не раздаются.

Как встроить в чужой модуль:
    from app.companies.antifraud import ensure_company_active, active_company_ids
    await ensure_company_active(session, user.company_id)        # перед действием рекрутера
    stmt = stmt.where(Vacancy.company_id.in_(active_company_ids()))  # фильтр ленты
"""

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.audit import write_audit
from app.companies.models import Company
from app.core.errors import AppError
from app.core.security import CurrentUser

COMPANY_BLOCKED_MESSAGE = (
    "Компания заблокирована администратором платформы: отправлять приглашения, "
    "публиковать вакансии и задания нельзя. Напишите в поддержку ФСП."
)


def company_blocked_error(company_id: int) -> AppError:
    return AppError(403, "company_blocked", COMPANY_BLOCKED_MESSAGE, {"company_id": company_id})


async def is_company_blocked(session: AsyncSession, company_id: int) -> bool:
    blocked = await session.scalar(select(Company.blocked).where(Company.id == company_id))
    return bool(blocked)


async def ensure_company_active(session: AsyncSession, company_id: int | None) -> None:
    """403 `company_blocked`, если компания заблокирована. Нет компании — не наша проверка."""
    if company_id is not None and await is_company_blocked(session, company_id):
        raise company_blocked_error(company_id)


def active_company_ids() -> Select[tuple[int]]:
    """Подзапрос id незаблокированных компаний — для фильтров лент и раздачи."""
    return select(Company.id).where(Company.blocked.is_(False))


async def set_company_blocked(
    session: AsyncSession,
    company: Company,
    blocked: bool,
    actor: CurrentUser | None,
    reason: str | None = None,
    details: dict[str, object] | None = None,
) -> bool:
    """Заблокировать/разблокировать компанию с записью в журнал. Коммит — за вызывающим.

    Возвращает True, если состояние изменилось.
    """
    if company.blocked == blocked:
        return False
    company.blocked = blocked
    verb = "заблокирована" if blocked else "разблокирована"
    summary = f"Компания {verb}: {company.name}"
    if reason:
        summary += f" — {reason}"
    await write_audit(
        session,
        actor,
        "company_blocked" if blocked else "company_unblocked",
        "company",
        company.id,
        summary,
        dict(details or {}),
    )
    return True
