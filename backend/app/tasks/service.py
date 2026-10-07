"""Регулярные задания на БД (E9): создание, раздача, ответ, оценка 0–3, свежесть профиля.

Жизненный цикл выданного задания: assigned → submitted → graded, или assigned → expired
(срок вышел без ответа). У кандидата не больше одного активного (assigned) задания.

Раздача: задание получают кандидаты его категории без активного задания, которым это задание
ещё не выдавали (не заблокированы, поиск не на паузе). Раздача идёт сразу при создании задания
и при вызове `distribute_all` — его зовёт планировщик раз в N дней (`python -m app.tasks`).

Свежесть профиля (0..1, поле `candidate_profiles.freshness`, входит в ранжирование подборки):
+0,08 за отправленный ответ, +0,04 + 0,03 × балл за первую оценку; без активности падает вдвое
за 30 дней (`decay_freshness`, зовёт планировщик раз в сутки). Числа — в `TASKS_*`.
"""

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Float, Numeric, case, cast, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import AuditLog
from app.candidates.models import CandidateProfile
from app.candidates.repository import CandidateDb
from app.candidates.service import to_card
from app.catalog.clock import as_msk, now_msk
from app.catalog.models import Category
from app.common.enums import SubmissionStatus, TaskStatus
from app.common.fixtures import Record
from app.companies.antifraud import active_company_ids, ensure_company_active
from app.companies.models import Company
from app.core.errors import AppError, not_found
from app.core.security import CurrentUser
from app.tasks.models import RegularTask, TaskSubmission
from app.tasks.schemas import RegularTaskCreate, SubmissionAnswer, SubmissionGrade
from app.tasks.settings import get_task_settings
from app.users.models import User

S = SubmissionStatus
DECAY_ACTION = "freshness_decayed"
# порядок ответов в кабинете рекрутера: сначала ждущие оценки
RECRUITER_ORDER = {S.submitted: 0, S.graded: 1, S.assigned: 2, S.expired: 3}


def _clamp(value: float) -> float:
    return round(min(1.0, max(0.0, value)), 3)


def task_record(task: RegularTask, company_name: str, category_label: str, count: int) -> Record:
    return {
        "id": task.id,
        "company_id": task.company_id,
        "company_name": company_name,
        "recruiter_id": task.recruiter_id,
        "title": task.title,
        "statement": task.statement,
        "category": task.category,
        "category_label": category_label,
        "deadline_days": task.deadline_days,
        "status": task.status,
        "submissions_count": count,
        "created_at": as_msk(task.created_at),
    }


def submission_record(sub: TaskSubmission, task: RegularTask, company_name: str) -> Record:
    return {
        "id": sub.id,
        "task_id": sub.task_id,
        "candidate_id": sub.candidate_id,
        "task_title": task.title,
        "statement": task.statement,
        "company_name": company_name,
        "status": sub.status,
        "assigned_at": as_msk(sub.assigned_at),
        "due_at": as_msk(sub.due_at),
        "answer_kind": sub.answer_kind,
        "answer_text": sub.answer_text,
        "submitted_at": as_msk(sub.submitted_at),
        "score": sub.score,
        "grader_comment": sub.grader_comment,
        "graded_at": as_msk(sub.graded_at),
    }


class TaskService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_task_settings()

    # ---------- чтение ----------

    async def _task_rows(self, *where: Any) -> list[Record]:
        counts = (
            select(TaskSubmission.task_id, func.count().label("n"))
            .group_by(TaskSubmission.task_id)
            .subquery()
        )
        rows = await self.session.execute(
            select(RegularTask, Company.name, Category.label, func.coalesce(counts.c.n, 0))
            .join(Company, Company.id == RegularTask.company_id)
            .join(Category, Category.code == RegularTask.category)
            .outerjoin(counts, counts.c.task_id == RegularTask.id)
            .where(*where)
            .order_by(RegularTask.created_at.desc(), RegularTask.id.desc())
        )
        return [task_record(t, name, label, int(n)) for t, name, label, n in rows.all()]

    async def _submission_rows(self, *where: Any) -> list[tuple[TaskSubmission, Record]]:
        rows = await self.session.execute(
            select(TaskSubmission, RegularTask, Company.name)
            .join(RegularTask, RegularTask.id == TaskSubmission.task_id)
            .join(Company, Company.id == RegularTask.company_id)
            .where(*where)
            .order_by(TaskSubmission.assigned_at.desc(), TaskSubmission.id.desc())
        )
        return [(sub, submission_record(sub, task, name)) for sub, task, name in rows.all()]

    async def _with_cards(self, subs: Sequence[Record]) -> list[Record]:
        cards = await CandidateDb(self.session).records(list({s["candidate_id"] for s in subs}))
        result = []
        for s in subs:
            cand = cards.get(s["candidate_id"])
            result.append({**s, "candidate": to_card(cand) if cand else None})
        return result

    async def _profile(self, candidate_id: int) -> CandidateProfile:
        profile = await self.session.get(CandidateProfile, candidate_id)
        if profile is None:
            raise AppError(404, "not_found", "Профиль кандидата не найден")
        return profile

    # ---------- кандидат ----------

    async def inbox(self, candidate_id: int) -> dict[str, Any]:
        profile = await self._profile(candidate_id)
        if await self.expire_overdue(candidate_id=candidate_id):
            await self.session.commit()
        subs = [
            r for _, r in await self._submission_rows(TaskSubmission.candidate_id == candidate_id)
        ]
        active = next((s for s in subs if s["status"] == S.assigned.value), None)
        history = [s for s in subs if s is not active]
        return {"active": active, "history": history, "freshness": profile.freshness or 0.0}

    async def answer(
        self, submission_id: int, candidate_id: int, body: SubmissionAnswer
    ) -> dict[str, Any]:
        sub = await self.session.get(TaskSubmission, submission_id, with_for_update=True)
        if sub is None or sub.candidate_id != candidate_id:
            raise not_found("task_submission", submission_id)
        if sub.status != S.assigned:
            raise AppError(
                409,
                "invalid_transition",
                "Ответ на это задание уже отправлен или срок истёк",
                {"status": sub.status},
            )
        now = now_msk()
        if sub.due_at <= now:
            sub.status = S.expired.value
            await self.session.commit()
            raise AppError(
                409, "submission_expired", "Срок ответа истёк", {"due_at": sub.due_at.isoformat()}
            )
        sub.status = S.submitted.value
        sub.answer_kind = str(body.answer_kind)
        sub.answer_text = body.answer_text.strip()
        sub.submitted_at = now
        profile = await self._profile(candidate_id)
        profile.freshness = _clamp((profile.freshness or 0) + self.settings.freshness_answer_bonus)
        await self.session.commit()
        return await self._one(submission_id)

    async def _one(self, submission_id: int) -> Record:
        rows = await self._submission_rows(TaskSubmission.id == submission_id)
        return rows[0][1]

    # ---------- рекрутер ----------

    async def list_tasks(self, company_id: int) -> list[Record]:
        return await self._task_rows(RegularTask.company_id == company_id)

    async def create_task(self, body: RegularTaskCreate, user: CurrentUser) -> Record:
        assert user.company_id is not None and user.recruiter_id is not None
        await ensure_company_active(self.session, user.company_id)
        if await self.session.get(Category, body.category) is None:
            raise AppError(
                422,
                "unknown_category",
                "Неизвестная категория",
                {"category": body.category, "fields": {"category": "Выберите категорию"}},
            )
        task = RegularTask(
            company_id=user.company_id,
            recruiter_id=user.recruiter_id,
            title=body.title.strip(),
            statement=body.statement.strip(),
            category=body.category,
            deadline_days=body.deadline_days,
            status=TaskStatus.active.value,
            created_at=now_msk(),
        )
        self.session.add(task)
        await self.session.flush()
        await self.distribute_task(task)
        await self.session.commit()
        return (await self._task_rows(RegularTask.id == task.id))[0]

    async def _own_task(self, task_id: int, company_id: int) -> RegularTask:
        task = await self.session.get(RegularTask, task_id)
        if task is None or task.company_id != company_id:
            raise not_found("regular_task", task_id)
        return task

    async def task_submissions(self, task_id: int, company_id: int) -> list[Record]:
        await self._own_task(task_id, company_id)
        if await self.expire_overdue(task_id=task_id):
            await self.session.commit()
        subs = [r for _, r in await self._submission_rows(TaskSubmission.task_id == task_id)]
        subs.sort(key=lambda s: RECRUITER_ORDER[S(s["status"])])  # устойчиво: внутри — свежие
        return await self._with_cards(subs)

    async def distribute_now(self, task_id: int, user: CurrentUser) -> dict[str, int]:
        assert user.company_id is not None
        task = await self._own_task(task_id, user.company_id)
        await ensure_company_active(self.session, user.company_id)
        if task.status != TaskStatus.active:
            raise AppError(409, "invalid_transition", "Задание в архиве — раздавать нельзя")
        assigned = await self.distribute_task(task)
        await self.session.commit()
        return {"assigned": assigned}

    async def grade(
        self, submission_id: int, body: SubmissionGrade, user: CurrentUser
    ) -> dict[str, Any]:
        sub = await self.session.get(TaskSubmission, submission_id, with_for_update=True)
        task = await self.session.get(RegularTask, sub.task_id) if sub else None
        if sub is None or task is None or task.company_id != user.company_id:
            raise not_found("task_submission", submission_id)
        if sub.status not in (S.submitted, S.graded):
            raise AppError(
                409,
                "invalid_transition",
                "Оценить можно только присланный ответ",
                {"status": sub.status},
            )
        cfg = self.settings
        if sub.status == S.submitted:
            delta = cfg.freshness_grade_base + cfg.freshness_grade_per_point * body.score
        else:  # переоценка: свежесть меняется на разницу баллов
            delta = cfg.freshness_grade_per_point * (body.score - (sub.score or 0))
        sub.status = S.graded.value
        sub.score = body.score
        sub.grader_comment = (body.comment or "").strip() or None
        sub.graded_by = user.user_id
        sub.graded_at = now_msk()
        profile = await self._profile(sub.candidate_id)
        profile.freshness = _clamp((profile.freshness or 0) + delta)
        await self.session.commit()
        return (await self._with_cards([await self._one(submission_id)]))[0]

    # ---------- раздача, сроки, свежесть (планировщик) ----------

    async def distribute_task(self, task: RegularTask, now: datetime | None = None) -> int:
        """Выдать задание кандидатам его категории без активного задания. Без коммита."""
        now = now or now_msk()
        busy = select(TaskSubmission.candidate_id).where(TaskSubmission.status == S.assigned.value)
        had = select(TaskSubmission.candidate_id).where(TaskSubmission.task_id == task.id)
        last_assigned = (
            select(func.max(TaskSubmission.assigned_at))
            .where(TaskSubmission.candidate_id == CandidateProfile.id)
            .correlate(CandidateProfile)
            .scalar_subquery()
        )
        ids = (
            await self.session.scalars(
                select(CandidateProfile.id)
                .join(User, User.id == CandidateProfile.user_id)
                .where(
                    CandidateProfile.category == task.category,
                    CandidateProfile.job_search_paused.is_(False),
                    User.blocked.is_(False),
                    CandidateProfile.id.not_in(busy),
                    CandidateProfile.id.not_in(had),
                )
                # дольше всех без заданий — первыми
                .order_by(last_assigned.asc().nulls_first(), CandidateProfile.id)
                .limit(self.settings.max_assign_per_run)
            )
        ).all()
        due = now + timedelta(days=task.deadline_days)
        for cid in ids:
            self.session.add(
                TaskSubmission(
                    task_id=task.id,
                    candidate_id=cid,
                    status=S.assigned.value,
                    assigned_at=now,
                    due_at=due,
                )
            )
        await self.session.flush()
        return len(ids)

    async def distribute_all(self, now: datetime | None = None) -> int:
        """Раздать все активные задания незаблокированных компаний (старые — первыми)."""
        tasks = (
            await self.session.scalars(
                select(RegularTask)
                .where(
                    RegularTask.status == TaskStatus.active.value,
                    RegularTask.company_id.in_(active_company_ids()),
                )
                .order_by(RegularTask.created_at, RegularTask.id)
            )
        ).all()
        total = 0
        for task in tasks:
            total += await self.distribute_task(task, now)
        return total

    async def expire_overdue(
        self,
        now: datetime | None = None,
        *,
        candidate_id: int | None = None,
        task_id: int | None = None,
    ) -> int:
        """Активные задания с прошедшим сроком → expired. Без коммита."""
        stmt = update(TaskSubmission).where(
            TaskSubmission.status == S.assigned.value, TaskSubmission.due_at <= (now or now_msk())
        )
        if candidate_id is not None:
            stmt = stmt.where(TaskSubmission.candidate_id == candidate_id)
        if task_id is not None:
            stmt = stmt.where(TaskSubmission.task_id == task_id)
        result = await self.session.execute(stmt.values(status=S.expired.value))
        return int(getattr(result, "rowcount", 0) or 0)

    async def decay_freshness(self, now: datetime | None = None) -> dict[str, Any]:
        """Снизить свежесть всех профилей пропорционально времени с прошлого запуска.

        Множитель 0,5^(дней / период полураспада). Время прошлого запуска — запись
        `freshness_decayed` в журнале; первого запуска нет — считаем, что прошли сутки.
        Без коммита.
        """
        now = now or now_msk()
        last = await self.session.scalar(
            select(func.max(AuditLog.at)).where(AuditLog.action == DECAY_ACTION)
        )
        elapsed = (now - last).total_seconds() / 86400 if last else 1.0
        if elapsed <= 0:
            return {"factor": 1.0, "elapsed_days": 0.0, "profiles": 0}
        factor = 0.5 ** (elapsed / self.settings.freshness_half_life_days)
        decayed = cast(func.round(cast(CandidateProfile.freshness * factor, Numeric), 3), Float)
        result = await self.session.execute(
            update(CandidateProfile)
            .where(CandidateProfile.freshness > 0)
            .values(
                freshness=case((decayed < 0.001, 0.0), else_=decayed),
                updated_at=CandidateProfile.updated_at,  # это не правка профиля человеком
            )
        )
        profiles = int(getattr(result, "rowcount", 0) or 0)
        self.session.add(
            AuditLog(
                at=now,
                actor_user_id=None,
                actor_role=None,
                action=DECAY_ACTION,
                target_type="system",
                target_id=None,
                summary=(
                    f"Свежесть профилей снижена ×{factor:.3f} за {elapsed:.1f} дн. "
                    f"(профилей: {profiles})"
                ),
                details={"factor": round(factor, 4), "elapsed_days": round(elapsed, 2)},
            )
        )
        await self.session.flush()
        return {"factor": round(factor, 4), "elapsed_days": round(elapsed, 2), "profiles": profiles}
