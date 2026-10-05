import math

import numpy as np
import pytest

from app.testing.engine.calibration import (
    A_MAX,
    B_MAX,
    activation_check,
    calibrate_bank,
    calibrate_item,
)
from app.testing.engine.irt import prob


def simulate(a, b, n, seed):
    rng = np.random.default_rng(seed)
    th = rng.normal(0, 1, n)
    x = rng.random(n) < prob(th, a, b)
    return th.tolist(), x.tolist()


@pytest.mark.parametrize(("a", "b"), [(1.0, 0.0), (1.8, -1.2), (0.7, 1.5)])
def test_recovers_parameters(a, b):
    th, x = simulate(a, b, 4000, seed=int(10 * a + b * 3 + 50))
    res = calibrate_item(th, x, a0=1.0, b0=0.0)
    assert res.converged
    # ошибка в пределах трёх стандартных ошибок оценки
    assert abs(res.a - a) <= 3 * res.se_a
    assert abs(res.b - b) <= 3 * res.se_b
    assert 0 < res.se_b < 0.15 and 0 < res.se_a < 0.15
    ok, reason = activation_check(res)
    assert ok, reason


def test_degenerate_data_stays_bounded():
    th = np.linspace(-2, 2, 50).tolist()
    res = calibrate_item(th, [True] * 50)  # все ответили верно
    assert math.isfinite(res.a) and math.isfinite(res.b)
    assert res.a <= A_MAX and res.b <= B_MAX
    empty = calibrate_item([], [])
    assert empty.n == 0 and not empty.converged
    with pytest.raises(ValueError):
        calibrate_item([0.0, 1.0], [True])


def test_activation_rules():
    th, x = simulate(1.2, 0.3, 60, seed=1)
    ok, reason = activation_check(calibrate_item(th, x))
    assert not ok and "Мало ответов" in reason
    th, x = simulate(0.1, 0.0, 3000, seed=2)  # задача почти не различает
    ok, reason = activation_check(calibrate_item(th, x))
    assert not ok and "различающая" in reason


def test_calibrate_bank():
    th, x = simulate(1.5, 0.5, 800, seed=3)
    out = calibrate_bank({"t1": list(zip(th, x, strict=True))}, {"t1": (1.0, 0.0)})
    assert set(out) == {"t1"}
    assert out["t1"].b == pytest.approx(0.5, abs=0.25)
