"""Данные кабинета администратора.

- `AdminDb` — пользователи и журнал действий в БД (T10.2).
- `AdminRepository` — фикстуры для разделов следующих волн: дашборд, банк задач,
  задания из вакансий, жалобы (волны 3, 4c, 5b).
"""

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import AuditLog
from app.candidates.models import CandidateProfile
from app.catalog.clock import as_msk
from app.common import fixtures
from app.common.fixtures import Record
from app.companies.models import Recruiter
from app.users.models import User


def user_record(u: User) -> Record:
    return {
        "id": u.id,
        "email": u.email,
        "role": u.role,
        "full_name": u.full_name,
        "email_verified": u.email_verified,
        "blocked": u.blocked,
        "created_at": as_msk(u.created_at),
        "last_login_at": as_msk(u.last_login_at),
    }


def audit_record(a: AuditLog) -> Record:
    return {
        "id": a.id,
        "at": as_msk(a.at),
        "actor_user_id": a.actor_user_id,
        "actor_role": a.actor_role,
        "action": a.action,
        "target_type": a.target_type,
        "target_id": a.target_id,
        "summary": a.summary,
        "details": a.details or {},
    }


class AdminDb:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def user(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def users(
        self, q: str | None, role: str | None, blocked: bool | None, page: int, page_size: int
    ) -> tuple[list[User], int]:
        stmt = select(User)
        if q:
            pattern = f"%{q.strip()}%"
            stmt = stmt.where(or_(User.email.ilike(pattern), User.full_name.ilike(pattern)))
        if role:
            stmt = stmt.where(User.role == role)
        if blocked is not None:
            stmt = stmt.where(User.blocked.is_(blocked))
        total = int(
            await self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        )
        rows = await self.session.scalars(
            stmt.order_by(User.id).offset((page - 1) * page_size).limit(page_size)
        )
        return list(rows.all()), total

    async def has_candidate_profile(self, user_id: int) -> bool:
        stmt = select(CandidateProfile.id).where(CandidateProfile.user_id == user_id)
        return await self.session.scalar(stmt) is not None

    async def has_recruiter_profile(self, user_id: int) -> bool:
        stmt = select(Recruiter.id).where(Recruiter.user_id == user_id)
        return await self.session.scalar(stmt) is not None

    async def audit(
        self,
        *,
        action: str | None = None,
        target_type: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AuditLog], int]:
        stmt = select(AuditLog)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if target_type:
            stmt = stmt.where(AuditLog.target_type == target_type)
        total = int(
            await self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        )
        rows = await self.session.scalars(
            stmt.order_by(AuditLog.at.desc(), AuditLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(rows.all()), total

    async def user_audit(self, user_id: int) -> list[AuditLog]:
        """Действия пользователя и действия над ним (как над пользователем или кандидатом)."""
        candidate_id = await self.session.scalar(
            select(CandidateProfile.id).where(CandidateProfile.user_id == user_id)
        )
        conditions: list[Any] = [
            AuditLog.actor_user_id == user_id,
            (AuditLog.target_type == "user") & (AuditLog.target_id == user_id),
        ]
        if candidate_id is not None:
            conditions.append(
                (AuditLog.target_type == "candidate") & (AuditLog.target_id == candidate_id)
            )
        rows = await self.session.scalars(
            select(AuditLog).where(or_(*conditions)).order_by(AuditLog.at.desc(), AuditLog.id)
        )
        return list(rows.all())


class AdminRepository:
    """Фикстуры для разделов админки следующих волн."""

    def users(self) -> list[Record]:
        return fixtures.all_records("users")

    def invitations(self) -> list[Record]:
        return fixtures.all_records("invitations")

    def test_sessions(self) -> list[Record]:
        return fixtures.all_records("test_sessions")

    def items(self) -> list[Record]:
        return fixtures.all_records("items")

    def item(self, item_id: int) -> Record | None:
        return fixtures.by_id("items", item_id)

    def topics(self) -> list[Record]:
        return fixtures.all_records("topics")

    def company(self, company_id: int) -> Record | None:
        return fixtures.by_id("companies", company_id)

    def reports(self) -> list[Record]:
        return fixtures.all_records("reports")

    def report(self, report_id: int) -> Record | None:
        return fixtures.by_id("reports", report_id)

    def vacancy_tests(self) -> list[Record]:
        return fixtures.all_records("vacancy_tests")
