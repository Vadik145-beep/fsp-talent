"""Грейд по θ, решение по итогам теста и правила частоты попыток.

Принудительного понижения нет:
- θ ниже порога заявленного грейда → грейд не присваивается (остаётся прежний, если был),
  кандидату предлагается тест на грейд ниже;
- уверенно выше (нижняя граница доверительного интервала выше порога следующего грейда) →
  заявленный грейд присваивается и предлагается тест на грейд выше.

Частота (чистые функции от дат):
- смена грейда — не чаще раза в 90 дней (первое присвоение сменой не считается);
- повтор неудачной попытки на тот же грейд — не раньше чем через 30 дней.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from .constants import GRADE_LABELS, GRADES, check_grade, grade_index

GRADE_CHANGE_COOLDOWN_DAYS = 90
FAILED_RETRY_COOLDOWN_DAYS = 30


@dataclass(frozen=True)
class GradeThresholds:
    """Нижние пороги θ для грейдов. intern — всё, что ниже junior."""

    junior: float = -1.0
    middle: float = 0.0
    senior: float = 1.0

    def __post_init__(self) -> None:
        if not self.junior < self.middle < self.senior:
            raise ValueError("Пороги должны возрастать: junior < middle < senior")

    def lower_bound(self, grade: str) -> float:
        """Минимальная θ для грейда (для intern — минус бесконечность)."""
        check_grade(grade)
        if grade == "intern":
            return -math.inf
        bound: float = getattr(self, grade)
        return bound

    def grade_for(self, theta: float) -> str:
        if theta >= self.senior:
            return "senior"
        if theta >= self.middle:
            return "middle"
        if theta >= self.junior:
            return "junior"
        return "intern"

    def cuts(self) -> tuple[float, float, float]:
        return self.junior, self.middle, self.senior


DEFAULT_THRESHOLDS = GradeThresholds()


def grade_for_theta(theta: float, thresholds: GradeThresholds = DEFAULT_THRESHOLDS) -> str:
    return thresholds.grade_for(theta)


def _neighbour(grade: str, step: int) -> str | None:
    i = grade_index(grade) + step
    return GRADES[i] if 0 <= i < len(GRADES) else None


Outcome = Literal["passed_claimed", "suggest_lower", "suggest_higher"]


@dataclass(frozen=True)
class GradeDecision:
    outcome: Outcome
    claimed_grade: str
    estimated_grade: str  # грейд по точечной оценке θ
    granted_grade: str | None  # что присваиваем: заявленный или прежний (None — пока нет)
    suggested_grade: str | None  # на какой грейд предложить следующий тест
    theta: float
    ci_low: float
    ci_high: float
    reason: str


def lower_test_needed(current_grade: str | None, suggested: str | None) -> bool:
    """Предлагать ли тест на грейд ниже: только если такого или более высокого грейда ещё нет."""
    if suggested is None:
        return False
    return current_grade is None or grade_index(current_grade) < grade_index(suggested)


def keep_grade_reason(
    claimed_grade: str, current_grade: str | None, retry_days: int = FAILED_RETRY_COOLDOWN_DAYS
) -> str:
    """Не прошёл тест выше, но свой грейд уже есть: грейд остаётся, повтор — после кулдауна."""
    label = GRADE_LABELS[claimed_grade]
    keep = f", ваш грейд {GRADE_LABELS[current_grade]} остаётся" if current_grade else ""
    return f"{label} не подтверждён{keep}. Повторить тест на {label} можно через {retry_days} дней."


def decide(
    theta: float,
    se: float,
    claimed_grade: str,
    *,
    current_grade: str | None = None,
    thresholds: GradeThresholds = DEFAULT_THRESHOLDS,
    ci_z: float = 1.645,
) -> GradeDecision:
    """Решение по итогам теста на заявленный грейд."""
    check_grade(claimed_grade)
    if current_grade is not None:
        check_grade(current_grade)
    lo, hi = theta - ci_z * se, theta + ci_z * se
    estimated = thresholds.grade_for(theta)
    label = GRADE_LABELS[claimed_grade]
    if theta < thresholds.lower_bound(claimed_grade):
        # для intern порог −∞, поэтому сюда попадаем только с junior и выше
        suggested = _neighbour(claimed_grade, -1)
        if not lower_test_needed(current_grade, suggested):
            # грейд не ниже предлагаемого уже есть — тест на него ничего не даст
            return GradeDecision(
                outcome="suggest_lower",
                claimed_grade=claimed_grade,
                estimated_grade=estimated,
                granted_grade=current_grade,
                suggested_grade=None,
                theta=theta,
                ci_low=lo,
                ci_high=hi,
                reason=keep_grade_reason(claimed_grade, current_grade),
            )
        keep = f" Текущий грейд {GRADE_LABELS[current_grade]} сохраняется." if current_grade else ""
        return GradeDecision(
            outcome="suggest_lower",
            claimed_grade=claimed_grade,
            estimated_grade=estimated,
            granted_grade=current_grade,
            suggested_grade=suggested,
            theta=theta,
            ci_low=lo,
            ci_high=hi,
            reason=(
                f"Результат ниже порога грейда {label}. Грейд принудительно не понижается: "
                f"можно пройти тест на грейд "
                f"{GRADE_LABELS[suggested] if suggested else 'ниже'}.{keep}"
            ),
        )
    higher = _neighbour(claimed_grade, +1)
    if higher is not None and lo >= thresholds.lower_bound(higher):
        return GradeDecision(
            outcome="suggest_higher",
            claimed_grade=claimed_grade,
            estimated_grade=estimated,
            granted_grade=claimed_grade,
            suggested_grade=higher,
            theta=theta,
            ci_low=lo,
            ci_high=hi,
            reason=(
                f"Грейд {label} подтверждён, причём уверенно выше порога "
                f"{GRADE_LABELS[higher]}: можно пройти тест на грейд {GRADE_LABELS[higher]}."
            ),
        )
    return GradeDecision(
        outcome="passed_claimed",
        claimed_grade=claimed_grade,
        estimated_grade=estimated,
        granted_grade=claimed_grade,
        suggested_grade=None,
        theta=theta,
        ci_low=lo,
        ci_high=hi,
        reason=f"Грейд {label} подтверждён.",
    )


# --------------------------------------------------------------------------- частота попыток


@dataclass(frozen=True)
class Attempt:
    """Прошлая попытка теста."""

    on: date
    target_grade: str
    passed: bool


@dataclass(frozen=True)
class Eligibility:
    allowed: bool
    code: str  # "allowed" / "grade_change_cooldown" / "failed_retry_cooldown"
    reason: str
    available_from: date | None  # когда станет доступно (None — уже можно)


def can_attempt(
    target_grade: str,
    today: date,
    *,
    current_grade: str | None,
    last_grade_change: date | None,
    attempts: Sequence[Attempt] = (),
    change_cooldown_days: int = GRADE_CHANGE_COOLDOWN_DAYS,
    retry_cooldown_days: int = FAILED_RETRY_COOLDOWN_DAYS,
) -> Eligibility:
    """Можно ли сейчас начать тест на target_grade.

    `last_grade_change` — дата последней смены грейда (с одного на другой). Первое
    присвоение грейда сменой не считается: после первого теста кандидат может сразу
    пройти тест выше или ниже, а дальше действует ограничение 90 дней.
    """
    check_grade(target_grade)
    if current_grade is not None:
        check_grade(current_grade)
    blockers: list[tuple[date, str, str]] = []

    failed = [a.on for a in attempts if a.target_grade == target_grade and not a.passed]
    if failed:
        until = max(failed) + timedelta(days=retry_cooldown_days)
        if today < until:
            blockers.append(
                (
                    until,
                    "failed_retry_cooldown",
                    f"Повторить тест на {GRADE_LABELS[target_grade]} после неудачной попытки "
                    f"можно не раньше {until:%d.%m.%Y} (через {retry_cooldown_days} дней).",
                )
            )

    changes_grade = current_grade is not None and target_grade != current_grade
    if changes_grade and last_grade_change is not None:
        until = last_grade_change + timedelta(days=change_cooldown_days)
        if today < until:
            blockers.append(
                (
                    until,
                    "grade_change_cooldown",
                    f"Грейд можно менять не чаще раза в {change_cooldown_days} дней: "
                    f"следующая смена возможна с {until:%d.%m.%Y}.",
                )
            )

    if not blockers:
        return Eligibility(True, "allowed", "Тест доступен.", None)
    until, code, reason = max(blockers, key=lambda b: b[0])
    return Eligibility(False, code, reason, until)


def next_grade_change_date(
    last_grade_change: date | None, change_cooldown_days: int = GRADE_CHANGE_COOLDOWN_DAYS
) -> date | None:
    """С какой даты можно снова менять грейд (None — ограничения нет)."""
    if last_grade_change is None:
        return None
    return last_grade_change + timedelta(days=change_cooldown_days)


def is_grade_change(previous_grade: str | None, new_grade: str | None) -> bool:
    """Считается ли присвоение сменой грейда (для записи даты в grade_history)."""
    return previous_grade is not None and new_grade is not None and previous_grade != new_grade
