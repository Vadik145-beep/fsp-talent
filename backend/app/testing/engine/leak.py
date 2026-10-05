"""Детектор утечек задач и аномалий кандидатов.

По задаче (шаблону), в скользящем окне последних ответов:
1. IRT-сигнал: наблюдаемая доля верных против ожидаемой по 2PL при известных θ отвечавших.
   z = (O − E) / sqrt(Σ p(1 − p)). Флаг, если n ≥ min_n, z ≥ порога и разница долей ≥ min_diff.
2. Сигнал скорости: сколько верных ответов дано подозрительно быстро (быстрее доли
   fast_fraction от медианного времени по задаче). Честно такие ответы редки; если слитый
   ответ просто вводят, их становится много. Проверка — хвост Пуассона.

По кандидату: верные ответы на задачи, сложные для его уровня (оценка θ без этой задачи),
данные подозрительно быстро; плюс индекс согласия рисунка ответов l_z.

θ отвечавших лучше брать «без этой задачи» (`irt.leave_one_out_thetas`): иначе слитая задача
сама подтягивает θ и маскирует утечку.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from .irt import estimate_theta, leave_one_out_thetas, person_fit_lz, prob


@dataclass(frozen=True, slots=True)
class ItemObservation:
    """Один ответ на задачу: θ отвечавшего, верно ли, время (сек)."""

    item_id: str
    theta: float
    correct: bool
    elapsed_s: float | None = None


@dataclass(frozen=True)
class LeakConfig:
    window: int = 300  # сколько последних ответов по задаче смотреть
    min_n: int = 30  # меньше ответов — не делаем выводов
    z_threshold: float = 3.5
    min_diff: float = 0.10  # минимальный рост доли верных (в долях, 0.10 = 10 п.п.)
    fast_fraction: float = 0.35  # «быстро» = быстрее 35% медианного времени задачи
    # Ожидаемая доля быстрых верных ответов у честных. None — оценить по всему банку
    # устойчиво к утечкам: берётся половина задач с наименьшей долей (слитыми может быть
    # почти половина показываемых задач, не искажая оценку), и не меньше fast_baseline_floor.
    fast_baseline: float | None = None
    fast_baseline_floor: float = 0.005
    fast_baseline_trim: float = 0.5
    fast_alpha: float = 1e-4  # порог значимости хвоста Пуассона
    fast_min_count: int = 4


@dataclass(frozen=True)
class ItemLeakReport:
    item_id: str
    n: int
    observed_rate: float
    expected_rate: float
    diff: float
    z: float
    median_time_s: float | None
    fast_correct: int
    fast_expected: float
    fast_p_value: float
    flagged: bool
    reasons: tuple[str, ...]  # "irt_drift", "fast_correct"


def poisson_sf(k: int, lam: float) -> float:
    """P(X ≥ k) для X ~ Пуассон(λ)."""
    if k <= 0:
        return 1.0
    if lam <= 0:
        return 0.0
    term = math.exp(-lam)
    cdf = term
    for i in range(1, k):
        term *= lam / i
        cdf += term
    return max(0.0, 1.0 - cdf)


@dataclass(frozen=True, slots=True)
class _FastStats:
    median_time_s: float | None
    fast_correct: int
    n_timed: int


def _fast_stats(obs: Sequence[ItemObservation], fast_fraction: float) -> _FastStats:
    times = [o.elapsed_s for o in obs if o.elapsed_s is not None]
    if not times:
        return _FastStats(None, 0, 0)
    median_time = float(statistics.median(times))
    limit = fast_fraction * median_time
    fast = sum(1 for o in obs if o.correct and o.elapsed_s is not None and o.elapsed_s < limit)
    return _FastStats(median_time, fast, len(times))


def estimate_fast_baseline(
    stats: Iterable[tuple[int, int]], trim: float = 0.5, floor: float = 0.005
) -> float:
    """Доля быстрых верных ответов у честных по парам (быстрых верных, всего с временем).

    Отбрасываем trim самых «быстрых» задач (там могут быть утечки) и считаем общую долю
    по остальным; не меньше floor.
    """
    rows = [(f, n) for f, n in stats if n > 0]
    if not rows:
        return floor
    rows.sort(key=lambda r: r[0] / r[1])
    keep = rows[: max(1, math.ceil(len(rows) * (1 - trim)))]
    total = sum(n for _, n in keep)
    return max(floor, sum(f for f, _ in keep) / total)


def item_leak_report(
    item_id: str,
    a: float,
    b: float,
    observations: Sequence[ItemObservation],
    config: LeakConfig | None = None,
    *,
    fast_baseline: float | None = None,
) -> ItemLeakReport:
    """Проверка одной задачи по последним `window` ответам (в хронологическом порядке).

    fast_baseline — ожидаемая доля быстрых верных; если не задана ни здесь, ни в config,
    берётся fast_baseline_floor (для оценки по всему банку используйте `detect_leaks`).
    """
    cfg = config or LeakConfig()
    obs = list(observations)[-cfg.window :]
    n = len(obs)
    if n == 0:
        return ItemLeakReport(item_id, 0, 0.0, 0.0, 0.0, 0.0, None, 0, 0.0, 1.0, False, ())
    theta = np.array([o.theta for o in obs], dtype=np.float64)
    x = np.array([o.correct for o in obs], dtype=bool)
    p = np.asarray(prob(theta, a, b), dtype=np.float64)
    observed = float(x.mean())
    expected = float(p.mean())
    var = float(np.sum(p * (1 - p)))
    z = float((x.sum() - p.sum()) / math.sqrt(var)) if var > 1e-12 else 0.0
    diff = observed - expected

    fs = _fast_stats(obs, cfg.fast_fraction)
    baseline = fast_baseline
    if baseline is None:
        baseline = cfg.fast_baseline if cfg.fast_baseline is not None else cfg.fast_baseline_floor
    fast_expected = baseline * fs.n_timed
    fast_p = poisson_sf(fs.fast_correct, fast_expected) if fs.n_timed else 1.0

    reasons: list[str] = []
    if n >= cfg.min_n and z >= cfg.z_threshold and diff >= cfg.min_diff:
        reasons.append("irt_drift")
    if (
        fs.n_timed >= cfg.min_n
        and fs.fast_correct >= cfg.fast_min_count
        and fast_p < cfg.fast_alpha
    ):
        reasons.append("fast_correct")
    return ItemLeakReport(
        item_id=item_id,
        n=n,
        observed_rate=observed,
        expected_rate=expected,
        diff=diff,
        z=z,
        median_time_s=fs.median_time_s,
        fast_correct=fs.fast_correct,
        fast_expected=fast_expected,
        fast_p_value=fast_p,
        flagged=bool(reasons),
        reasons=tuple(reasons),
    )


def detect_leaks(
    observations: Iterable[ItemObservation],
    params: Mapping[str, tuple[float, float]],
    config: LeakConfig | None = None,
) -> list[ItemLeakReport]:
    """Отчёт по всем задачам, у которых есть ответы. Сначала помеченные, затем по убыванию z.

    `params` — текущие (a, b) задач; ответы на задачи без параметров пропускаются.
    """
    cfg = config or LeakConfig()
    by_item: dict[str, list[ItemObservation]] = defaultdict(list)
    for o in observations:
        if o.item_id in params:
            by_item[o.item_id].append(o)
    windows = {k: v[-cfg.window :] for k, v in by_item.items()}
    baseline = cfg.fast_baseline
    if baseline is None:
        stats = (_fast_stats(v, cfg.fast_fraction) for v in windows.values())
        baseline = estimate_fast_baseline(
            ((s.fast_correct, s.n_timed) for s in stats),
            cfg.fast_baseline_trim,
            cfg.fast_baseline_floor,
        )
    reports = [
        item_leak_report(item_id, *params[item_id], obs, cfg, fast_baseline=baseline)
        for item_id, obs in windows.items()
    ]
    return sorted(reports, key=lambda r: (not r.flagged, -r.z))


def flagged_item_ids(reports: Iterable[ItemLeakReport]) -> list[str]:
    return [r.item_id for r in reports if r.flagged]


# --------------------------------------------------------------------------- аномалии кандидата


@dataclass(frozen=True, slots=True)
class CandidateResponse:
    """Ответ кандидата для проверки на аномалии."""

    item_id: str
    a: float
    b: float
    correct: bool
    elapsed_s: float | None
    typical_time_s: float | None  # медианное время ответа на эту задачу по всем кандидатам


@dataclass(frozen=True)
class CandidateAnomalyConfig:
    fast_fraction: float = 0.35
    hard_p: float = 0.6  # «сложная» — шанс верного ответа при θ кандидата ниже 60%
    min_hits: int = 2  # столько быстрых верных ответов на сложные задачи — уже флаг
    lz_threshold: float = -3.0
    prior_mean: float = 0.0
    prior_sd: float = 1.0


@dataclass(frozen=True)
class CandidateAnomalyReport:
    n: int
    suspicious_item_ids: tuple[str, ...]
    lz: float
    flagged: bool
    reasons: tuple[str, ...]  # "fast_hard_correct", "aberrant_pattern"


def candidate_anomalies(
    responses: Sequence[CandidateResponse], config: CandidateAnomalyConfig | None = None
) -> CandidateAnomalyReport:
    """Аномалии одного кандидата: быстрые верные ответы на сложные для него задачи."""
    cfg = config or CandidateAnomalyConfig()
    rows = list(responses)
    if not rows:
        return CandidateAnomalyReport(0, (), 0.0, False, ())
    triples = [(r.a, r.b, r.correct) for r in rows]
    loo = leave_one_out_thetas(triples, cfg.prior_mean, cfg.prior_sd)
    hits: list[str] = []
    for r, th in zip(rows, loo, strict=True):
        if not r.correct or r.elapsed_s is None or not r.typical_time_s:
            continue
        fast = r.elapsed_s < cfg.fast_fraction * r.typical_time_s
        hard = prob(th, r.a, r.b) < cfg.hard_p
        if fast and hard:
            hits.append(r.item_id)
    theta_all = estimate_theta(triples, cfg.prior_mean, cfg.prior_sd).theta
    lz = person_fit_lz(triples, theta_all)
    reasons: list[str] = []
    if len(hits) >= cfg.min_hits:
        reasons.append("fast_hard_correct")
    if len(rows) >= 8 and lz < cfg.lz_threshold:
        reasons.append("aberrant_pattern")
    return CandidateAnomalyReport(
        n=len(rows),
        suspicious_item_ids=tuple(hits),
        lz=lz,
        flagged=bool(reasons),
        reasons=tuple(reasons),
    )


def precision_recall(flagged: Iterable[str], truth: Iterable[str]) -> tuple[float, float]:
    """Точность и полнота набора флагов относительно истинного набора."""
    f, t = set(flagged), set(truth)
    tp = len(f & t)
    precision = tp / len(f) if f else 1.0
    recall = tp / len(t) if t else 1.0
    return precision, recall
