"""Доступ к профилям кандидатов.

- `CandidateDb` — таблицы БД (async): профиль, стек, привязка ФСП, связанные записи.
- `CandidateRepository` — фикстуры `data/seed`; остаётся для модулей, которые ещё работают
  на фикстурах (matching, invitations, vacancies, tasks, testing — волна 3).
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import any_, delete, exists, func, insert, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.candidates.fsp_score import achievements_for, fsp_badges, fsp_score
from app.candidates.models import CandidateProfile, candidate_skills
from app.catalog.clock import as_msk, now_msk
from app.catalog.models import Category
from app.common import fixtures
from app.common.enums import grade_status_code
from app.common.fixtures import Record
from app.companies.models import Company
from app.fsp.models import FspAchievement, FspLink
from app.invitations.models import Invitation
from app.tasks.models import RegularTask, TaskSubmission
from app.testing.models import GradeHistory, TestSession
from app.users.models import Consent, User
from app.vacancies.models import Application, Vacancy


class CandidateRepository:
    """Профили из фикстур (для модулей на фикстурах)."""

    def all(self) -> list[Record]:
        return fixtures.all_records("candidates")

    def get(self, candidate_id: int) -> Record | None:
        return fixtures.by_id("candidates", candidate_id)

    def test_sessions(self, candidate_id: int) -> list[Record]:
        return fixtures.where("test_sessions", candidate_id=candidate_id)

    def invitations(self, candidate_id: int) -> list[Record]:
        return fixtures.where("invitations", candidate_id=candidate_id)

    def applications(self, candidate_id: int) -> list[Record]:
        return fixtures.where("applications", candidate_id=candidate_id)

    def submissions(self, candidate_id: int) -> list[Record]:
        return fixtures.where("task_submissions", candidate_id=candidate_id)


def profile_completeness(record: Record) -> int:
    """Полнота профиля, % — 10 признаков, как в генераторе фикстур."""
    filled = [
        record.get("phone"),
        record.get("telegram"),
        record.get("city"),
        record.get("grade"),
        record.get("links"),
        record.get("fsp_id"),
        record.get("about"),
        record.get("min_salary"),
        len(record.get("stack") or []) >= 4,
        record.get("soft_skills"),
    ]
    return round(100 * sum(bool(x) for x in filled) / 10)


def searchable_conditions() -> list[ColumnElement[bool]]:
    """Условия попадания в выдачу [T2.4, T3.4]: грейд подтверждён тестом, согласие на
    публикацию, поиск не на паузе, пользователь не заблокирован.

    Явное правило (FTT.4): `grade` пишет только результат теста; заявленный соискателем
    грейд (`declared_grade`, статус «не подтверждён») в выдачу, подборку и банк кандидатов
    не пускает."""
    return [
        CandidateProfile.grade.is_not(None),
        CandidateProfile.publication_consent.is_(True),
        CandidateProfile.job_search_paused.is_(False),
        User.blocked.is_(False),
    ]


def has_fsp_condition() -> ColumnElement[bool]:
    """«Есть достижения ФСП» (фильтр банка и подборки, флаг `has_fsp` карточки): у кандидата
    есть хотя бы одно подтверждённое достижение ФСП И он не скрыл достижения настройкой
    приватности. Привязанный ФСП ID без истории или со скрытыми достижениями — «нет»:
    фильтр не должен выдавать скрытое участие."""
    cp = CandidateProfile
    achieved = (
        exists()
        .where(
            FspLink.candidate_id == cp.id,
            FspAchievement.fsp_id == FspLink.fsp_id,
            FspAchievement.verified.is_(True),
        )
        .correlate(cp)
    )
    shown = func.coalesce(cp.privacy["show_fsp_achievements"].as_boolean(), True).is_(True)
    return achieved & shown


class CandidateDb:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---------- профиль ----------

    async def profile(self, candidate_id: int) -> CandidateProfile | None:
        return await self.session.get(CandidateProfile, candidate_id)

    async def by_user(self, user_id: int) -> CandidateProfile | None:
        rows = await self.session.scalars(
            select(CandidateProfile).where(CandidateProfile.user_id == user_id)
        )
        return rows.first()

    async def stacks(self, ids: Sequence[int]) -> dict[int, list[str]]:
        rows = await self.session.execute(
            select(candidate_skills.c.candidate_id, candidate_skills.c.skill_code)
            .where(candidate_skills.c.candidate_id.in_(ids))
            .order_by(candidate_skills.c.position, candidate_skills.c.skill_code)
        )
        result: dict[int, list[str]] = {i: [] for i in ids}
        for cid, code in rows:
            result[cid].append(code)
        return result

    async def fsp_ids(self, ids: Sequence[int]) -> dict[int, str]:
        rows = await self.session.execute(
            select(FspLink.candidate_id, FspLink.fsp_id).where(FspLink.candidate_id.in_(ids))
        )
        return {cid: fsp_id for cid, fsp_id in rows}

    async def records(self, ids: Sequence[int]) -> dict[int, Record]:
        """Полные записи профилей (форма `CandidateProfile` из контракта) по id."""
        if not ids:
            return {}
        rows = (
            await self.session.execute(
                select(CandidateProfile, User, Category.label)
                .join(User, User.id == CandidateProfile.user_id)
                .outerjoin(Category, Category.code == CandidateProfile.category)
                .where(CandidateProfile.id.in_(ids))
            )
        ).all()
        stacks = await self.stacks(ids)
        fsp = await self.fsp_ids(ids)
        confirmed = await self.grade_confirmed_at(ids)
        result: dict[int, Record] = {}
        for p, user, category_label in rows:
            record = await self._record(p, user, category_label, stacks[p.id], fsp.get(p.id))
            if p.grade:
                at = confirmed.get((p.id, p.specialization or ""))
                # только дата пройденного теста: последняя попытка могла быть неудачной
                record["grade_confirmed_at"] = as_msk(at) if at else None
            result[p.id] = record
        return result

    async def grade_confirmed_at(self, ids: Sequence[int]) -> dict[tuple[int, str], Any]:
        """Дата последнего пройденного теста по (кандидат, специализация) — один запрос."""
        rows = await self.session.execute(
            select(
                TestSession.candidate_id,
                TestSession.specialization,
                func.max(TestSession.finished_at),
            )
            .where(
                TestSession.candidate_id.in_(ids),
                TestSession.status == "finished",
                TestSession.passed.is_(True),
            )
            .group_by(TestSession.candidate_id, TestSession.specialization)
        )
        return {(cid, spec): at for cid, spec, at in rows}

    async def record(self, candidate_id: int) -> Record | None:
        return (await self.records([candidate_id])).get(candidate_id)

    async def _record(
        self,
        p: CandidateProfile,
        user: User,
        category_label: str | None,
        stack: list[str],
        fsp_id: str | None,
    ) -> Record:
        score, badges = p.fsp_score, list(p.fsp_badges or [])
        if fsp_id and score is None:
            # снимка ещё нет (ФСП ID привязали после загрузки сида) — считаем на лету
            achs = await achievements_for(self.session, fsp_id)
            score, badges = fsp_score(achs), fsp_badges(achs)
        if not fsp_id:
            score, badges = None, []
        record: Record = {
            "id": p.id,
            "user_id": p.user_id,
            "pseudonym": p.pseudonym,
            "full_name": user.full_name,
            "email": user.email,
            "phone": p.phone,
            "telegram": p.telegram,
            "city": p.city,
            "work_formats": list(p.work_formats or []),
            "specialization": p.specialization,
            "grade": p.grade,
            "category": p.category,
            "category_label": category_label,
            "theta": p.theta,
            "theta_se": p.theta_se,
            "topic_scores": list(p.topic_scores or []),
            "stack": stack,
            "roles_in_team": list(p.roles_in_team or []),
            "experience_years": p.experience_years,
            "soft_skills": list(p.soft_skills or []),
            "about": p.about,
            "links": list(p.links or []),
            "min_salary": p.min_salary,
            "fsp_id": fsp_id,
            "fsp_score": score,
            "fsp_badges": badges,
            "privacy": dict(p.privacy or {}),
            "job_search_paused": p.job_search_paused,
            "publication_consent": p.publication_consent,
            "freshness": p.freshness,
            "last_test_at": as_msk(p.last_test_at),
            "grade_changed_at": as_msk(p.grade_changed_at),
            "grade_status": grade_status_code(p.grade, p.declared_grade).value,
            "grade_confirmed_at": None,
            "declared_specialization": p.declared_specialization,
            "declared_grade": p.declared_grade,
            "declared_at": as_msk(p.declared_at),
            "created_at": as_msk(p.created_at),
            "blocked": user.blocked,
        }
        record["profile_completeness"] = profile_completeness(record)
        return record

    async def replace_stack(self, candidate_id: int, codes: list[str]) -> None:
        await self.session.execute(
            delete(candidate_skills).where(candidate_skills.c.candidate_id == candidate_id)
        )
        if codes:
            await self.session.execute(
                insert(candidate_skills),
                [
                    {"candidate_id": candidate_id, "skill_code": code, "position": pos}
                    for pos, code in enumerate(codes)
                ],
            )

    # ---------- банк кандидатов ----------

    async def search_ids(
        self,
        *,
        specialization: str | None,
        grade: str | None,
        category: str | None,
        skills: list[str],
        has_fsp: bool | None,
        work_format: str | None,
        city: str | None,
        sort: str,
        page: int,
        page_size: int | None,
    ) -> tuple[list[int], int]:
        """Кандидаты банка по фильтрам: id страницы и общее число.

        `page_size=None` — все id без страниц (для сортировки по соответствию потребности,
        которая считается в Python той же формулой, что подборка)."""
        cp = CandidateProfile
        conditions = searchable_conditions()
        if specialization:
            conditions.append(cp.specialization == specialization)
        if grade:
            conditions.append(cp.grade == grade)
        if category:
            conditions.append(cp.category == category)
        for code in skills:
            conditions.append(
                exists().where(
                    candidate_skills.c.candidate_id == cp.id, candidate_skills.c.skill_code == code
                )
            )
        if has_fsp is not None:
            conditions.append(has_fsp_condition() if has_fsp else ~has_fsp_condition())
        if work_format:
            conditions.append(literal(work_format) == any_(cp.work_formats))
        if city:
            conditions.append(cp.city == city)
            conditions.append(cp.privacy["show_city"].as_boolean().is_(True))

        base = select(cp.id).join(User, User.id == cp.user_id).where(*conditions)
        total = int(
            await self.session.scalar(select(func.count()).select_from(base.subquery())) or 0
        )
        orders: dict[str, list[Any]] = {
            "theta": [cp.theta.desc().nulls_last()],
            "fsp": [func.coalesce(cp.fsp_score, 0).desc()],
            "freshness": [cp.freshness.desc()],
            "recent": [cp.last_test_at.desc().nulls_last()],
        }
        order = orders.get(sort, orders["theta"])
        stmt = base.order_by(*order, cp.id)
        if page_size is not None:
            stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        ids = list((await self.session.scalars(stmt)).all())
        return ids, total

    async def count_searchable_in_category(self, category: str) -> int:
        stmt = (
            select(func.count())
            .select_from(CandidateProfile)
            .join(User, User.id == CandidateProfile.user_id)
            .where(*searchable_conditions(), CandidateProfile.category == category)
        )
        return int(await self.session.scalar(stmt) or 0)

    # ---------- связанные записи ----------

    async def invitations(self, candidate_id: int) -> list[Record]:
        rows = (
            await self.session.execute(
                select(Invitation, Company.name)
                .join(Company, Company.id == Invitation.company_id)
                .where(Invitation.candidate_id == candidate_id)
                .order_by(Invitation.created_at.desc(), Invitation.id.desc())
            )
        ).all()
        return [
            {
                "id": inv.id,
                "company_id": inv.company_id,
                "company_name": name,
                "salary_from": inv.salary_from,
                "salary_to": inv.salary_to,
                "status": inv.status,
                "created_at": as_msk(inv.created_at),
            }
            for inv, name in rows
        ]

    async def contacts_visible(self, candidate_id: int, company_id: int) -> bool:
        accepted = exists().where(
            Invitation.candidate_id == candidate_id,
            Invitation.company_id == company_id,
            Invitation.status == "accepted",
        )
        applied = exists().where(
            Application.candidate_id == candidate_id,
            Application.vacancy_id == Vacancy.id,
            Vacancy.company_id == company_id,
        )
        return bool(await self.session.scalar(select(accepted | applied)))

    async def task_offers(self, candidate_id: int) -> list[Record]:
        """Задачи недели на выбор (без ответа, срок не вышел), ближайший срок — первым."""
        rows = await self.session.execute(
            select(TaskSubmission, RegularTask.title, Company.name)
            .join(RegularTask, RegularTask.id == TaskSubmission.task_id)
            .join(Company, Company.id == RegularTask.company_id)
            .where(
                TaskSubmission.candidate_id == candidate_id,
                TaskSubmission.status == "assigned",
                TaskSubmission.due_at > now_msk(),
            )
            .order_by(TaskSubmission.due_at, TaskSubmission.id)
        )
        return [
            {
                "submission_id": sub.id,
                "title": title,
                "company_name": company,
                "due_at": as_msk(sub.due_at),
            }
            for sub, title, company in rows.all()
        ]

    async def test_sessions(self, candidate_id: int) -> list[TestSession]:
        rows = await self.session.scalars(
            select(TestSession)
            .where(TestSession.candidate_id == candidate_id)
            .order_by(TestSession.started_at.desc(), TestSession.id.desc())
        )
        return list(rows.all())

    async def grade_history(self, candidate_id: int) -> list[GradeHistory]:
        rows = await self.session.scalars(
            select(GradeHistory)
            .where(GradeHistory.candidate_id == candidate_id)
            .order_by(GradeHistory.at, GradeHistory.id)
        )
        return list(rows.all())

    # ---------- согласия ----------

    async def active_publication_consents(self, user_id: int) -> list[Consent]:
        rows = await self.session.scalars(
            select(Consent).where(
                Consent.user_id == user_id,
                Consent.type == "publication",
                Consent.granted.is_(True),
                Consent.revoked_at.is_(None),
            )
        )
        return list(rows.all())


def session_grade(s: TestSession) -> str | None:
    """Грейд сессии для результата и истории тестов.

    Тест подтверждён — присвоенный грейд (тот, что в профиле видит работодатель), даже если
    уровень по θ выше: это лишь повод предложить тест на грейд выше. Не подтверждён — уровень
    по θ. Старые сессии хранили в `result_grade` уровень по θ, поэтому сначала смотрим решение.
    """
    if s.passed:
        decision = (s.engine_state or {}).get("decision") or {}
        granted = decision.get("granted_grade")
        if isinstance(granted, str) and granted:
            return granted
    return s.result_grade


def session_record(s: TestSession) -> dict[str, Any]:
    """Сессия теста в форме контракта (`TestSession`)."""
    state = s.engine_state or {}
    grade = session_grade(s)
    return {
        "id": s.id,
        "candidate_id": s.candidate_id,
        "specialization": s.specialization,
        "target_grade": s.target_grade,
        "kind": s.kind,
        "status": s.status,
        "started_at": as_msk(s.started_at),
        "finished_at": as_msk(s.finished_at),
        "items_answered": s.items_answered,
        "max_items": s.max_items,
        "theta": s.theta,
        "se": s.se,
        "ci_low": state.get("ci_low"),
        "ci_high": state.get("ci_high"),
        "result_grade": grade,
        "result_category": f"{s.specialization}:{grade}" if grade else None,
        "passed": s.passed,
        "topic_scores": list(s.topic_scores or []),
    }


def history_record(h: GradeHistory) -> dict[str, Any]:
    return {
        "id": h.id,
        "candidate_id": h.candidate_id,
        "at": as_msk(h.at),
        "event": h.event,
        "specialization": h.specialization,
        "grade_from": h.grade_from,
        "grade_to": h.grade_to,
        "test_session_id": h.test_session_id,
        "comment": h.comment,
    }
