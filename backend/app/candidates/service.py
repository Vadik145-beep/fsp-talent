"""Профиль кандидата и правила видимости для рекрутера.

Главное правило [ТЗ 2.1, 2.2 п.2]: рекрутер видит обезличенную карточку. ФИО и контакты —
только если кандидат принял приглашение компании рекрутера или сам откликнулся
на её вакансию. Минимальная зарплата не уходит рекрутеру никогда.

`CandidateProfileService` работает с БД. `CandidateService` (фикстуры) и функции
`is_searchable` / `to_card` / `to_contacts` нужны модулям, которые ещё на фикстурах (волна 3).
"""

from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.audit import write_audit
from app.candidates.grading import grade_status
from app.candidates.models import CandidateProfile
from app.candidates.repository import CandidateDb, CandidateRepository, session_grade
from app.candidates.schemas import CandidateProfileUpdate, PrivacySettings
from app.catalog.clock import as_msk, now_msk
from app.catalog.repository import CatalogDb
from app.common.enums import (
    ACTIVE_INVITATION_STATUSES,
    ConsentType,
    GradeStatusCode,
    InvitationStatus,
)
from app.common.fixtures import Record
from app.core.errors import AppError, not_found
from app.core.security import CurrentUser
from app.fsp.scoring import fsp_profile_note
from app.fsp.service import fsp_summaries
from app.testing.engine.constants import GRADE_LABELS
from app.users.models import Consent, User

# Поля карточки, которые рекрутер видит всегда (без ФИО, контактов, зарплаты, ФСП ID)
CARD_FIELDS = (
    "id",
    "pseudonym",
    "specialization",
    "grade",
    "category",
    "category_label",
    "theta",
    "stack",
    "work_formats",
    "roles_in_team",
    "topic_scores",
    "freshness",
)


def is_searchable(candidate: Record) -> bool:
    """В выдаче: есть грейд, дано согласие на публикацию, поиск не на паузе [T2.4, T3.4]."""
    return (
        bool(candidate.get("grade"))
        and bool(candidate.get("publication_consent"))
        and not candidate.get("job_search_paused")
        and not candidate.get("blocked")
    )


def to_card(candidate: Record) -> dict[str, Any]:
    privacy = candidate.get("privacy") or {}
    card: dict[str, Any] = {key: candidate.get(key) for key in CARD_FIELDS}
    card["city"] = candidate.get("city") if privacy.get("show_city") else None
    card["experience_years"] = (
        candidate.get("experience_years") if privacy.get("show_experience") else None
    )
    card["links"] = candidate.get("links") if privacy.get("show_links") else None
    card["has_fsp"] = bool(candidate.get("fsp_id"))
    show_fsp = privacy.get("show_fsp_achievements", True)
    card["fsp_score"] = candidate.get("fsp_score") if show_fsp else None
    card["fsp_badges"] = candidate.get("fsp_badges", []) if show_fsp else []
    return card


def to_contacts(candidate: Record) -> dict[str, Any]:
    return {
        "full_name": candidate["full_name"],
        "email": candidate["email"],
        "phone": candidate.get("phone"),
        "telegram": candidate.get("telegram"),
    }


class CandidateService:
    """Профили из фикстур — для модулей, которые ещё на фикстурах (волна 3)."""

    def __init__(self, repo: CandidateRepository | None = None) -> None:
        self.repo = repo or CandidateRepository()

    def get_or_404(self, candidate_id: int) -> Record:
        candidate = self.repo.get(candidate_id)
        if candidate is None:
            raise not_found("candidate", candidate_id)
        return candidate


class CandidateProfileService:
    """Кабинет кандидата и банк кандидатов на БД."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.db = CandidateDb(session)
        self.catalog = CatalogDb(session)

    async def get_or_404(self, candidate_id: int) -> Record:
        record = await self.db.record(candidate_id)
        if record is None:
            raise not_found("candidate", candidate_id)
        return record

    # ---------- свой профиль ----------

    async def update_profile(self, candidate_id: int, body: CandidateProfileUpdate) -> Record:
        profile = await self.db.profile(candidate_id)
        if profile is None:
            raise not_found("candidate", candidate_id)
        stack = list(dict.fromkeys(code.strip().lower() for code in body.stack))
        known = await self.catalog.existing_skill_codes(stack)
        unknown = [c for c in stack if c not in known]
        if unknown:
            raise AppError(
                422,
                "unknown_skills",
                "Технологий нет в справочнике стека — выберите из списка",
                {"skills": unknown},
            )
        user = await self.session.get(User, profile.user_id)
        assert user is not None
        user.full_name = body.full_name.strip()
        profile.phone = body.phone
        profile.telegram = body.telegram
        profile.city = body.city
        profile.work_formats = [str(f) for f in dict.fromkeys(body.work_formats)]
        profile.roles_in_team = body.roles_in_team
        profile.experience_years = body.experience_years
        profile.soft_skills = body.soft_skills
        profile.about = body.about
        profile.links = [link.model_dump(mode="json") for link in body.links]
        profile.min_salary = body.min_salary
        await self.db.replace_stack(candidate_id, stack)
        await self.session.commit()
        return await self.get_or_404(candidate_id)

    async def dashboard(self, candidate_id: int) -> dict[str, Any]:
        cand = await self.get_or_404(candidate_id)
        invitations = await self.db.invitations(candidate_id)
        # «Новые» — только непрочитанные: просмотренные и отвеченные бейдж не считает.
        new = [i for i in invitations if i["status"] == InvitationStatus.sent]
        hints: list[str] = []
        if not cand.get("fsp_id"):
            hints.append(
                "Привяжите ФСП ID — достижения появятся в профиле с отметкой «подтверждено ФСП»"
            )
        if not cand.get("links"):
            hints.append("Добавьте ссылку на GitHub — профиль станет полнее")
        if cand.get("grade_status") == GradeStatusCode.unconfirmed:
            label = GRADE_LABELS.get(cand.get("declared_grade") or "", "")
            hints.append(
                f"Грейд {label} не подтверждён — пройдите тест: официально грейд присваивается "
                "только по результату теста, и только тогда профиль попадает в выдачу"
            )
        elif not cand.get("grade"):
            hints.append("Пройдите тест, чтобы получить категорию и попасть в выдачу работодателям")
        if not cand.get("publication_consent"):
            hints.append(
                "Дайте согласие на публикацию профиля — без него работодатели вас не видят"
            )
        offers = await self.db.task_offers(candidate_id)
        return {
            "full_name": cand["full_name"],
            "category": cand.get("category"),
            "category_label": cand.get("category_label"),
            "grade": cand.get("grade"),
            "theta": cand.get("theta"),
            "grade_status": cand.get("grade_status"),
            "grade_confirmed_at": cand.get("grade_confirmed_at"),
            "declared_specialization": cand.get("declared_specialization"),
            "declared_grade": cand.get("declared_grade"),
            "onboarding_completed": bool(cand.get("grade")),
            "new_invitations_count": len(new),
            "recent_invitations": invitations[:3],
            "active_task": offers[0] if offers else None,
            "task_offers": offers,
            "profile_completeness": cand["profile_completeness"],
            "fsp_linked": bool(cand.get("fsp_id")),
            "hints": hints,
        }

    # ---------- настройки ----------

    @staticmethod
    def _settings(cand: Record) -> dict[str, Any]:
        return {
            "privacy": cand["privacy"],
            "job_search_paused": cand["job_search_paused"],
            "publication_consent": cand["publication_consent"],
            "fsp_linked": bool(cand.get("fsp_id")),
            "fsp_id": cand.get("fsp_id"),
        }

    async def settings(self, candidate_id: int) -> dict[str, Any]:
        return self._settings(await self.get_or_404(candidate_id))

    async def update_privacy(self, candidate_id: int, body: PrivacySettings) -> dict[str, Any]:
        profile = await self.db.profile(candidate_id)
        if profile is None:
            raise not_found("candidate", candidate_id)
        profile.privacy = body.model_dump()
        await self.session.commit()
        return await self.settings(candidate_id)

    async def update_job_search(self, candidate_id: int, paused: bool) -> dict[str, Any]:
        profile = await self.db.profile(candidate_id)
        if profile is None:
            raise not_found("candidate", candidate_id)
        profile.job_search_paused = paused
        await self.session.commit()
        return await self.settings(candidate_id)

    async def set_publication_consent(
        self, candidate_id: int, granted: bool, actor: CurrentUser | None = None
    ) -> dict[str, Any]:
        """Согласие на публикацию [T2.4]: флаг в профиле + запись в consents.
        Отзыв действует сразу — кандидат пропадает из банка кандидатов и подборок."""
        profile = await self.db.profile(candidate_id)
        if profile is None:
            raise not_found("candidate", candidate_id)
        await apply_publication_consent(self.session, profile.user_id, granted, actor)
        await self.session.commit()
        return await self.settings(candidate_id)

    # ---------- категория и грейд ----------

    async def declare_grade(
        self, candidate_id: int, specialization: str, grade: str
    ) -> dict[str, Any]:
        """Соискатель сам выбрал грейд (онбординг): статус «грейд не подтверждён» (FTT.4).

        Официальный грейд (`grade`) не меняется — его присваивает только тест.
        """
        profile = await self.db.profile(candidate_id)
        if profile is None:
            raise not_found("candidate", candidate_id)
        declare(profile, specialization, grade)
        await self.session.commit()
        return await self.grade(candidate_id)

    async def grade(self, candidate_id: int, today: date | None = None) -> dict[str, Any]:
        cand = await self.get_or_404(candidate_id)
        sessions = await self.db.test_sessions(candidate_id)
        history = await self.db.grade_history(candidate_id)
        settings = await self.catalog.settings()
        return grade_status(cand, sessions, history, settings, today or now_msk().date())

    # ---------- банк кандидатов (рекрутер) ----------

    async def search(self, *, page: int = 1, page_size: int = 20, **filters: Any) -> dict[str, Any]:
        ids, total = await self.db.search_ids(page=page, page_size=page_size, **filters)
        records = await self.db.records(ids)
        return {
            "items": [to_card(records[i]) for i in ids if i in records],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def anonymous_profile(self, candidate_id: int, company_id: int) -> dict[str, Any]:
        cand = await self.db.record(candidate_id)
        if cand is None:
            raise not_found("candidate", candidate_id)
        visible = await self.db.contacts_visible(candidate_id, company_id)
        if not is_searchable(cand) and not visible:
            # профиль скрыт (нет согласия / пауза поиска / блокировка) — для рекрутера его нет
            raise not_found("candidate", candidate_id)
        company_invs = [
            i for i in await self.db.invitations(candidate_id) if i["company_id"] == company_id
        ]
        last_inv = company_invs[0] if company_invs else None
        # История тестов — присвоенная категория, как в профиле (не уровень по θ)
        history = [
            {
                "date": as_msk(s.finished_at).date(),  # type: ignore[union-attr]
                "category": f"{s.specialization}:{grade}",
                "theta": s.theta,
            }
            for s in sorted(await self.db.test_sessions(candidate_id), key=lambda s: s.id)
            if s.status == "finished" and s.passed and s.finished_at and (grade := session_grade(s))
        ]
        profile = to_card(cand)
        note = None
        if cand.get("fsp_id") and (cand.get("privacy") or {}).get("show_fsp_achievements", True):
            summary = (await fsp_summaries(self.session, [candidate_id]))[candidate_id]
            note = fsp_profile_note(summary.achievements, cand.get("specialization"))
        profile.update(
            fsp_profile_note=note,
            soft_skills=cand.get("soft_skills", []),
            test_history=history,
            invitation_id=last_inv["id"] if last_inv else None,
            invitation_status=last_inv["status"] if last_inv else None,
            contacts_visible=visible,
            contacts=to_contacts(cand) if visible else None,
            can_invite=is_searchable(cand)
            and not (last_inv and last_inv["status"] in ACTIVE_INVITATION_STATUSES),
        )
        return profile


def declare(profile: CandidateProfile, specialization: str, grade: str) -> None:
    """Запомнить заявленный грейд (онбординг или старт теста). Коммит — за вызывающим."""
    profile.declared_specialization = specialization
    profile.declared_grade = grade
    profile.declared_at = now_msk()


async def apply_publication_consent(
    session: AsyncSession, user_id: int, granted: bool, actor: CurrentUser | None = None
) -> None:
    """Выдать/отозвать согласие на публикацию: флаг профиля + запись в consents + журнал.

    Общая точка для кабинета кандидата и модуля согласий (users): кто бы ни менял согласие,
    флаг `candidate_profiles.publication_consent` и таблица `consents` остаются согласованы.
    Коммит — за вызывающим.
    """
    db = CandidateDb(session)
    profile = await db.by_user(user_id)
    now = now_msk()
    active = await db.active_publication_consents(user_id)
    if granted:
        if not active:
            version = str((await CatalogDb(session).settings()).get("consent_version", ""))
            session.add(
                Consent(
                    user_id=user_id,
                    type=ConsentType.publication.value,
                    version=version or now.date().isoformat(),
                    granted=True,
                    granted_at=now,
                    revoked_at=None,
                )
            )
    else:
        for consent in active:
            consent.granted = False
            consent.revoked_at = now
    changed = profile is not None and profile.publication_consent != granted
    if profile is not None:
        profile.publication_consent = granted
    if changed or (not granted and active):
        await write_audit(
            session,
            actor,
            "consent_granted" if granted else "consent_revoked",
            "consent",
            profile.id if profile else None,
            "Дано согласие на публикацию профиля"
            if granted
            else "Отозвано согласие на публикацию профиля",
            {"type": ConsentType.publication.value, "user_id": user_id},
        )
