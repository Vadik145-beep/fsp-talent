"""Симуляция на 1000 синтетических кандидатах (T4.4, T4.7, T11.3, T11.4)."""

import numpy as np
import pytest

from app.testing.engine.simulate import (
    DEFAULT_SEED,
    cohens_kappa,
    format_report,
    grade_accuracy,
    make_candidates,
    make_synthetic_bank,
    pearson,
    point_biserial,
    run_all,
    run_base,
    run_leak,
)


@pytest.fixture(scope="module")
def base():
    results, _run, _items = run_base(1000, DEFAULT_SEED)
    return results


@pytest.fixture(scope="module")
def leak():
    return run_leak(1000, DEFAULT_SEED)


def test_theta_recovery_and_length(base):
    a = base.accuracy
    assert a.n == 1000
    assert a.corr_theta >= 0.85
    assert a.mean_length <= 15 and a.max_length <= 15
    assert a.grade_within1 >= 0.95
    assert a.grade_exact >= 0.65


def test_retest_stability(base):
    s = base.stability
    assert s.retest_corr >= 0.8
    assert s.agreement >= 0.6 and s.kappa >= 0.45
    assert s.decision_agreement >= 0.8


def test_discrimination_and_exposure(base):
    assert base.cat_rpb_mean > 0.15
    assert base.linear_rpb_mean > 0.25
    assert base.max_exposure <= 0.25 + 1e-9


def test_leak_scenario(leak):
    modes = {m.mode: m for m in leak.modes}
    background = modes["Нет утечки (фон)"]
    unprotected = modes["Утечка, без защиты (один вариант)"]
    param = modes["Утечка + параметризация"]
    detector = modes["Утечка + детектор (один вариант)"]
    assert leak.n_leaked == 48 and leak.n_cheaters == 100
    # утечка без защиты завышает грейд читерам
    assert unprotected.cheater_inflated > background.cheater_inflated + 0.3
    # параметризация почти убирает выгоду от слива
    assert param.cheater_bias < 0.25 * unprotected.cheater_bias
    # детектор находит слитые задачи и не трогает честные
    assert detector.item_recall >= 0.7
    assert detector.item_precision >= 0.9
    assert detector.cheater_inflated < unprotected.cheater_inflated
    assert background.items_flagged == 0
    assert unprotected.cand_recall >= 0.5 and unprotected.cand_precision >= 0.9


def test_metric_functions():
    assert cohens_kappa(["junior", "middle"] * 5, ["junior", "middle"] * 5) == pytest.approx(1.0)
    assert grade_accuracy(["junior", "senior"], ["middle", "senior"]) == (0.5, 1.0)
    assert pearson([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0)
    assert point_biserial([True, False, True, False], [2.0, 0.0, 2.0, 0.0]) == pytest.approx(1.0)
    rng = np.random.default_rng(0)
    bank = make_synthetic_bank(rng, n_items=200, n_pilot=10)
    assert sum(not it.bank_item.is_pilot for it in bank) == 200
    assert len({it.bank_item.topic for it in bank}) == 8
    cands = make_candidates(100, rng, cheater_share=0.1)
    assert sum(c.cheater for c in cands) == 10


def test_report_renders():
    text = format_report(run_all(DEFAULT_SEED, n=120))
    assert "Корреляция θ̂ с истинным θ" in text
    assert "Утечка + параметризация" in text
    assert "Размер банка" in text
