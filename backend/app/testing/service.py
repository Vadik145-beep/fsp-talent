"""Опрос, сессии теста, результат и грейд — заглушки до волны 3a.

Настоящий адаптивный движок (θ, EAP, информация Фишера) — `app/testing/engine` (трек 0b).
Здесь задачи берутся из предпросмотров банка (`items.json`), без правильных ответов.
"""

from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from app.candidates.service import CandidateService
from app.catalog.repository import CatalogRepository
from app.common.enums import (
    GradeCode,
    ItemStatus,
    SpecializationCode,
    TestSessionKind,
    TestSessionStatus,
)
from app.common.fixtures import Record
from app.core.errors import AppError, not_found
from app.testing.repository import TestingRepository
from app.testing.schemas import AnswerSubmit, SurveySubmit, TestSessionCreate

GRADE_ORDER = [g.value for g in GradeCode]
ITEM_VIEW_FIELDS = (
    "instance_id",
    "format",
    "topic",
    "topic_label",
    "prompt",
    "code",
    "options",
    "steps",
    "unit",
    "time_limit_sec",
)


def _now() -> datetime:
    return datetime.now().astimezone()


class TestingService:
    __test__ = False

    def __init__(
        self,
        repo: TestingRepository | None = None,
        candidates: CandidateService | None = None,
        catalog: CatalogRepository | None = None,
    ) -> None:
        self.repo = repo or TestingRepository()
        self.candidates = candidates or CandidateService()
        self.catalog = catalog or CatalogRepository()

    # ---------- опрос ----------

    def survey(self) -> list[Record]:
        return self.repo.survey_questions()

    def submit_survey(self, body: SurveySubmit) -> dict[str, Any]:
        options = {
            opt["id"]: opt for q in self.repo.survey_questions() for opt in q.get("options", [])
        }
        votes: Counter[str] = Counter()
        for answer in body.answers:
            for option_id in answer.option_ids:
                for spec in options.get(option_id, {}).get("specializations", []):
                    votes[spec] += 1
        if not votes:
            votes[SpecializationCode.backend] = 1
        total = sum(votes.values())
        ranked = votes.most_common()
        best = ranked[0][0]
        chosen = {o for a in body.answers for o in a.option_ids}
        grade = (
            GradeCode.senior
            if "q4_5" in chosen
            else GradeCode.middle
            if "q4_3" in chosen
            else GradeCode.junior
            if "q4_1" in chosen
            else GradeCode.intern
        )
        topics = [t["id"] for t in self.repo.topics() if t["specialization"] == best][:4]
        return {
            "recommended_specialization": best,
            "alternatives": [
                {"specialization": spec, "score": round(n / total, 2)} for spec, n in ranked[:3]
            ],
            "suggested_grade": grade,
            "topics": topics,
            "explanation": [
                f"Ответы чаще всего указывали на «{best}»: {ranked[0][1]} из {total}",
                "Рекомендация не оценивается баллом — специализацию можно поменять",
            ],
        }

    # ---------- сессии ----------

    def _item_view(self, specialization: str, number: int) -> dict[str, Any] | None:
        pool = [
            it
            for it in self.repo.items()
            if it["specialization"] == specialization and it["status"] == ItemStatus.active
        ]
        if not pool:
            return None
        item = pool[(number - 1) % len(pool)]
        variant = item["preview_variants"][(number - 1) % len(item["preview_variants"])]
        return {key: variant.get(key) for key in ITEM_VIEW_FIELDS}

    def _own_session(self, session_id: int, candidate_id: int) -> Record:
        session = self.repo.session(session_id)
        if session is None or session["candidate_id"] != candidate_id:
            raise not_found("test_session", session_id)
        return session

    def sessions(self, candidate_id: int) -> list[Record]:
        return sorted(self.repo.sessions(candidate_id), key=lambda s: s["started_at"], reverse=True)

    def state(self, session: Record) -> dict[str, Any]:
        in_progress = session["status"] == TestSessionStatus.in_progress
        number = session["items_answered"] + 1 if in_progress else session["items_answered"]
        item = self._item_view(session["specialization"], number) if in_progress else None
        return {
            "session": session,
            "current_item": item,
            "item_number": number,
            "time_left_sec": item["time_limit_sec"] if item else None,
        }

    def get_state(self, session_id: int, candidate_id: int) -> dict[str, Any]:
        return self.state(self._own_session(session_id, candidate_id))

    def create(self, body: TestSessionCreate, candidate_id: int) -> dict[str, Any]:
        cand = self.candidates.get_or_404(candidate_id)
        if any(
            s["status"] == TestSessionStatus.in_progress for s in self.repo.sessions(candidate_id)
        ):
            raise AppError(409, "session_in_progress", "Сначала завершите начатый тест")
        if body.kind != TestSessionKind.placement and cand.get("grade_changed_at"):
            cooldown = int(self.catalog.platform_settings().get("grade_change_cooldown_days", 90))
            available = datetime.fromisoformat(cand["grade_changed_at"]) + timedelta(days=cooldown)
            if available > _now():
                raise AppError(
                    409,
                    "cooldown_active",
                    "Сменить грейд можно не чаще раза в 90 дней",
                    {"available_at": available.isoformat()},
                )
        session = {
            "id": self.repo.next_session_id(),
            "candidate_id": candidate_id,
            "specialization": body.specialization,
            "target_grade": body.target_grade,
            "kind": body.kind,
            "status": TestSessionStatus.in_progress,
            "started_at": _now().isoformat(),
            "items_answered": 0,
            "max_items": int(self.catalog.platform_settings().get("cat_max_items", 15)),
            "topic_scores": [],
        }
        return self.state(session)

    def answer(self, session_id: int, candidate_id: int, body: AnswerSubmit) -> dict[str, Any]:
        session = self._own_session(session_id, candidate_id)
        if session["status"] != TestSessionStatus.in_progress:
            raise AppError(409, "session_finished", "Тест уже завершён")
        answered = session["items_answered"] + 1
        finished = answered >= session["max_items"]
        return {
            "session_id": session_id,
            "answered": answered,
            "finished": finished,
            "next_item": None
            if finished
            else self._item_view(session["specialization"], answered + 1),
            "time_expired": False,
        }

    def result(self, session_id: int, candidate_id: int) -> dict[str, Any]:
        s = self._own_session(session_id, candidate_id)
        if s["status"] != TestSessionStatus.finished:
            raise AppError(409, "session_not_finished", "Тест ещё не завершён")
        scores = s["topic_scores"]
        category = self.catalog.category(s["result_category"])
        target_idx = GRADE_ORDER.index(s["target_grade"])
        if s["passed"]:
            if target_idx < len(GRADE_ORDER) - 1 and (s["ci_low"] or 0) > 0.3:
                action, message = (
                    "offer_higher",
                    "Уверенный результат: можно попробовать грейд выше",
                )
            else:
                action, message = "stay", "Грейд подтверждён"
        else:
            action, message = "offer_lower", "Заявленный грейд не подтверждён — пройдите тест ниже"
        return {
            "session_id": s["id"],
            "specialization": s["specialization"],
            "target_grade": s["target_grade"],
            "result_grade": s["result_grade"],
            "category": s["result_category"],
            "category_label": (category or {}).get("label", s["result_category"]),
            "theta": s["theta"],
            "se": s["se"],
            "ci_low": s["ci_low"],
            "ci_high": s["ci_high"],
            "passed": s["passed"],
            "items_answered": s["items_answered"],
            "finished_at": s["finished_at"],
            "topic_scores": scores,
            "strong_topics": [t["label"] for t in scores if t["level"] == "strong"],
            "weak_topics": [t["label"] for t in scores if t["level"] == "weak"],
            "recommendation": {"action": action, "message": message, "available_at": None},
        }

    # ---------- грейд ----------

    def grade_status(self, candidate_id: int) -> dict[str, Any]:
        cand = self.candidates.get_or_404(candidate_id)
        settings = self.catalog.platform_settings()
        cooldown = int(settings.get("grade_change_cooldown_days", 90))
        retry = int(settings.get("retry_cooldown_days", 30))
        changed = cand.get("grade_changed_at")
        available = datetime.fromisoformat(changed) + timedelta(days=cooldown) if changed else None
        open_now = available is None or available <= _now()
        grade = cand.get("grade")
        return {
            "candidate_id": candidate_id,
            "specialization": cand.get("specialization"),
            "grade": grade,
            "category": cand.get("category"),
            "category_label": cand.get("category_label"),
            "theta": cand.get("theta"),
            "grade_changed_at": changed,
            "grade_change_cooldown_days": cooldown,
            "retry_cooldown_days": retry,
            "can_test_lower": bool(grade) and grade != GradeCode.intern and open_now,
            "lower_available_at": None if open_now else available,
            "can_test_higher": bool(grade) and grade != GradeCode.senior and open_now,
            "higher_available_at": None if open_now else available,
            "history": sorted(self.repo.grade_history(candidate_id), key=lambda h: h["at"]),
            "tests": self.sessions(candidate_id),
        }
