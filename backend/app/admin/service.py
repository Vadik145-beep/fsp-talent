"""Жалобы соискателей на работодателей (T10.6, T12.1) — на БД.

Кандидат жалуется на компанию, с которой у него был контакт (приглашение, отклик на вакансию
или задание). Админ берёт жалобу в работу, подтверждает (по желанию — сразу блокирует
компанию) или отклоняет. Подтверждённая жалоба снижает скоринг надёжности компании
(−15, см. `app.companies.service.trust_score`), жалоба в работе — −5. Всё пишется в журнал.
"""

from typing import Any

from pydantic import Field
from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.audit import write_audit
from app.admin.models import Report
from app.admin.repository import AdminRepository
from app.admin.schemas import ReportCreate, ReportUpdate
from app.catalog.clock import as_msk, now_msk
from app.common.enums import ReportStatus
from app.common.fixtures import Record
from app.companies.antifraud import set_company_blocked
from app.companies.models import Company
from app.core.errors import AppError, not_found
from app.core.security import CurrentUser
from app.invitations.models import Invitation
from app.tasks.models import RegularTask, TaskSubmission
from app.vacancies.models import Application, Vacancy

R = ReportStatus
OPEN = (R.new.value, R.in_review.value)
FINAL = (R.resolved.value, R.rejected.value)
# допустимые переходы статуса жалобы
TRANSITIONS: dict[str, tuple[str, ...]] = {
    R.new: (R.in_review, R.resolved, R.rejected),
    R.in_review: (R.resolved, R.rejected),
    R.resolved: (),
    R.rejected: (),
}
STATUS_LABELS = {
    R.new: "новая",
    R.in_review: "в работе",
    R.resolved: "подтверждена",
    R.rejected: "отклонена",
}
REASON_LABELS = {
    "fake_vacancy": "фиктивная вакансия",
    "spam": "спам",
    "salary_mismatch": "зарплата не та",
    "rude": "грубость",
    "other": "другое",
}


class AdminService:
    """Остаток фикстур: демо-примеры тестов из вакансий (`vacancy_tests_router`, волна 3c)."""

    def __init__(self, repo: AdminRepository | None = None) -> None:
        self.repo = repo or AdminRepository()

    def vacancy_tests(self) -> list[Record]:
        return self.repo.vacancy_tests()


class ReportDecision(ReportUpdate):
    """Решение по жалобе. Схема живёт здесь, чтобы не трогать общий `admin/schemas.py`."""

    block_company: bool = Field(
        default=False,
        description="Вместе с подтверждением (resolved) заблокировать компанию",
    )


def report_record(r: Report, company_name: str) -> Record:
    return {
        "id": r.id,
        "company_id": r.company_id,
        "company_name": company_name,
        "reporter_candidate_id": r.reporter_candidate_id,
        "invitation_id": r.invitation_id,
        "vacancy_id": r.vacancy_id,
        "reason": r.reason,
        "text": r.text,
        "status": r.status,
        "resolution": r.resolution,
        "created_at": as_msk(r.created_at),
        "resolved_at": as_msk(r.resolved_at),
    }


class ReportService:
    def __init__(self, session: AsyncSession, actor: CurrentUser) -> None:
        self.session = session
        self.actor = actor

    async def _rows(self, *where: Any) -> list[Record]:
        rows = await self.session.execute(
            select(Report, Company.name)
            .join(Company, Company.id == Report.company_id)
            .where(*where)
            .order_by(Report.created_at.desc(), Report.id.desc())
        )
        return [report_record(r, name) for r, name in rows.all()]

    async def _one(self, report_id: int) -> Record:
        return (await self._rows(Report.id == report_id))[0]

    # ---------- соискатель ----------

    async def _had_contact(self, candidate_id: int, company_id: int) -> bool:
        invited = exists().where(
            Invitation.candidate_id == candidate_id, Invitation.company_id == company_id
        )
        applied = exists().where(
            Application.candidate_id == candidate_id,
            Application.vacancy_id == Vacancy.id,
            Vacancy.company_id == company_id,
        )
        tasked = exists().where(
            TaskSubmission.candidate_id == candidate_id,
            TaskSubmission.task_id == RegularTask.id,
            RegularTask.company_id == company_id,
        )
        return bool(await self.session.scalar(select(or_(invited, applied, tasked))))

    async def create(self, body: ReportCreate, candidate_id: int) -> Record:
        company = await self.session.get(Company, body.company_id)
        if company is None:
            raise not_found("company", body.company_id)
        if body.invitation_id is not None:
            inv = await self.session.get(Invitation, body.invitation_id)
            if inv is None or inv.candidate_id != candidate_id or inv.company_id != company.id:
                raise not_found("invitation", body.invitation_id)
        if body.vacancy_id is not None:
            vacancy = await self.session.get(Vacancy, body.vacancy_id)
            if vacancy is None or vacancy.company_id != company.id:
                raise not_found("vacancy", body.vacancy_id)
        if not await self._had_contact(candidate_id, company.id):
            raise AppError(
                403,
                "no_contact_with_company",
                "Пожаловаться можно на компанию, с которой был контакт: приглашение, отклик "
                "или задание",
                {"company_id": company.id},
            )
        duplicate = await self.session.scalar(
            select(Report.id).where(
                Report.reporter_candidate_id == candidate_id,
                Report.company_id == company.id,
                Report.status.in_(OPEN),
            )
        )
        if duplicate is not None:
            raise AppError(
                409,
                "report_exists",
                "Ваша жалоба на эту компанию уже на рассмотрении",
                {"report_id": duplicate},
            )
        report = Report(
            company_id=company.id,
            reporter_candidate_id=candidate_id,
            invitation_id=body.invitation_id,
            vacancy_id=body.vacancy_id,
            reason=str(body.reason),
            text=body.text.strip(),
            status=R.new.value,
            created_at=now_msk(),
        )
        self.session.add(report)
        await self.session.flush()
        await write_audit(
            self.session,
            self.actor,
            "report_created",
            "report",
            report.id,
            f"Жалоба на «{company.name}»: {REASON_LABELS.get(report.reason, report.reason)}",
            {"company_id": company.id, "reason": report.reason},
        )
        await self.session.commit()
        return await self._one(report.id)

    # ---------- администратор ----------

    async def queue(self, status: ReportStatus | None) -> list[Record]:
        rows = await self._rows(*([Report.status == status.value] if status else []))
        order = {R.new: 0, R.in_review: 1, R.resolved: 2, R.rejected: 3}
        return sorted(rows, key=lambda r: order[R(r["status"])])  # устойчиво: внутри — свежие

    async def decide(self, report_id: int, body: ReportDecision) -> Record:
        report = await self.session.get(Report, report_id, with_for_update=True)
        if report is None:
            raise not_found("report", report_id)
        target = body.status.value
        if target not in TRANSITIONS[R(report.status)]:
            raise AppError(
                409,
                "invalid_transition",
                f"Жалоба уже {STATUS_LABELS[R(report.status)]} — "
                f"перевести в «{STATUS_LABELS[body.status]}» нельзя",
                {"from": report.status, "to": target},
            )
        if body.block_company and target != R.resolved:
            raise AppError(
                422,
                "block_requires_resolve",
                "Заблокировать компанию можно только при подтверждении жалобы",
                {"fields": {"block_company": "Выберите «Подтвердить»"}},
            )
        company = await self.session.get(Company, report.company_id)
        assert company is not None
        report.status = target
        if body.resolution is not None:
            report.resolution = body.resolution.strip() or None
        if target in FINAL:
            report.resolved_at = now_msk()
            report.resolved_by = self.actor.user_id
        action = "report_resolved" if target in FINAL else "report_in_review"
        summary = f"Жалоба на «{company.name}» {STATUS_LABELS[body.status]}" + (
            f": {report.resolution}" if report.resolution and target in FINAL else ""
        )
        await write_audit(
            self.session,
            self.actor,
            action,
            "report",
            report.id,
            summary,
            {"company_id": company.id, "status": target, "block_company": body.block_company},
        )
        if body.block_company:
            await set_company_blocked(
                self.session,
                company,
                True,
                self.actor,
                reason=f"подтверждена жалоба #{report.id}",
                details={"report_id": report.id},
            )
        await self.session.commit()
        return await self._one(report.id)
