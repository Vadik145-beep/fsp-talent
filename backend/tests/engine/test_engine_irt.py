import math

import numpy as np
import pytest

from app.testing.engine.irt import (
    GRID_POINTS,
    THETA_GRID,
    estimate_theta,
    estimate_theta_for_grade,
    information,
    leave_one_out_thetas,
    person_fit_lz,
    prior_for_grade,
    prob,
    total_information,
)


def test_prob_basics():
    assert prob(0.7, 1.4, 0.7) == pytest.approx(0.5)
    assert prob(3.0, 1.0, 0.0) > prob(1.0, 1.0, 0.0) > prob(-1.0, 1.0, 0.0)
    arr = prob(np.array([-1.0, 0.0, 1.0]), 1.0, 0.0)
    assert arr.shape == (3,)
    assert isinstance(prob(0.0, 1.0, 0.0), float)
    # экстремальные значения не дают переполнения
    assert 0.0 < prob(-100.0, 3.0, 4.0) < 1e-10
    assert 1.0 - 1e-10 < prob(100.0, 3.0, -4.0) <= 1.0


def test_information_max_at_b():
    a, b = 1.7, 0.4
    assert information(b, a, b) == pytest.approx(a**2 / 4)
    assert information(b + 1, a, b) < information(b, a, b)
    assert total_information(b, [(a, b), (a, b)]) == pytest.approx(a**2 / 2)


def test_grid_resolution():
    assert GRID_POINTS >= 61
    assert THETA_GRID[0] == -4.0 and THETA_GRID[-1] == 4.0


def test_eap_without_answers_returns_prior():
    est = estimate_theta([], prior_mean=0.5, prior_sd=1.0)
    assert est.theta == pytest.approx(0.5, abs=0.02)
    assert est.se == pytest.approx(1.0, abs=0.05)
    assert est.n == 0


def test_eap_direction():
    items = [(1.2, b) for b in (-1.0, -0.5, 0.0, 0.5, 1.0)]
    up = estimate_theta([(a, b, True) for a, b in items])
    down = estimate_theta([(a, b, False) for a, b in items])
    assert up.theta > 0.5 and down.theta < -0.5
    assert up.se < 1.0


def test_eap_recovers_theta():
    rng = np.random.default_rng(1)
    true_theta = 1.2
    responses = []
    for _ in range(300):
        a, b = rng.uniform(0.8, 2.0), rng.uniform(-2.0, 3.0)
        responses.append((a, b, bool(rng.random() < prob(true_theta, a, b))))
    est = estimate_theta(responses)
    assert est.theta == pytest.approx(true_theta, abs=0.25)
    assert est.se < 0.15
    lo, hi = est.interval()
    assert lo < est.theta < hi


def test_prior_depends_on_grade():
    assert (
        prior_for_grade("senior")[0] > prior_for_grade("middle")[0] > prior_for_grade("intern")[0]
    )
    assert prior_for_grade(None) == (0.0, 1.0)
    with pytest.raises(ValueError):
        prior_for_grade("lead")
    # одинаковые ответы, разный заявленный грейд — с малым числом ответов оценка сдвигается
    resp = [(1.0, 0.0, True), (1.0, 0.0, False)]
    assert (
        estimate_theta_for_grade(resp, "senior").theta
        > estimate_theta_for_grade(resp, "junior").theta
    )


def test_leave_one_out():
    resp = [(1.5, 0.0, True), (1.5, 0.5, True), (1.5, 1.0, False), (1.5, -0.5, True)]
    loo = leave_one_out_thetas(resp)
    full = estimate_theta(resp).theta
    assert len(loo) == len(resp)
    # убрали верный ответ — оценка ниже, убрали неверный — выше
    assert loo[0] < full and loo[2] > full
    assert leave_one_out_thetas([]) == []


def test_person_fit_lz_detects_aberrant_pattern():
    bs = np.linspace(-2, 2, 20)
    typical = [(1.5, b, b < 0) for b in bs]  # верно на лёгких, неверно на сложных
    aberrant = [(1.5, b, b >= 0) for b in bs]  # наоборот
    assert person_fit_lz(typical, 0.0) > -1.0
    assert person_fit_lz(aberrant, 0.0) < -3.0
    assert math.isfinite(person_fit_lz([], 0.0))
