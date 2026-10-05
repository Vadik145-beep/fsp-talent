import math
from datetime import date, timedelta

import pytest

from app.testing.engine.grading import (
    Attempt,
    GradeThresholds,
    can_attempt,
    decide,
    grade_for_theta,
    is_grade_change,
    next_grade_change_date,
)

TODAY = date(2026, 10, 11)


def test_thresholds():
    t = GradeThresholds()
    assert [grade_for_theta(x) for x in (-1.01, -1.0, -0.01, 0.0, 0.99, 1.0)] == [
        "intern",
        "junior",
        "junior",
        "middle",
        "middle",
        "senior",
    ]
    assert t.lower_bound("intern") == -math.inf
    assert t.lower_bound("middle") == 0.0
    custom = GradeThresholds(junior=-0.5, middle=0.5, senior=1.5)
    assert custom.grade_for(1.0) == "middle"
    with pytest.raises(ValueError):
        GradeThresholds(junior=0.5, middle=0.0, senior=1.0)
    with pytest.raises(ValueError):
        t.lower_bound("lead")


def test_decide_suggest_lower_without_forced_downgrade():
    d = decide(-0.3, 0.3, "middle")
    assert d.outcome == "suggest_lower"
    assert d.suggested_grade == "junior"
    assert d.granted_grade is None  # первый тест: грейд пока не присвоен
    assert d.estimated_grade == "junior"
    d2 = decide(-0.3, 0.3, "middle", current_grade="middle")
    assert d2.granted_grade == "middle"  # действующий грейд не понижаем
    assert "не понижается" in d2.reason
    d3 = decide(-2.5, 0.3, "senior")
    assert d3.suggested_grade == "middle"  # предлагаем на один грейд ниже


def test_decide_intern_always_passes():
    d = decide(-3.5, 0.4, "intern")
    assert d.outcome == "passed_claimed" and d.granted_grade == "intern"


def test_decide_suggest_higher_only_when_confident():
    # нижняя граница 90% ДИ: 1.7 − 1.645·0.3 ≈ 1.21 ≥ 1.0 → уверенно выше
    d = decide(1.7, 0.3, "middle")
    assert d.outcome == "suggest_higher"
    assert d.granted_grade == "middle" and d.suggested_grade == "senior"
    # θ выше порога senior, но не уверенно
    d2 = decide(1.2, 0.3, "middle")
    assert d2.outcome == "passed_claimed" and d2.suggested_grade is None
    # выше senior некуда
    assert decide(3.0, 0.2, "senior").outcome == "passed_claimed"
    lo, hi = d.ci_low, d.ci_high
    assert lo < d.theta < hi


def test_can_attempt_first_time():
    e = can_attempt("middle", TODAY, current_grade=None, last_grade_change=None)
    assert e.allowed and e.code == "allowed" and e.available_from is None


def test_failed_retry_cooldown():
    attempts = [Attempt(TODAY - timedelta(days=10), "middle", passed=False)]
    e = can_attempt("middle", TODAY, current_grade=None, last_grade_change=None, attempts=attempts)
    assert not e.allowed and e.code == "failed_retry_cooldown"
    assert e.available_from == TODAY + timedelta(days=20)
    # на грейд ниже — сразу можно
    lower = can_attempt(
        "junior", TODAY, current_grade=None, last_grade_change=None, attempts=attempts
    )
    assert lower.allowed
    # через 30 дней — можно
    later = can_attempt(
        "middle",
        TODAY + timedelta(days=20),
        current_grade=None,
        last_grade_change=None,
        attempts=attempts,
    )
    assert later.allowed


def test_grade_change_cooldown():
    changed = TODAY - timedelta(days=40)
    e = can_attempt("senior", TODAY, current_grade="middle", last_grade_change=changed)
    assert not e.allowed and e.code == "grade_change_cooldown"
    assert e.available_from == changed + timedelta(days=90)
    assert "90" in e.reason
    # подтверждение текущего грейда — не смена
    same = can_attempt("middle", TODAY, current_grade="middle", last_grade_change=changed)
    assert same.allowed
    after = can_attempt(
        "senior", changed + timedelta(days=90), current_grade="middle", last_grade_change=changed
    )
    assert after.allowed


def test_initial_assignment_is_not_a_change():
    # грейд присвоен первым тестом, смен ещё не было — можно сразу пробовать выше
    e = can_attempt("senior", TODAY, current_grade="middle", last_grade_change=None)
    assert e.allowed
    assert not is_grade_change(None, "middle")
    assert is_grade_change("middle", "senior")
    assert not is_grade_change("middle", "middle")


def test_two_blockers_return_latest_date():
    changed = TODAY - timedelta(days=80)  # смена доступна через 10 дней
    attempts = [Attempt(TODAY - timedelta(days=5), "senior", passed=False)]  # повтор — через 25
    e = can_attempt(
        "senior", TODAY, current_grade="middle", last_grade_change=changed, attempts=attempts
    )
    assert not e.allowed
    assert e.available_from == TODAY + timedelta(days=25)
    assert e.code == "failed_retry_cooldown"


def test_next_grade_change_date():
    assert next_grade_change_date(None) is None
    assert next_grade_change_date(TODAY) == TODAY + timedelta(days=90)
