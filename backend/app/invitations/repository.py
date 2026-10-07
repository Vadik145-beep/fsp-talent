"""Приглашения и журнал событий (БД). Выборки пакетные, коммит — за сервисом."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.candidates.models import CandidateProfile
from app.catalog.models import Category
from app.common.enums import ACTIVE_INVITATION_STATUSES, InvitationStatus
from app.companies.models import Company, Recruiter
from app.invitations.models import Invitation, InvitationEvent
from app.users.models import User

ACTIVE = [s.value for s in ACTIVE_INVITATION_STATUSES]

# Строка выборки: приглашение + название компании + ФИО рекрутера + подпись категории
InvitationRow = tuple[Invitation, str, str, str | None]


class InvitationDb:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---------- истечение срока (лениво, при чтении) ----------

    async def expire_overdue(self, now: datetime) -> list[int]:
        """Активные приглашения с истёкшим сроком → `expired` + событие (время = срок)."""
        rows = (
            await self.session.execute(
                update(Invitation)
                .where(Invitation.status.in_(ACTIVE), Invitation.expires_at < now)
                .values(status=InvitationStatus.expired.value)
                .returning(Invitation.id, Invitation.expires_at)
            )
        ).all()
        for inv_id, expires_at in rows:
            self.session.add(
                InvitationEvent(
                    invitation_id=inv_id, type="expired", at=expires_at, actor_role=None
                )
            )
        if rows:
            await self.session.flush()
        return [inv_id for inv_id, _ in rows]

    # ---------- чтение ----------

    def _select(self) -> Any:
        return (
            select(Invitation, Company.name, User.full_name, Category.label)
            .join(Company, Company.id == Invitation.company_id)
            .join(Recruiter, Recruiter.id == Invitation.recruiter_id)
            .join(User, User.id == Recruiter.user_id)
            .outerjoin(Category, Category.code == Invitation.category)
        )

    async def rows(self, *conditions: ColumnElement[bool]) -> list[InvitationRow]:
        stmt = (
            self._select()
            .where(*conditions)
            .order_by(Invitation.created_at.desc(), Invitation.id.desc())
        )
        return [(r[0], r[1], r[2], r[3]) for r in (await self.session.execute(stmt)).all()]

    async def row(self, invitation_id: int) -> InvitationRow | None:
        rows = await self.rows(Invitation.id == invitation_id)
        return rows[0] if rows else None

    async def get(self, invitation_id: int) -> Invitation | None:
        return await self.session.get(Invitation, invitation_id)

    async def events(self, invitation_id: int) -> list[InvitationEvent]:
        rows = await self.session.scalars(
            select(InvitationEvent)
            .where(InvitationEvent.invitation_id == invitation_id)
            .order_by(InvitationEvent.at, InvitationEvent.id)
        )
        return list(rows.all())

    async def recruiter_contacts(self, recruiter_ids: Sequence[int]) -> dict[int, dict[str, Any]]:
        if not recruiter_ids:
            return {}
        rows = (
            await self.session.execute(
                select(Recruiter, User.full_name, User.email)
                .join(User, User.id == Recruiter.user_id)
                .where(Recruiter.id.in_(list(recruiter_ids)))
            )
        ).all()
        return {
            r.id: {
                "full_name": full_name,
                "position": r.position or "",
                "email": email,
                "phone": r.phone,
                "telegram": r.telegram,
            }
            for r, full_name, email in rows
        }

    async def company(self, company_id: int) -> Company | None:
        return await self.session.get(Company, company_id)

    async def recruiter_name(self, recruiter_id: int) -> str:
        name = await self.session.scalar(
            select(User.full_name)
            .join(Recruiter, Recruiter.user_id == User.id)
            .where(Recruiter.id == recruiter_id)
        )
        return str(name or "")

    async def recruiter_email(self, recruiter_id: int) -> str | None:
        email = await self.session.scalar(
            select(User.email)
            .join(Recruiter, Recruiter.user_id == User.id)
            .where(Recruiter.id == recruiter_id)
        )
        return str(email) if email else None

    # ---------- квота и ограничения ----------

    async def active_count(self, recruiter_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(Invitation)
            .where(Invitation.recruiter_id == recruiter_id, Invitation.status.in_(ACTIVE))
        )
        return int(await self.session.scalar(stmt) or 0)

    async def active_for(self, company_id: int, candidate_id: int) -> Invitation | None:
        rows = await self.session.scalars(
            select(Invitation)
            .where(
                Invitation.company_id == company_id,
                Invitation.candidate_id == candidate_id,
                Invitation.status.in_(ACTIVE),
            )
            .order_by(Invitation.created_at.desc())
            .limit(1)
        )
        return rows.first()

    # ---------- счётчики (T7.8) ----------

    async def count_candidate_new(self, candidate_id: int) -> tuple[int, int]:
        """(новые — ещё не открытые, активные всего)."""
        rows = (
            await self.session.execute(
                select(Invitation.status, func.count())
                .where(Invitation.candidate_id == candidate_id, Invitation.status.in_(ACTIVE))
                .group_by(Invitation.status)
            )
        ).all()
        by_status = {status: int(n) for status, n in rows}
        return by_status.get(InvitationStatus.sent.value, 0), sum(by_status.values())

    async def count_company_updates(self, company_id: int) -> int:
        """Ответы кандидатов (просмотр, принятие, отказ), которые рекрутер ещё не открывал."""
        changed_at = func.coalesce(Invitation.responded_at, Invitation.viewed_at)
        stmt = (
            select(func.count())
            .select_from(Invitation)
            .where(
                Invitation.company_id == company_id,
                Invitation.status.in_(["viewed", "accepted", "declined"]),
                changed_at.is_not(None),
                or_(
                    Invitation.recruiter_seen_at.is_(None),
                    Invitation.recruiter_seen_at < changed_at,
                ),
            )
        )
        return int(await self.session.scalar(stmt) or 0)

    async def count_company_active(self, company_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(Invitation)
            .where(Invitation.company_id == company_id, Invitation.status.in_(ACTIVE))
        )
        return int(await self.session.scalar(stmt) or 0)

    # ---------- рыночная подсказка ----------

    async def accepted_ranges(self, category: str) -> list[tuple[int, int]]:
        rows = (
            await self.session.execute(
                select(Invitation.salary_from, Invitation.salary_to).where(
                    Invitation.category == category,
                    Invitation.status == InvitationStatus.accepted.value,
                )
            )
        ).all()
        return [(int(a), int(b)) for a, b in rows]

    async def candidate_minimums(self, category: str) -> list[int]:
        rows = await self.session.scalars(
            select(CandidateProfile.min_salary).where(
                CandidateProfile.category == category,
                CandidateProfile.min_salary.is_not(None),
                CandidateProfile.min_salary > 0,
            )
        )
        return [int(v) for v in rows.all() if v]
