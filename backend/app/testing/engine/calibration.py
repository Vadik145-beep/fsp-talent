"""Калибровка шаблона: переоценка a, b по накопленным ответам при известных θ.

Модель: logit P = a·θ + c, b = −c / a. Это логистическая регрессия ответа на θ.
Решаем методом Ньютона со слабым нормальным априором вокруг текущих (a, b) — он не даёт
параметрам улететь в бесконечность на малых выборках или при «все ответили верно»,
а на сотнях ответов практически не влияет. a и b ограничиваются разумными рамками.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from .irt import prob

A_MIN, A_MAX = 0.2, 4.0
B_MIN, B_MAX = -4.0, 4.0


@dataclass(frozen=True)
class CalibrationResult:
    a: float
    b: float
    se_a: float
    se_b: float
    n: int
    converged: bool
    iterations: int
    log_lik: float


def calibrate_item(
    thetas: Sequence[float],
    corrects: Sequence[bool],
    *,
    a0: float = 1.0,
    b0: float = 0.0,
    prior_sd_a: float = 1.0,
    prior_sd_c: float = 3.0,
    max_iter: int = 100,
    tol: float = 1e-6,
) -> CalibrationResult:
    """Оценить (a, b) задачи по парам (θ отвечавшего, верно ли)."""
    th = np.asarray(thetas, dtype=np.float64)
    x = np.asarray(corrects, dtype=np.float64)
    if th.shape != x.shape:
        raise ValueError("thetas и corrects должны быть одной длины")
    n = int(th.size)
    a0 = min(max(a0, A_MIN), A_MAX)
    c0 = -a0 * b0
    if n == 0:
        return CalibrationResult(a0, b0, math.inf, math.inf, 0, False, 0, 0.0)

    def objective(a: float, c: float) -> float:
        z = np.clip(a * th + c, -35, 35)
        ll = float(np.sum(x * z - np.logaddexp(0.0, z)))
        return ll - 0.5 * ((a - a0) / prior_sd_a) ** 2 - 0.5 * ((c - c0) / prior_sd_c) ** 2

    a, c = a0, c0
    cur = objective(a, c)
    converged = False
    it = 0
    for it in range(1, max_iter + 1):  # noqa: B007 - номер итерации нужен после цикла
        p = np.asarray(prob(th, a, -c / a), dtype=np.float64)
        r = x - p
        g = np.array(
            [
                float(np.sum(r * th)) - (a - a0) / prior_sd_a**2,
                float(np.sum(r)) - (c - c0) / prior_sd_c**2,
            ]
        )
        w = p * (1 - p)
        h = -np.array(
            [
                [float(np.sum(w * th * th)) + 1 / prior_sd_a**2, float(np.sum(w * th))],
                [float(np.sum(w * th)), float(np.sum(w)) + 1 / prior_sd_c**2],
            ]
        )
        step = -np.linalg.solve(h, g)
        t = 1.0
        while True:
            na = min(max(a + t * step[0], A_MIN), A_MAX)
            nc = c + t * step[1]
            new = objective(na, nc)
            if new >= cur - 1e-12 or t < 1e-6:
                break
            t /= 2
        if new < cur - 1e-12:  # улучшить уже нельзя — мы в максимуме (с учётом рамок)
            converged = True
            break
        moved = abs(na - a) + abs(nc - c)
        a, c, cur = na, nc, new
        if moved < tol:
            converged = True
            break

    p = np.asarray(prob(th, a, -c / a), dtype=np.float64)
    w = p * (1 - p)
    info = np.array(
        [
            [float(np.sum(w * th * th)) + 1 / prior_sd_a**2, float(np.sum(w * th))],
            [float(np.sum(w * th)), float(np.sum(w)) + 1 / prior_sd_c**2],
        ]
    )
    cov = np.linalg.inv(info)
    se_a = math.sqrt(max(float(cov[0, 0]), 0.0))
    db_da, db_dc = c / a**2, -1.0 / a
    var_b = db_da**2 * cov[0, 0] + db_dc**2 * cov[1, 1] + 2 * db_da * db_dc * cov[0, 1]
    se_b = math.sqrt(max(float(var_b), 0.0))
    b = min(max(-c / a, B_MIN), B_MAX)
    z = np.clip(a * th + c, -35, 35)
    log_lik = float(np.sum(x * z - np.logaddexp(0.0, z)))
    return CalibrationResult(float(a), float(b), se_a, se_b, n, converged, it, log_lik)


@dataclass(frozen=True)
class ActivationRule:
    """Когда пилотную задачу можно сделать проверочной."""

    min_n: int = 150
    min_a: float = 0.4  # слабая различающая сила — задача бесполезна
    max_se_b: float = 0.35
    max_abs_b: float = 3.5


def activation_check(
    result: CalibrationResult, rule: ActivationRule | None = None
) -> tuple[bool, str]:
    """Можно ли перевести шаблон pilot → active. Возвращает (да/нет, причина по-русски)."""
    rule = rule or ActivationRule()
    if result.n < rule.min_n:
        return False, f"Мало ответов: {result.n} из {rule.min_n}."
    if not result.converged:
        return False, "Оценка параметров не сошлась."
    if result.a < rule.min_a:
        return False, f"Слабая различающая сила: a = {result.a:.2f} < {rule.min_a}."
    if abs(result.b) > rule.max_abs_b:
        return False, f"Сложность вне рабочего диапазона: b = {result.b:.2f}."
    if result.se_b > rule.max_se_b:
        return False, f"Сложность оценена неточно: SE(b) = {result.se_b:.2f}."
    return True, "Достаточно ответов, параметры устойчивы — задачу можно сделать активной."


def calibrate_bank(
    responses: Mapping[str, Sequence[tuple[float, bool]]],
    current: Mapping[str, tuple[float, float]],
) -> dict[str, CalibrationResult]:
    """Пересчитать параметры нескольких шаблонов. responses: id → [(θ, верно)]."""
    out: dict[str, CalibrationResult] = {}
    for item_id, rows in responses.items():
        a0, b0 = current.get(item_id, (1.0, 0.0))
        out[item_id] = calibrate_item(
            [r[0] for r in rows], [bool(r[1]) for r in rows], a0=a0, b0=b0
        )
    return out
