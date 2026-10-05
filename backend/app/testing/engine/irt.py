"""Двухпараметрическая модель IRT (2PL) и EAP-оценка уровня кандидата.

P(верно | θ) = 1 / (1 + exp(-a · (θ - b))), где
- θ — уровень кандидата (шкала: среднее 0, стандартное отклонение 1 по популяции);
- b — сложность задачи (уровень θ, при котором шанс ответить верно 50%);
- a — различающая сила (насколько резко растёт шанс верного ответа с ростом θ).

Оценка θ — EAP (среднее апостериорного распределения) по квадратуре на сетке −4..4
с нормальным априором. Центр априора зависит от заявленного грейда: это ускоряет тест,
но при 6+ ответах данные перевешивают априор.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

from .constants import check_grade

FloatArray = npt.NDArray[np.float64]

THETA_MIN = -4.0
THETA_MAX = 4.0
GRID_POINTS = 81
THETA_GRID: FloatArray = np.linspace(THETA_MIN, THETA_MAX, GRID_POINTS)

# Центр априора по заявленному грейду — середины полос грейдов при порогах −1 / 0 / 1.
GRADE_PRIOR_MEANS: dict[str, float] = {
    "intern": -1.5,
    "junior": -0.5,
    "middle": 0.5,
    "senior": 1.5,
}
DEFAULT_PRIOR_SD = 1.0

# Ответ для оценки: (a, b, верно ли).
ResponseTuple = tuple[float, float, bool]


def prob(theta: Any, a: Any, b: Any) -> Any:
    """Вероятность верного ответа по 2PL. Работает и со скалярами, и с массивами numpy."""
    z = np.clip(np.multiply(a, np.subtract(theta, b)), -35.0, 35.0)
    p = 1.0 / (1.0 + np.exp(-z))
    if np.ndim(p) == 0:
        return float(p)
    return p


def information(theta: Any, a: Any, b: Any) -> Any:
    """Информация Фишера задачи в точке θ: a² · P · (1 − P)."""
    p = prob(theta, a, b)
    info = np.multiply(np.square(a), np.multiply(p, np.subtract(1.0, p)))
    if np.ndim(info) == 0:
        return float(info)
    return info


def total_information(theta: float, items: Iterable[tuple[float, float]]) -> float:
    """Суммарная информация набора задач (a, b) в точке θ."""
    return float(sum(information(theta, a, b) for a, b in items))


def prior_for_grade(grade: str | None, sd: float = DEFAULT_PRIOR_SD) -> tuple[float, float]:
    """Параметры нормального априора (среднее, sd) для заявленного грейда.

    Без грейда — стандартный N(0, 1).
    """
    if grade is None:
        return 0.0, sd
    check_grade(grade)
    return GRADE_PRIOR_MEANS[grade], sd


@dataclass(frozen=True, slots=True)
class ThetaEstimate:
    """Оценка уровня: θ, стандартная ошибка и число учтённых ответов."""

    theta: float
    se: float
    n: int

    def interval(self, z: float = 1.645) -> tuple[float, float]:
        """Доверительный интервал θ ± z · SE (по умолчанию 90%)."""
        return self.theta - z * self.se, self.theta + z * self.se


def _as_arrays(
    responses: Iterable[ResponseTuple],
) -> tuple[FloatArray, FloatArray, npt.NDArray[np.bool_]]:
    rows = list(responses)
    if not rows:
        empty = np.empty(0, dtype=np.float64)
        return empty, empty, np.empty(0, dtype=np.bool_)
    a = np.fromiter((r[0] for r in rows), dtype=np.float64, count=len(rows))
    b = np.fromiter((r[1] for r in rows), dtype=np.float64, count=len(rows))
    x = np.fromiter((bool(r[2]) for r in rows), dtype=np.bool_, count=len(rows))
    return a, b, x


def log_likelihood_grid(
    a: FloatArray, b: FloatArray, x: npt.NDArray[np.bool_], grid: FloatArray = THETA_GRID
) -> FloatArray:
    """Логарифм правдоподобия ответов в каждой точке сетки θ."""
    if a.size == 0:
        return np.zeros_like(grid)
    p = prob(grid[None, :], a[:, None], b[:, None])
    p = np.clip(p, 1e-12, 1.0 - 1e-12)
    ll = np.where(x[:, None], np.log(p), np.log1p(-p))
    result: FloatArray = ll.sum(axis=0)
    return result


def posterior(
    responses: Iterable[ResponseTuple],
    prior_mean: float = 0.0,
    prior_sd: float = DEFAULT_PRIOR_SD,
    grid: FloatArray = THETA_GRID,
) -> FloatArray:
    """Нормированное апостериорное распределение θ на сетке."""
    a, b, x = _as_arrays(responses)
    log_post = -0.5 * ((grid - prior_mean) / prior_sd) ** 2 + log_likelihood_grid(a, b, x, grid)
    w = np.exp(log_post - log_post.max())
    result: FloatArray = w / w.sum()
    return result


def estimate_theta(
    responses: Iterable[ResponseTuple],
    prior_mean: float = 0.0,
    prior_sd: float = DEFAULT_PRIOR_SD,
    grid: FloatArray = THETA_GRID,
) -> ThetaEstimate:
    """EAP-оценка θ и её стандартная ошибка (sd апостериорного распределения)."""
    rows = list(responses)
    w = posterior(rows, prior_mean, prior_sd, grid)
    theta = float(np.dot(w, grid))
    se = float(math.sqrt(max(float(np.dot(w, (grid - theta) ** 2)), 0.0)))
    return ThetaEstimate(theta=theta, se=se, n=len(rows))


def estimate_theta_for_grade(
    responses: Iterable[ResponseTuple],
    claimed_grade: str | None,
    prior_sd: float = DEFAULT_PRIOR_SD,
) -> ThetaEstimate:
    """EAP с априором, центрированным на заявленном грейде."""
    mean, sd = prior_for_grade(claimed_grade, prior_sd)
    return estimate_theta(responses, mean, sd)


def leave_one_out_thetas(
    responses: Sequence[ResponseTuple],
    prior_mean: float = 0.0,
    prior_sd: float = DEFAULT_PRIOR_SD,
    grid: FloatArray = THETA_GRID,
) -> list[float]:
    """θ кандидата без учёта каждой задачи по очереди.

    Нужна детектору утечек: ожидаемая доля верных по задаче считается по уровню,
    оценённому на остальных задачах, чтобы слитая задача не «подтягивала» θ под себя.
    """
    a, b, x = _as_arrays(responses)
    if a.size == 0:
        return []
    p = np.clip(prob(grid[None, :], a[:, None], b[:, None]), 1e-12, 1.0 - 1e-12)
    ll = np.where(x[:, None], np.log(p), np.log1p(-p))
    total = ll.sum(axis=0) - 0.5 * ((grid - prior_mean) / prior_sd) ** 2
    out: list[float] = []
    for i in range(a.size):
        lp = total - ll[i]
        w = np.exp(lp - lp.max())
        w /= w.sum()
        out.append(float(np.dot(w, grid)))
    return out


def person_fit_lz(responses: Sequence[ResponseTuple], theta: float) -> float:
    """Стандартизованный индекс согласия ответов с моделью (l_z, Drasgow и др., 1985).

    Около 0 — ответы типичны для такого θ; сильно отрицательный (< −2) —
    необычный рисунок ответов (например, верно на сложных и неверно на лёгких).
    """
    a, b, x = _as_arrays(responses)
    if a.size == 0:
        return 0.0
    p = np.clip(prob(theta, a, b), 1e-9, 1.0 - 1e-9)
    lp = np.log(p)
    lq = np.log1p(-p)
    l0 = float(np.sum(np.where(x, lp, lq)))
    expected = float(np.sum(p * lp + (1 - p) * lq))
    variance = float(np.sum(p * (1 - p) * (lp - lq) ** 2))
    if variance <= 1e-12:
        return 0.0
    return (l0 - expected) / math.sqrt(variance)
