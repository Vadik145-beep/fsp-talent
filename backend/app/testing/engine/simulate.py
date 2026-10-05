"""Синтетическая проверка механики тестирования.

Кандидаты с известным истинным θ проходят настоящий `CATSession` на синтетическом банке;
ответы генерируются по 2PL от истинного θ. Считаем метрики, которые просит жюри [ТЗ 6.2]:
восстановление θ, точность грейда, стабильность при повторе, различающая сила задач,
длина теста; плюс сценарий утечки и работу детектора.

Запуск (из корня репозитория):
    PYTHONPATH=backend python -m app.testing.engine.simulate --seed 20261011
"""

from __future__ import annotations

import argparse
import math
import statistics
import time
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import numpy.typing as npt

from .calibration import activation_check, calibrate_item
from .cat import AnswerRecord, BankItem, CATConfig, CATSession, ItemBank
from .constants import GRADES, grade_index
from .grading import DEFAULT_THRESHOLDS, GradeThresholds, decide
from .irt import leave_one_out_thetas, prior_for_grade, prob
from .leak import (
    CandidateAnomalyConfig,
    CandidateResponse,
    ItemObservation,
    LeakConfig,
    candidate_anomalies,
    detect_leaks,
    precision_recall,
)

DEFAULT_SEED = 20261011

# --------------------------------------------------------------------------- данные


@dataclass(frozen=True)
class SimCandidate:
    cid: int
    theta: float  # истинный уровень (скрыт от движка)
    claimed_grade: str
    cheater: bool = False


@dataclass(frozen=True)
class SimItem:
    bank_item: BankItem  # то, что видит движок (a, b могут быть с ошибкой калибровки)
    true_a: float
    true_b: float
    median_time_s: float


def make_candidates(
    n: int,
    rng: np.random.Generator,
    *,
    thresholds: GradeThresholds = DEFAULT_THRESHOLDS,
    cheater_share: float = 0.0,
) -> list[SimCandidate]:
    """θ ~ N(0, 1). Заявленный грейд: 60% — истинный, по 20% — на один выше или ниже."""
    thetas = np.clip(rng.normal(0.0, 1.0, n), -3.5, 3.5)
    shifts = rng.choice([-1, 0, 1], size=n, p=[0.2, 0.6, 0.2])
    cheaters = set(rng.choice(n, size=round(cheater_share * n), replace=False).tolist())
    out = []
    for i in range(n):
        true_idx = grade_index(thresholds.grade_for(float(thetas[i])))
        claimed = GRADES[min(max(true_idx + int(shifts[i]), 0), len(GRADES) - 1)]
        out.append(SimCandidate(i, float(thetas[i]), claimed, i in cheaters))
    return out


def make_synthetic_bank(
    rng: np.random.Generator,
    *,
    n_items: int = 240,
    n_topics: int = 8,
    n_pilot: int = 20,
    param_noise: float = 0.0,
) -> list[SimItem]:
    """Синтетический банк: a ~ логнормальное (медиана 1.3), b ~ U(−2.8, 2.8), темы случайно.

    param_noise > 0 — движку отдаются параметры с ошибкой калибровки
    (b ± noise, a × exp(± noise)), а ответы идут по истинным.
    """
    items: list[SimItem] = []
    for k in range(n_items + n_pilot):
        true_a = float(np.clip(rng.lognormal(math.log(1.3), 0.25), 0.6, 2.5))
        true_b = float(rng.uniform(-2.8, 2.8))
        topic = f"topic_{int(rng.integers(n_topics)) + 1}"
        median_time = float(rng.uniform(40, 150))
        a_seen, b_seen = true_a, true_b
        if param_noise > 0:
            a_seen = float(np.clip(true_a * math.exp(rng.normal(0, param_noise)), 0.3, 3.0))
            b_seen = float(true_b + rng.normal(0, param_noise))
        pilot = k >= n_items
        bank_item = BankItem(
            item_id=f"{'pilot' if pilot else 'item'}_{k:04d}",
            topic=topic,
            # для пилотных движок знает только экспертную оценку
            a=1.0 if pilot else a_seen,
            b=round(true_b) if pilot else b_seen,
            status="pilot" if pilot else "active",
            time_limit_s=3 * median_time,
        )
        items.append(SimItem(bank_item, true_a, true_b, median_time))
    return items


# --------------------------------------------------------------------------- модель ответа


@dataclass(frozen=True)
class LeakSetup:
    """Сценарий утечки: какие задачи слиты и как читер ими пользуется."""

    leaked: frozenset[str] = frozenset()
    parametrized: bool = True  # False — у задачи один вариант, слитый ответ подходит всегда
    variant_match_prob: float = 0.1  # при параметризации: шанс, что попался слитый вариант


def simulate_answer(
    rng: np.random.Generator, cand: SimCandidate, item: SimItem, leak: LeakSetup
) -> tuple[bool, float]:
    """Ответ кандидата и время. Честно — по 2PL; читер на слитой задаче — быстро и верно."""
    knows = False
    if cand.cheater and item.bank_item.item_id in leak.leaked:
        knows = (not leak.parametrized) or rng.random() < leak.variant_match_prob
    if knows:
        return True, float(item.median_time_s * 0.2 * rng.lognormal(0.0, 0.3))
    p = prob(cand.theta, item.true_a, item.true_b)
    correct = bool(rng.random() < p)
    speed = math.exp(0.15 * (item.true_b - cand.theta))
    return correct, float(item.median_time_s * speed * rng.lognormal(0.0, 0.35))


# --------------------------------------------------------------------------- прогон


@dataclass
class SessionOutcome:
    cid: int
    true_theta: float
    claimed_grade: str
    cheater: bool
    theta: float
    se: float
    n_scored: int
    n_pilot: int
    records: list[AnswerRecord]


@dataclass
class PopulationRun:
    outcomes: list[SessionOutcome]
    observations: list[ItemObservation]
    retired: list[tuple[int, str]] = field(default_factory=list)  # (номер сессии, item_id)
    pilot_responses: dict[str, list[tuple[float, bool]]] = field(default_factory=dict)


class ExposureTracker:
    """Доля сессий, в которых показывали задачу (вход для контроля экспозиции)."""

    def __init__(self, warmup: int = 20) -> None:
        self.counts: dict[str, int] = defaultdict(int)
        self.sessions = 0
        self.warmup = warmup

    def rates(self) -> dict[str, float]:
        if self.sessions < self.warmup:
            return {}
        return {k: v / self.sessions for k, v in self.counts.items()}

    def update(self, item_ids: Iterable[str]) -> None:
        self.sessions += 1
        for i in item_ids:
            self.counts[i] += 1


def run_population(
    candidates: Sequence[SimCandidate],
    items: Sequence[SimItem],
    *,
    config: CATConfig | None = None,
    seed: int = DEFAULT_SEED,
    leak: LeakSetup | None = None,
    detector_every: int | None = None,
    leak_config: LeakConfig | None = None,
    exposure: ExposureTracker | None = None,
) -> PopulationRun:
    """Прогнать кандидатов по очереди через CAT.

    detector_every — раз в столько сессий запускать детектор утечек и выводить
    помеченные задачи из банка (None — детектор выключен).
    """
    cfg = config or CATConfig()
    leak = leak or LeakSetup()
    rng = np.random.default_rng(seed)
    by_id = {it.bank_item.item_id: it for it in items}
    params = {k: (v.bank_item.a, v.bank_item.b) for k, v in by_id.items()}
    active_ids = [it.bank_item.item_id for it in items]
    bank = ItemBank(it.bank_item for it in items)
    exposure = exposure or ExposureTracker()
    run = PopulationRun([], [])
    retired: set[str] = set()

    for n_session, cand in enumerate(candidates, start=1):
        session = CATSession(
            bank,
            cand.claimed_grade,
            config=cfg,
            seed=int(rng.integers(2**31)),
            exposure_rates=exposure.rates(),
        )
        while (item := session.next_item()) is not None:
            correct, elapsed = simulate_answer(rng, cand, by_id[item.item_id], leak)
            session.submit(item.item_id, correct, elapsed)
        res = session.result()
        exposure.update(r.item_id for r in res.records)
        scored = [r for r in res.records if r.scored]
        mean, sd = prior_for_grade(cand.claimed_grade, cfg.prior_sd)
        loo = leave_one_out_thetas([(r.a, r.b, r.correct) for r in scored], mean, sd)
        for r, th in zip(scored, loo, strict=True):
            run.observations.append(ItemObservation(r.item_id, th, r.correct, r.elapsed_s))
        for r in res.records:
            if not r.scored:
                run.pilot_responses.setdefault(r.item_id, []).append((res.theta, r.correct))
        run.outcomes.append(
            SessionOutcome(
                cand.cid,
                cand.theta,
                cand.claimed_grade,
                cand.cheater,
                res.theta,
                res.se,
                res.n_scored,
                res.n_pilot,
                list(res.records),
            )
        )
        if detector_every and n_session % detector_every == 0:
            reports = detect_leaks(run.observations, params, leak_config)
            newly = [r.item_id for r in reports if r.flagged and r.item_id not in retired]
            if newly:
                retired.update(newly)
                run.retired += [(n_session, i) for i in newly]
                bank = ItemBank(by_id[i].bank_item for i in active_ids if i not in retired)
    return run


# --------------------------------------------------------------------------- метрики


def pearson(x: npt.ArrayLike, y: npt.ArrayLike) -> float:
    xa, ya = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if xa.size < 2 or xa.std() == 0 or ya.std() == 0:
        return 0.0
    return float(np.corrcoef(xa, ya)[0, 1])


def point_biserial(binary: Sequence[bool], scores: Sequence[float]) -> float:
    """Точечно-бисериальная корреляция (= Пирсон между 0/1 и баллом)."""
    return pearson([float(b) for b in binary], scores)


def grade_accuracy(true_grades: Sequence[str], est_grades: Sequence[str]) -> tuple[float, float]:
    """Доля точного совпадения грейда и доля с ошибкой не больше одного грейда."""
    pairs = list(zip(true_grades, est_grades, strict=True))
    if not pairs:
        return 0.0, 0.0
    exact = sum(t == e for t, e in pairs) / len(pairs)
    within = sum(abs(grade_index(t) - grade_index(e)) <= 1 for t, e in pairs) / len(pairs)
    return exact, within


def cohens_kappa(a: Sequence[str], b: Sequence[str], categories: Sequence[str] = GRADES) -> float:
    """Каппа Коэна: согласие двух классификаций с поправкой на случайное совпадение."""
    n = len(a)
    if n == 0:
        return 0.0
    idx = {c: i for i, c in enumerate(categories)}
    m = np.zeros((len(categories), len(categories)))
    for x, y in zip(a, b, strict=True):
        m[idx[x], idx[y]] += 1
    po = np.trace(m) / n
    pe = float(np.sum(m.sum(axis=1) * m.sum(axis=0))) / n**2
    return float((po - pe) / (1 - pe)) if pe < 1 else 1.0


def item_point_biserials(
    observations: Iterable[ItemObservation], min_n: int = 30
) -> dict[str, float]:
    """r_pb каждой задачи: ответ против θ отвечавшего, оценённой без этой задачи."""
    by_item: dict[str, list[ItemObservation]] = defaultdict(list)
    for o in observations:
        by_item[o.item_id].append(o)
    return {
        k: point_biserial([o.correct for o in v], [o.theta for o in v])
        for k, v in by_item.items()
        if len(v) >= min_n
    }


def linear_form_point_biserials(
    candidates: Sequence[SimCandidate],
    items: Sequence[SimItem],
    rng: np.random.Generator,
    form_length: int = 30,
) -> list[float]:
    """Классическая r_pb на неадаптивной форме: каждый решает одни и те же form_length задач,
    корреляция ответа с суммой баллов по остальным задачам формы."""
    active = [it for it in items if not it.bank_item.is_pilot]
    form = [active[i] for i in rng.choice(len(active), size=form_length, replace=False)]
    x = np.array(
        [[rng.random() < prob(c.theta, it.true_a, it.true_b) for it in form] for c in candidates],
        dtype=float,
    )
    total = x.sum(axis=1)
    return [pearson(x[:, j], total - x[:, j]) for j in range(form_length)]


@dataclass(frozen=True)
class AccuracyMetrics:
    n: int
    corr_theta: float
    rmse_theta: float
    mean_se: float
    grade_exact: float
    grade_within1: float
    grade_exact_far: float  # только кандидаты дальше 0.25 от порогов
    mean_length: float
    max_length: int
    share_se_target: float
    decisions: dict[str, float]


def accuracy_metrics(
    outcomes: Sequence[SessionOutcome],
    thresholds: GradeThresholds = DEFAULT_THRESHOLDS,
    se_target: float = 0.35,
) -> AccuracyMetrics:
    true_t = [o.true_theta for o in outcomes]
    est_t = [o.theta for o in outcomes]
    tg = [thresholds.grade_for(t) for t in true_t]
    eg = [thresholds.grade_for(t) for t in est_t]
    exact, within = grade_accuracy(tg, eg)
    far = [
        (t, e)
        for o, t, e in zip(outcomes, tg, eg, strict=True)
        if min(abs(o.true_theta - c) for c in thresholds.cuts()) > 0.25
    ]
    exact_far = sum(t == e for t, e in far) / len(far) if far else 0.0
    dec: dict[str, int] = defaultdict(int)
    for o in outcomes:
        dec[decide(o.theta, o.se, o.claimed_grade, thresholds=thresholds).outcome] += 1
    return AccuracyMetrics(
        n=len(outcomes),
        corr_theta=pearson(true_t, est_t),
        rmse_theta=float(np.sqrt(np.mean((np.array(true_t) - np.array(est_t)) ** 2))),
        mean_se=float(np.mean([o.se for o in outcomes])),
        grade_exact=exact,
        grade_within1=within,
        grade_exact_far=exact_far,
        mean_length=float(np.mean([o.n_scored for o in outcomes])),
        max_length=max(o.n_scored for o in outcomes),
        share_se_target=float(np.mean([o.se < se_target for o in outcomes])),
        decisions={k: v / len(outcomes) for k, v in sorted(dec.items())},
    )


@dataclass(frozen=True)
class StabilityMetrics:
    n: int
    agreement: float  # доля совпадения оценённого грейда
    kappa: float
    retest_corr: float
    decision_agreement: float  # доля совпадения решения «заявленный грейд подтверждён / нет»
    decision_kappa: float


def stability_metrics(
    first: Sequence[SessionOutcome],
    second: Sequence[SessionOutcome],
    thresholds: GradeThresholds = DEFAULT_THRESHOLDS,
) -> StabilityMetrics:
    g1 = [thresholds.grade_for(o.theta) for o in first]
    g2 = [thresholds.grade_for(o.theta) for o in second]
    agree = sum(x == y for x, y in zip(g1, g2, strict=True)) / len(g1)

    def passed(o: SessionOutcome) -> str:
        d = decide(o.theta, o.se, o.claimed_grade, thresholds=thresholds)
        return "fail" if d.outcome == "suggest_lower" else "pass"

    d1 = [passed(o) for o in first]
    d2 = [passed(o) for o in second]
    return StabilityMetrics(
        n=len(g1),
        agreement=agree,
        kappa=cohens_kappa(g1, g2),
        retest_corr=pearson([o.theta for o in first], [o.theta for o in second]),
        decision_agreement=sum(x == y for x, y in zip(d1, d2, strict=True)) / len(d1),
        decision_kappa=cohens_kappa(d1, d2, ("pass", "fail")),
    )


# --------------------------------------------------------------------------- сценарии


@dataclass
class BaseResults:
    seed: int
    accuracy: AccuracyMetrics
    stability: StabilityMetrics
    mean_a: float
    cat_rpb_mean: float
    cat_rpb_share_02: float
    linear_rpb_mean: float
    linear_rpb_share_02: float
    max_exposure: float
    seconds: float


def run_base(
    n: int = 1000, seed: int = DEFAULT_SEED, config: CATConfig | None = None
) -> tuple[BaseResults, PopulationRun, list[SimItem]]:
    """Точность, стабильность повтора и различающая сила на n синтетических кандидатах."""
    t0 = time.perf_counter()
    rng = np.random.default_rng(seed)
    items = make_synthetic_bank(rng)
    cands = make_candidates(n, rng)
    cfg = config or CATConfig()
    exposure = ExposureTracker()
    first = run_population(cands, items, config=cfg, seed=seed + 1, exposure=exposure)
    second = run_population(cands, items, config=cfg, seed=seed + 2, exposure=exposure)
    rpb = item_point_biserials(first.observations)
    lin = linear_form_point_biserials(cands, items, np.random.default_rng(seed + 3))
    active = [it for it in items if not it.bank_item.is_pilot]
    res = BaseResults(
        seed=seed,
        accuracy=accuracy_metrics(first.outcomes, se_target=cfg.se_target),
        stability=stability_metrics(first.outcomes, second.outcomes),
        mean_a=float(np.mean([it.true_a for it in active])),
        cat_rpb_mean=float(np.mean(list(rpb.values()))) if rpb else 0.0,
        cat_rpb_share_02=float(np.mean([v > 0.2 for v in rpb.values()])) if rpb else 0.0,
        linear_rpb_mean=float(np.mean(lin)),
        linear_rpb_share_02=float(np.mean([v > 0.2 for v in lin])),
        max_exposure=max(exposure.counts.values()) / exposure.sessions,
        seconds=time.perf_counter() - t0,
    )
    return res, first, items


@dataclass(frozen=True)
class LeakModeResult:
    mode: str
    cheater_bias: float  # средняя θ̂ − θ у читеров
    cheater_inflated: float  # доля читеров, у которых грейд выше истинного
    honest_inflated: float  # то же у честных (фон из-за ошибки измерения)
    item_precision: float
    item_recall: float
    recall_exposed: float  # полнота среди слитых задач, показанных ≥ min_n раз
    n_exposed: int
    recall_irt: float  # полнота только по IRT-сигналу
    recall_fast: float  # полнота только по сигналу скорости
    items_flagged: int
    retired: int
    cand_precision: float
    cand_recall: float


@dataclass
class LeakResults:
    seed: int
    n: int
    n_leaked: int
    n_cheaters: int
    modes: list[LeakModeResult]
    seconds: float


def _inflated(outcomes: Sequence[SessionOutcome], thresholds: GradeThresholds) -> float:
    if not outcomes:
        return 0.0
    return sum(
        grade_index(thresholds.grade_for(o.theta)) > grade_index(thresholds.grade_for(o.true_theta))
        for o in outcomes
    ) / len(outcomes)


def candidate_flags(run: PopulationRun, cfg: CandidateAnomalyConfig | None = None) -> set[int]:
    """Кандидаты с аномалиями времени (по медианному времени задач во всём журнале)."""
    times: dict[str, list[float]] = defaultdict(list)
    for o in run.observations:
        if o.elapsed_s is not None:
            times[o.item_id].append(o.elapsed_s)
    typical = {k: statistics.median(v) for k, v in times.items()}
    flagged = set()
    for out in run.outcomes:
        mean, sd = prior_for_grade(out.claimed_grade)
        c = cfg or CandidateAnomalyConfig()
        c = CandidateAnomalyConfig(
            c.fast_fraction, c.hard_p, c.min_hits, c.lz_threshold, prior_mean=mean, prior_sd=sd
        )
        rows = [
            CandidateResponse(r.item_id, r.a, r.b, r.correct, r.elapsed_s, typical.get(r.item_id))
            for r in out.records
            if r.scored
        ]
        if candidate_anomalies(rows, c).flagged:
            flagged.add(out.cid)
    return flagged


def _sample_leaked(
    run: PopulationRun, active: Sequence[str], k: int, rng: np.random.Generator
) -> frozenset[str]:
    """Сливаются задачи, которые реально показывали: вероятность ∝ числу показов."""
    counts: dict[str, int] = defaultdict(int)
    for out in run.outcomes:
        for r in out.records:
            if r.scored:
                counts[r.item_id] += 1
    shown = [i for i in active if counts[i] > 0]
    weights = np.array([counts[i] for i in shown], dtype=float)
    take = min(k, len(shown))
    leaked = set(rng.choice(shown, size=take, replace=False, p=weights / weights.sum()).tolist())
    rest = [i for i in active if i not in leaked]
    if len(leaked) < k:
        leaked |= set(rng.choice(rest, size=k - len(leaked), replace=False).tolist())
    return frozenset(leaked)


def run_leak(
    n: int = 1000,
    seed: int = DEFAULT_SEED,
    *,
    leaked_share: float = 0.2,
    cheater_share: float = 0.1,
    variant_match_prob: float = 0.1,
    detector_every: int = 100,
    config: CATConfig | None = None,
    leak_config: LeakConfig | None = None,
) -> LeakResults:
    """Сценарий утечки: 20% задач банка слиты, 10% кандидатов знают ответы на слитые.

    Сначала идёт честный прогон (фон). По нему выбираются слитые задачи — пропорционально
    числу показов: утечь может только то, что кандидаты видели, и чаще утекает то,
    что видели чаще. Затем тот же поток кандидатов проходит тест в каждом режиме защиты.
    """
    t0 = time.perf_counter()
    rng = np.random.default_rng(seed + 100)
    items = make_synthetic_bank(rng)
    cands = make_candidates(n, rng, cheater_share=cheater_share)
    active = [it.bank_item.item_id for it in items if not it.bank_item.is_pilot]
    cheater_ids = {c.cid for c in cands if c.cheater}
    params = {it.bank_item.item_id: (it.bank_item.a, it.bank_item.b) for it in items}
    lcfg = leak_config or LeakConfig()
    nan = float("nan")

    def run_mode(setup: LeakSetup, every: int | None) -> PopulationRun:
        return run_population(
            cands,
            items,
            config=config,
            seed=seed + 101,
            leak=setup,
            detector_every=every,
            leak_config=lcfg,
        )

    def evaluate(name: str, setup: LeakSetup, run: PopulationRun) -> LeakModeResult:
        cheaters = [o for o in run.outcomes if o.cheater]
        honest = [o for o in run.outcomes if not o.cheater]
        reports = detect_leaks(run.observations, params, lcfg)
        flagged = {r.item_id for r in reports if r.flagged} | {i for _, i in run.retired}
        ip, ir = precision_recall(flagged, setup.leaked)
        shown: dict[str, int] = defaultdict(int)
        for o in run.observations:
            shown[o.item_id] += 1
        exposed = {i for i in setup.leaked if shown[i] >= lcfg.min_n}
        by_irt = {r.item_id for r in reports if "irt_drift" in r.reasons}
        by_fast = {r.item_id for r in reports if "fast_correct" in r.reasons}
        cp, cr = precision_recall(
            {str(c) for c in candidate_flags(run)}, {str(c) for c in cheater_ids}
        )
        has_leak = bool(setup.leaked)
        return LeakModeResult(
            mode=name,
            cheater_bias=float(np.mean([o.theta - o.true_theta for o in cheaters])),
            cheater_inflated=_inflated(cheaters, DEFAULT_THRESHOLDS),
            honest_inflated=_inflated(honest, DEFAULT_THRESHOLDS),
            item_precision=ip,
            item_recall=ir if has_leak else nan,
            recall_exposed=precision_recall(flagged, exposed)[1] if exposed else nan,
            n_exposed=len(exposed),
            recall_irt=precision_recall(by_irt, setup.leaked)[1] if has_leak else nan,
            recall_fast=precision_recall(by_fast, setup.leaked)[1] if has_leak else nan,
            items_flagged=len(flagged),
            retired=len(run.retired),
            cand_precision=cp,
            cand_recall=cr,
        )

    background = run_mode(LeakSetup(frozenset()), None)
    leaked = _sample_leaked(background, active, round(leaked_share * len(active)), rng)
    static = LeakSetup(leaked, parametrized=False)
    param = LeakSetup(leaked, parametrized=True, variant_match_prob=variant_match_prob)
    results = [
        evaluate("Нет утечки (фон)", LeakSetup(frozenset()), background),
        evaluate("Утечка, без защиты (один вариант)", static, run_mode(static, None)),
        evaluate("Утечка + параметризация", param, run_mode(param, None)),
        evaluate("Утечка + детектор (один вариант)", static, run_mode(static, detector_every)),
        evaluate("Утечка + параметризация + детектор", param, run_mode(param, detector_every)),
    ]
    return LeakResults(seed, n, len(leaked), len(cheater_ids), results, time.perf_counter() - t0)


@dataclass(frozen=True)
class BankSizeRow:
    n_items: int
    n_candidates: int
    corr_theta: float
    mean_se: float
    grade_exact: float
    mean_length: float


def run_bank_sizes(
    sizes: Sequence[int] = (15, 30, 60, 120, 240), n: int = 500, seed: int = DEFAULT_SEED
) -> list[BankSizeRow]:
    """Как точность зависит от размера банка (на одну специализацию).

    Банки вложенные: меньший — первые k задач большого, кандидаты одни и те же.
    """
    rng = np.random.default_rng(seed + 200)
    full = make_synthetic_bank(rng, n_items=max(sizes), n_pilot=0)
    cands = make_candidates(n, rng)
    rows = []
    for size in sizes:
        run = run_population(cands, full[:size], seed=seed + 300)
        m = accuracy_metrics(run.outcomes)
        rows.append(BankSizeRow(size, n, m.corr_theta, m.mean_se, m.grade_exact, m.mean_length))
    return rows


def run_length_tradeoff(
    n: int = 1000, seed: int = DEFAULT_SEED, se_target: float = 0.30, max_items: int = 20
) -> BaseResults:
    """Что даёт более длинный тест (настройка, а не значение по умолчанию)."""
    res, _, _ = run_base(n, seed, CATConfig(se_target=se_target, max_items=max_items))
    return res


def run_param_noise(n: int = 1000, seed: int = DEFAULT_SEED, noise: float = 0.2) -> AccuracyMetrics:
    """Устойчивость к ошибке калибровки: движок знает a, b с ошибкой ~noise."""
    rng = np.random.default_rng(seed + 400)
    items = make_synthetic_bank(rng, param_noise=noise)
    cands = make_candidates(n, rng)
    return accuracy_metrics(run_population(cands, items, seed=seed + 401).outcomes)


@dataclass(frozen=True)
class CalibrationSummary:
    n_items: int
    responses_per_item: int
    rmse_a: float
    rmse_b: float
    activated: float


def run_calibration(
    n_items: int = 30, responses_per_item: int = 300, seed: int = DEFAULT_SEED
) -> CalibrationSummary:
    """Восстановление a, b пилотных задач по ответам кандидатов с известной θ."""
    rng = np.random.default_rng(seed + 500)
    err_a, err_b, ok = [], [], 0
    for _ in range(n_items):
        a = float(np.clip(rng.lognormal(math.log(1.3), 0.25), 0.6, 2.5))
        b = float(rng.uniform(-2.0, 2.0))
        # θ берём как оценку движка: истинная θ + ошибка измерения ~0.3
        true_t = rng.normal(0, 1, responses_per_item)
        x = rng.random(responses_per_item) < prob(true_t, a, b)
        est_t = true_t + rng.normal(0, 0.3, responses_per_item)
        res = calibrate_item(est_t.tolist(), x.tolist(), a0=1.0, b0=round(b))
        err_a.append(res.a - a)
        err_b.append(res.b - b)
        ok += activation_check(res)[0]
    return CalibrationSummary(
        n_items,
        responses_per_item,
        float(np.sqrt(np.mean(np.square(err_a)))),
        float(np.sqrt(np.mean(np.square(err_b)))),
        ok / n_items,
    )


# --------------------------------------------------------------------------- отчёт


def _pct(x: float) -> str:
    return "—" if math.isnan(x) else f"{100 * x:.1f}%"


def run_all(seed: int = DEFAULT_SEED, n: int = 1000) -> dict[str, Any]:
    base, _, _ = run_base(n, seed)
    return {
        "base": base,
        "noise": run_param_noise(n, seed),
        "leak": run_leak(n, seed),
        "sizes": run_bank_sizes(n=max(100, n // 2), seed=seed),
        "longer": run_length_tradeoff(n, seed),
        "calibration": run_calibration(seed=seed),
    }


def format_report(r: dict[str, Any]) -> str:
    b: BaseResults = r["base"]
    a = b.accuracy
    s = b.stability
    nz: AccuracyMetrics = r["noise"]
    lk: LeakResults = r["leak"]
    cal: CalibrationSummary = r["calibration"]
    lines = [
        f"## Точность и стабильность (seed {b.seed}, {a.n} кандидатов, банк 240 задач)",
        "",
        "| Метрика | Значение | Шум калибровки ±0.2 |",
        "|---|---|---|",
        f"| Корреляция θ̂ с истинным θ | {a.corr_theta:.3f} | {nz.corr_theta:.3f} |",
        f"| RMSE θ | {a.rmse_theta:.3f} | {nz.rmse_theta:.3f} |",
        f"| Средняя SE | {a.mean_se:.3f} | {nz.mean_se:.3f} |",
        f"| Грейд точно | {_pct(a.grade_exact)} | {_pct(nz.grade_exact)} |",
        f"| Грейд ±1 | {_pct(a.grade_within1)} | {_pct(nz.grade_within1)} |",
        f"| Грейд точно (θ дальше 0.25 от порога) | {_pct(a.grade_exact_far)} | "
        f"{_pct(nz.grade_exact_far)} |",
        f"| Средняя длина теста | {a.mean_length:.1f} | {nz.mean_length:.1f} |",
        f"| Максимальная длина | {a.max_length} | {nz.max_length} |",
        f"| Доля тестов, остановленных по SE < 0.35 | {_pct(a.share_se_target)} | "
        f"{_pct(nz.share_se_target)} |",
        f"| Повтор: тот же грейд | {_pct(s.agreement)} | |",
        f"| Повтор: каппа Коэна | {s.kappa:.3f} | |",
        f"| Повтор: корреляция θ̂₁ и θ̂₂ | {s.retest_corr:.3f} | |",
        f"| Повтор: то же решение по заявленному грейду (подтверждён / нет) | "
        f"{_pct(s.decision_agreement)} | |",
        f"| Повтор: каппа Коэна для решения | {s.decision_kappa:.3f} | |",
        f"| Средняя a банка | {b.mean_a:.2f} | |",
        f"| r_pb в адаптивном тесте (средняя / доля > 0.2) | {b.cat_rpb_mean:.3f} / "
        f"{_pct(b.cat_rpb_share_02)} | |",
        f"| r_pb на линейной форме 30 задач (средняя / доля > 0.2) | {b.linear_rpb_mean:.3f} / "
        f"{_pct(b.linear_rpb_share_02)} | |",
        f"| Максимальная доля показов одной задачи | {_pct(b.max_exposure)} | |",
        "",
        "Решения по заявленному грейду: "
        + ", ".join(f"{k} {_pct(v)}" for k, v in a.decisions.items()),
        "",
        f"## Утечка: {lk.n_leaked} задач (20%) слиты, {lk.n_cheaters} читеров (10%)",
        "",
        "| Режим | θ̂−θ у читеров | Грейд завышен у читеров | ... у честных | "
        "Детектор задач: точность / полнота (среди показанных ≥30 раз) | "
        "Выведено задач по ходу | Детектор кандидатов: точность / полнота |",
        "|---|---|---|---|---|---|---|",
    ]
    for m in lk.modes:
        lines.append(
            f"| {m.mode} | {m.cheater_bias:+.2f} | {_pct(m.cheater_inflated)} | "
            f"{_pct(m.honest_inflated)} | {_pct(m.item_precision)} / {_pct(m.item_recall)} "
            f"({_pct(m.recall_exposed)}) | {m.retired} | "
            f"{_pct(m.cand_precision)} / {_pct(m.cand_recall)} |"
        )
    lines += [
        "",
        "Полнота детектора задач по сигналам (режим без защиты): "
        + "; ".join(
            f"IRT {_pct(m.recall_irt)}, скорость {_pct(m.recall_fast)}" for m in lk.modes[1:2]
        ),
    ]
    lines += [
        "",
        f"## Размер банка ({r['sizes'][0].n_candidates} кандидатов на каждый размер)",
        "",
        "| Задач в банке | Корреляция θ | Средняя SE | Грейд точно | Средняя длина |",
        "|---|---|---|---|---|",
    ]
    for row in r["sizes"]:
        lines.append(
            f"| {row.n_items} | {row.corr_theta:.3f} | {row.mean_se:.3f} | "
            f"{_pct(row.grade_exact)} | {row.mean_length:.1f} |"
        )
    lg: BaseResults = r["longer"]
    lines += [
        "",
        "## Длина теста: по умолчанию и длиннее (настройка CATConfig)",
        "",
        "| Правило остановки | Корреляция θ | Грейд точно | Средняя длина | "
        "Повтор: тот же грейд / каппа | Повтор: то же решение |",
        "|---|---|---|---|---|---|",
        f"| SE < 0.35 или 15 задач (по умолчанию) | {a.corr_theta:.3f} | {_pct(a.grade_exact)} "
        f"| {a.mean_length:.1f} | {_pct(s.agreement)} / {s.kappa:.3f} | "
        f"{_pct(s.decision_agreement)} |",
        f"| SE < 0.30 или 20 задач | {lg.accuracy.corr_theta:.3f} | "
        f"{_pct(lg.accuracy.grade_exact)} | {lg.accuracy.mean_length:.1f} | "
        f"{_pct(lg.stability.agreement)} / {lg.stability.kappa:.3f} | "
        f"{_pct(lg.stability.decision_agreement)} |",
    ]
    lines += [
        "",
        f"## Калибровка: {cal.n_items} пилотных задач × {cal.responses_per_item} ответов",
        "",
        f"RMSE a = {cal.rmse_a:.3f}, RMSE b = {cal.rmse_b:.3f}, "
        f"переведено в active: {_pct(cal.activated)}",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Симуляция механики тестирования")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--n", type=int, default=1000, help="число синтетических кандидатов")
    args = parser.parse_args(argv)
    t0 = time.perf_counter()
    report = format_report(run_all(args.seed, args.n))
    print(report)
    print(f"\n_Время прогона: {time.perf_counter() - t0:.0f} с_")


if __name__ == "__main__":
    main()
