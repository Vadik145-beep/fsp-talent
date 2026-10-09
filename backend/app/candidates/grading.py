"""Экран «Категория и грейд» (T3.5): статус, история, доступность теста ниже/выше.

Доступность считает движок (`app.testing.engine.grading.can_attempt`):
- смена грейда — не чаще раза в N дней (`grade_change_cooldown_days`, по умолчанию 90);
  первое присвоение грейда сменой не считается;
- повтор неудачной попытки на тот же грейд — не раньше чем через M дней
  (`retry_cooldown_days`, по умолчанию 30).
Дата последней смены — последнее событие `grade_changed` в истории, где грейд действительно
поменялся (`grade_from` → `grade_to`).
"""

from datetime import date, datetime
from typing import Any

from app.candidates.repository import history_record, session_record
from app.catalog.clock import MSK, as_msk, start_of_day_msk
from app.common.fixtures import Record
from app.testing.engine.constants import GRADES
from app.testing.engine.grading import Attempt, can_attempt, is_grade_change
from app.testing.models import GradeHistory, TestSession


def _neighbour(grade: str, step: int) -> str | None:
    i = GRADES.index(grade) + step
    return GRADES[i] if 0 <= i < len(GRADES) else None


def last_grade_change(history: list[GradeHistory]) -> datetime | None:
    changes = [
        h.at
        for h in history
        if h.event == "grade_changed" and is_grade_change(h.grade_from, h.grade_to)
    ]
    return as_msk(max(changes)) if changes else None


def _msk_date(value: datetime) -> date:
    return value.astimezone(MSK).date()


def attempts_of(sessions: list[TestSession]) -> list[Attempt]:
    return [
        Attempt(on=_msk_date(s.finished_at), target_grade=s.target_grade, passed=bool(s.passed))
        for s in sessions
        if s.status == "finished" and s.finished_at is not None and s.passed is not None
    ]


def grade_status(
    cand: Record,
    sessions: list[TestSession],
    history: list[GradeHistory],
    settings: Record,
    today: date,
) -> dict[str, Any]:
    cooldown = int(settings.get("grade_change_cooldown_days", 90))
    retry = int(settings.get("retry_cooldown_days", 30))
    grade: str | None = cand.get("grade")
    changed_at = last_grade_change(history)
    changed = changed_at.date() if changed_at else None
    attempts = attempts_of(sessions)

    def option(step: int) -> dict[str, Any] | None:
        target = _neighbour(grade, step) if grade else None
        if grade is None or target is None:
            return None
        verdict = can_attempt(
            target,
            today,
            current_grade=grade,
            last_grade_change=changed,
            attempts=attempts,
            change_cooldown_days=cooldown,
            retry_cooldown_days=retry,
        )
        return {
            "target_grade": target,
            "allowed": verdict.allowed,
            "code": verdict.code,
            "reason": verdict.reason,
            "available_at": start_of_day_msk(verdict.available_from),
        }

    lower, higher = option(-1), option(+1)
    return {
        "candidate_id": cand["id"],
        "specialization": cand.get("specialization"),
        "grade": grade,
        "category": cand.get("category"),
        "category_label": cand.get("category_label"),
        "theta": cand.get("theta"),
        "grade_changed_at": changed_at,
        "grade_status": cand.get("grade_status", "none"),
        "grade_confirmed_at": cand.get("grade_confirmed_at"),
        "declared_specialization": cand.get("declared_specialization"),
        "declared_grade": cand.get("declared_grade"),
        "declared_at": cand.get("declared_at"),
        "grade_change_cooldown_days": cooldown,
        "retry_cooldown_days": retry,
        "can_test_lower": bool(lower and lower["allowed"]),
        "lower_available_at": lower["available_at"] if lower else None,
        "can_test_higher": bool(higher and higher["allowed"]),
        "higher_available_at": higher["available_at"] if higher else None,
        "lower": lower,
        "higher": higher,
        "history": [history_record(h) for h in history],
        "tests": [session_record(s) for s in sessions],
    }
