# ruff: noqa: I001 — `common` подключает backend в sys.path и должен импортироваться до `app.*`
"""Симуляция теста на настоящем банке (T11.3, T11.4).

Каждый синтетический кандидат проходит НАСТОЯЩИЙ `CATSession` движка по банку своей
специализации (`bank_registry()`: 192 шаблона, по 32 на направление, их a и b) с настройками
стенда (`TestingSettings`: до 20 задач, стоп при SE < 0,30, минимум 6; лимит экспозиции
выключен, пока в направлении < 100 шаблонов). Ответ верен с вероятностью 2PL от ИСТИННОГО θ.

Онбординг повторяет правила платформы (`decide`): тест на заявленный грейд; не прошёл —
тест на грейд ниже (и так до прохождения); прошёл уверенно — один тест на грейд выше.
Итоговая категория = специализация × присвоенный грейд.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from typing import Any

import numpy as np
from common import GRADES, SPECS

from app.testing.engine import BankItem, CATConfig, decide, prob
from app.testing.engine.bank import bank_registry
from app.testing.engine.leak import LeakConfig, detect_leaks, precision_recall
from app.testing.engine.simulate import (
    LeakSetup,
    PopulationRun,
    SessionOutcome,
    SimCandidate,
    SimItem,
    accuracy_metrics,
    candidate_flags,
    item_point_biserials,
    run_population,
    stability_metrics,
)
from app.testing.settings import TestingSettings
from app.eval.metrics import cohens_kappa, pearson

THRESHOLDS = (-1.0, 0.0, 1.0)


def stand_config() -> CATConfig:
    s = TestingSettings()
    return CATConfig(
        se_target=s.cat_se_stop,
        max_items=s.cat_max_items,
        min_items=s.cat_min_items,
        max_exposure_rate=1.0,  # банк направления < exposure_min_bank (100) — лимит выключен
    )


def spec_items(
    spec: str, *, noise: float = 0.0, rng: np.random.Generator | None = None
) -> list[SimItem]:
    """Шаблоны направления: движок видит a, b реестра; ответы — по «истинным» a, b.

    noise > 0 — истинные параметры отличаются от экспертных (b ± noise, a × e^(±noise)).
    """
    out = []
    for t in bank_registry():
        if t.specialization != spec:
            continue
        a, b = float(t.a), float(t.b)
        if noise > 0 and rng is not None:
            a = float(np.clip(a * math.exp(rng.normal(0, noise)), 0.3, 3.0))
            b = float(b + rng.normal(0, noise))
        out.append(SimItem(BankItem.from_template(t), a, b, float(t.time_limit_s) / 3))
    return out


def _sim(c: dict[str, Any], claimed: str, cid: int) -> SimCandidate:
    return SimCandidate(cid, float(c["truth"]["theta"]), claimed)


def onboarding(
    cands: Sequence[dict[str, Any]], items: Sequence[SimItem], cfg: CATConfig, seed: int
) -> tuple[dict[str, dict[str, Any]], PopulationRun]:
    """Цепочка тестов до категории. Возвращает итог по кандидату и прогон первого теста."""
    idx = {n: c for n, c in enumerate(cands)}
    state: dict[int, dict[str, Any]] = {
        n: {"granted": None, "theta": None, "se": None, "sessions": []} for n in idx
    }
    pending: dict[int, tuple[str, str]] = {
        n: (c["declared_grade"], "first") for n, c in idx.items()
    }
    first_run: PopulationRun | None = None
    for rnd in range(6):
        if not pending:
            break
        batch = [_sim(idx[n], claimed, n) for n, (claimed, _) in sorted(pending.items())]
        run = run_population(batch, items, config=cfg, seed=seed + 7919 * rnd)
        if first_run is None:
            first_run = run
        nxt: dict[int, tuple[str, str]] = {}
        for out in run.outcomes:
            n = out.cid
            claimed, phase = pending[n]
            st = state[n]
            d = decide(out.theta, out.se, claimed, current_grade=st["granted"])
            st["sessions"].append(
                {
                    "claimed": claimed,
                    "theta": round(out.theta, 4),
                    "se": round(out.se, 4),
                    "n_items": out.n_scored,
                    "outcome": d.outcome,
                }
            )
            passed = d.outcome != "suggest_lower"
            gi = GRADES.index(claimed)
            if passed:
                st.update(granted=claimed, theta=out.theta, se=out.se)
                if phase == "first" and d.outcome == "suggest_higher" and gi < 3:
                    nxt[n] = (GRADES[gi + 1], "up")
            elif phase in ("first", "down") and gi > 0:
                nxt[n] = (GRADES[gi - 1], "down")
        pending = nxt
    assert first_run is not None
    result = {}
    for n, c in idx.items():
        st = state[n]
        result[c["id"]] = {
            "grade": st["granted"],
            "category": f"{c['specialization']}:{st['granted']}" if st["granted"] else None,
            "theta": round(st["theta"], 4) if st["theta"] is not None else None,
            "se": round(st["se"], 4) if st["se"] is not None else None,
            "first_theta": st["sessions"][0]["theta"],
            "first_se": st["sessions"][0]["se"],
            "first_outcome": st["sessions"][0]["outcome"],
            "n_items": st["sessions"][0]["n_items"],
            "tests": len(st["sessions"]),
        }
    return result, first_run


def linear_form_rpb(
    cands: Sequence[dict[str, Any]], items: Sequence[SimItem], rng: np.random.Generator
) -> list[tuple[str, float, float]]:
    """Классический анализ задач: каждый решает ВСЕ шаблоны направления; r_pb = корреляция
    ответа на задачу с суммой по остальным. Возвращает (id, a, r_pb)."""
    thetas = np.array([c["truth"]["theta"] for c in cands])
    x = np.array(
        [[rng.random() < prob(float(t), it.true_a, it.true_b) for it in items] for t in thetas],
        dtype=float,
    )
    total = x.sum(axis=1)
    return [
        (
            it.bank_item.item_id,
            it.bank_item.a,
            pearson(x[:, j].tolist(), (total - x[:, j]).tolist()),
        )
        for j, it in enumerate(items)
    ]


def _grade(theta: float) -> str:
    j, m, s = THRESHOLDS
    return (
        "senior" if theta >= s else "middle" if theta >= m else "junior" if theta >= j else "intern"
    )


def _far(theta: float, margin: float = 0.25) -> bool:
    return min(abs(theta - c) for c in THRESHOLDS) > margin


def run_main(candidates: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    """Точность, стабильность повтора, различающая сила; категории для подбора."""
    cfg = stand_config()
    by_spec: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in candidates:
        by_spec[c["specialization"]].append(c)
    first: dict[str, dict[str, Any]] = {}
    second: dict[str, dict[str, Any]] = {}
    outcomes1: list[SessionOutcome] = []
    outcomes2: list[SessionOutcome] = []
    rpb_adaptive: dict[str, float] = {}
    rpb_linear: list[tuple[str, float, float]] = []
    for k, spec in enumerate(SPECS):
        cands = by_spec[spec]
        items = spec_items(spec)
        r1, run1 = onboarding(cands, items, cfg, seed + 1000 * k + 1)
        r2, run2 = onboarding(cands, items, cfg, seed + 1000 * k + 2)
        first.update(r1)
        second.update(r2)
        outcomes1 += run1.outcomes
        outcomes2 += run2.outcomes
        rpb_adaptive.update(item_point_biserials(run1.observations, min_n=30))
        rpb_linear += linear_form_rpb(cands, items, np.random.default_rng(seed + 1000 * k + 3))

    acc = accuracy_metrics(outcomes1, se_target=cfg.se_target)
    stab = stability_metrics(outcomes1, outcomes2)
    true_g = [c["truth"]["grade"] for c in candidates]
    cat1 = [first[c["id"]]["grade"] or "none" for c in candidates]
    cat2 = [second[c["id"]]["grade"] or "none" for c in candidates]
    far = [i for i, c in enumerate(candidates) if _far(c["truth"]["theta"])]

    def exact(idx: Sequence[int]) -> float:
        return sum(cat1[i] == true_g[i] for i in idx) / len(idx) if idx else 0.0

    per_grade = {}
    for g in GRADES:
        idx = [i for i, t in enumerate(true_g) if t == g]
        per_grade[g] = {
            "n": len(idx),
            "exact": exact(idx),
            "within_one": sum(abs(GRADES.index(cat1[i]) - GRADES.index(g)) <= 1 for i in idx)
            / len(idx),
            "theta_exact": sum(_grade(outcomes_theta(first, candidates[i])) == g for i in idx)
            / len(idx),
        }
    per_spec = {}
    for spec in SPECS:
        idx = [i for i, c in enumerate(candidates) if c["specialization"] == spec]
        per_spec[spec] = {"n": len(idx), "exact": exact(idx)}
    declared_over = [
        i
        for i, c in enumerate(candidates)
        if GRADES.index(c["declared_grade"]) > GRADES.index(c["truth"]["grade"])
    ]
    lengths = [first[c["id"]]["n_items"] for c in candidates]
    hist = {n: lengths.count(n) for n in sorted(set(lengths))}
    linear_vals = [r for _, _, r in rpb_linear]
    adaptive_vals = list(rpb_adaptive.values())
    return {
        "categories": first,
        "categories_retest": second,
        "accuracy": {
            "n": acc.n,
            "corr_theta": acc.corr_theta,
            "rmse_theta": acc.rmse_theta,
            "mean_se": acc.mean_se,
            "grade_exact": acc.grade_exact,
            "grade_within1": acc.grade_within1,
            "grade_exact_far": acc.grade_exact_far,
            "mean_length": acc.mean_length,
            "max_length": acc.max_length,
            "share_se_target": acc.share_se_target,
            "decisions": acc.decisions,
            "length_hist": hist,
            "scatter": [(c["truth"]["theta"], first[c["id"]]["first_theta"]) for c in candidates],
        },
        "category": {
            "exact": exact(range(len(candidates))),
            "within_one": sum(
                abs(GRADES.index(a) - GRADES.index(b)) <= 1
                for a, b in zip(cat1, true_g, strict=True)
            )
            / len(candidates),
            "exact_far": exact(far),
            "share_far": len(far) / len(candidates),
            "per_grade": per_grade,
            "per_spec": per_spec,
            "mean_tests": float(np.mean([first[c["id"]]["tests"] for c in candidates])),
            "overclaimers": len(declared_over),
            "overclaimers_corrected": sum(cat1[i] == true_g[i] for i in declared_over)
            / max(1, len(declared_over)),
            "overclaimers_kept_inflated": sum(
                GRADES.index(cat1[i]) > GRADES.index(true_g[i]) for i in declared_over
            )
            / max(1, len(declared_over)),
            "declared_exact": sum(c["declared_grade"] == c["truth"]["grade"] for c in candidates)
            / len(candidates),
        },
        "stability": {
            "theta_grade_agreement": stab.agreement,
            "theta_grade_kappa": stab.kappa,
            "retest_corr": stab.retest_corr,
            "decision_agreement": stab.decision_agreement,
            "decision_kappa": stab.decision_kappa,
            "category_agreement": sum(a == b for a, b in zip(cat1, cat2, strict=True)) / len(cat1),
            "category_kappa": cohens_kappa(cat1, cat2),
        },
        "discrimination": {
            "mean_a": float(np.mean([a for _, a, _ in rpb_linear])),
            "linear_mean": float(np.mean(linear_vals)),
            "linear_share_02": float(np.mean([v > 0.2 for v in linear_vals])),
            "linear_min": float(np.min(linear_vals)),
            "adaptive_mean": float(np.mean(adaptive_vals)) if adaptive_vals else 0.0,
            "adaptive_share_02": float(np.mean([v > 0.2 for v in adaptive_vals]))
            if adaptive_vals
            else 0.0,
            "adaptive_n_items": len(adaptive_vals),
            "points": rpb_linear,
            "weak_items": sorted([i for i, _, r in rpb_linear if r <= 0.2]),
        },
    }


def outcomes_theta(first: dict[str, dict[str, Any]], cand: dict[str, Any]) -> float:
    return float(first[cand["id"]]["first_theta"])


def run_noise(candidates: list[dict[str, Any]], seed: int, noise: float = 0.3) -> dict[str, float]:
    """Устойчивость к ошибке экспертных a, b: ответы идут по «истинным», движок их не знает."""
    cfg = stand_config()
    outcomes: list[SessionOutcome] = []
    for k, spec in enumerate(SPECS):
        rng = np.random.default_rng(seed + 50 + k)
        items = spec_items(spec, noise=noise, rng=rng)
        batch = [
            _sim(c, c["declared_grade"], n)
            for n, c in enumerate(x for x in candidates if x["specialization"] == spec)
        ]
        outcomes += run_population(batch, items, config=cfg, seed=seed + 60 + k).outcomes
    acc = accuracy_metrics(outcomes, se_target=cfg.se_target)
    return {
        "noise": noise,
        "corr_theta": acc.corr_theta,
        "rmse_theta": acc.rmse_theta,
        "grade_exact": acc.grade_exact,
        "grade_within1": acc.grade_within1,
        "mean_length": acc.mean_length,
    }


def run_bank_sizes(
    candidates: list[dict[str, Any]], seed: int, sizes: Sequence[int] = (8, 12, 16, 24, 32)
) -> list[dict[str, float]]:
    """Точность при урезанном банке: первые k шаблонов случайной перестановки направления."""
    cfg = stand_config()
    rows = []
    perms = {}
    for k, spec in enumerate(SPECS):
        items = spec_items(spec)
        order = np.random.default_rng(seed + 70 + k).permutation(len(items)).tolist()
        perms[spec] = [items[i] for i in order]
    for size in sizes:
        outcomes: list[SessionOutcome] = []
        for k, spec in enumerate(SPECS):
            batch = [
                _sim(c, c["declared_grade"], n)
                for n, c in enumerate(x for x in candidates if x["specialization"] == spec)
            ]
            outcomes += run_population(
                batch, perms[spec][:size], config=cfg, seed=seed + 80 + k
            ).outcomes
        acc = accuracy_metrics(outcomes, se_target=cfg.se_target)
        rows.append(
            {
                "size": size,
                "corr_theta": acc.corr_theta,
                "mean_se": acc.mean_se,
                "grade_exact": acc.grade_exact,
                "mean_length": acc.mean_length,
            }
        )
    return rows


# --------------------------------------------------------------------------- утечка


def _sample_leaked(
    run: PopulationRun, items: Sequence[SimItem], share: float, rng: np.random.Generator
) -> frozenset[str]:
    """Утекает то, что показывали: вероятность ∝ числу показов в честном прогоне."""
    counts: dict[str, int] = defaultdict(int)
    for o in run.observations:
        counts[o.item_id] += 1
    ids = [it.bank_item.item_id for it in items]
    w = np.array([counts[i] + 1e-9 for i in ids], dtype=float)
    k = round(share * len(ids))
    picked = rng.choice(len(ids), size=k, replace=False, p=w / w.sum())
    return frozenset(ids[int(i)] for i in picked)


MODES = [
    ("none", "Нет утечки (фон)"),
    ("static", "Утечка, без защиты"),
    ("param", "Утечка + параметризация"),
    ("detector", "Утечка + детектор"),
    ("both", "Параметризация + детектор"),
]


def _leak_spec(args: tuple[int, int, int, float, float, float, int]) -> dict[str, Any]:
    """Сценарий утечки для одного направления (отдельный процесс, свой seed)."""
    k, seed, n_per_spec, leaked_share, cheater_share, variant_match_prob, every = args
    spec = SPECS[k]
    cfg = stand_config()
    lcfg = LeakConfig()
    rng = np.random.default_rng(seed + 300 + k)
    items = spec_items(spec)
    thetas = np.clip(rng.normal(0, 1, n_per_spec), -3.0, 3.0)
    shifts = rng.choice([-1, 0, 1], size=n_per_spec, p=[0.15, 0.6, 0.25])
    n_cheat = round(cheater_share * n_per_spec)
    cheaters = set(rng.choice(n_per_spec, size=n_cheat, replace=False).tolist())
    base_id = (k + 1) * 100_000
    cands = []
    for i in range(n_per_spec):
        gi = GRADES.index(_grade(float(thetas[i])))
        claimed = GRADES[min(max(gi + int(shifts[i]), 0), 3)]
        cands.append(SimCandidate(base_id + i, float(thetas[i]), claimed, i in cheaters))
    params = {it.bank_item.item_id: (it.bank_item.a, it.bank_item.b) for it in items}

    def run_mode(setup: LeakSetup, detector: int | None) -> PopulationRun:
        return run_population(
            cands,
            items,
            config=cfg,
            seed=seed + 400 + k,
            leak=setup,
            detector_every=detector,
            leak_config=lcfg,
        )

    background = run_mode(LeakSetup(frozenset()), None)
    leaked = _sample_leaked(background, items, leaked_share, rng)
    static = LeakSetup(leaked, parametrized=False)
    param = LeakSetup(leaked, parametrized=True, variant_match_prob=variant_match_prob)
    runs = {
        "none": (LeakSetup(frozenset()), background),
        "static": (static, run_mode(static, None)),
        "param": (param, run_mode(param, None)),
        "detector": (static, run_mode(static, every)),
        "both": (param, run_mode(param, every)),
    }
    out: dict[str, Any] = {
        "leaked": sorted(leaked),
        "cheater_ids": sorted(base_id + i for i in cheaters),
    }
    for mode, (setup, run) in runs.items():
        reports = detect_leaks(run.observations, params, lcfg)
        flagged = {r.item_id for r in reports if r.flagged} | {i for _, i in run.retired}
        out[mode] = {
            "flagged": sorted(flagged),
            "by_fast": sorted(r.item_id for r in reports if "fast_correct" in r.reasons),
            "by_irt": sorted(r.item_id for r in reports if "irt_drift" in r.reasons),
            "leaked": sorted(setup.leaked),
            "retired": len(run.retired),
            "cand_flags": sorted(candidate_flags(run)),
            "rows": [
                (
                    o.cheater,
                    GRADES.index(_grade(o.theta)) > GRADES.index(_grade(o.true_theta)),
                    o.theta - o.true_theta,
                )
                for o in run.outcomes
            ],
        }
    return out


def run_leak(
    seed: int,
    *,
    n_per_spec: int = 1000,
    leaked_share: float = 0.2,
    cheater_share: float = 0.1,
    variant_match_prob: float = 0.1,
    detector_every: int = 10,
    workers: int = 6,
) -> dict[str, Any]:
    """20% шаблонов каждого направления слиты, 10% кандидатов — читеры.

    Читер на слитой задаче без параметризации отвечает верно и быстро; с параметризацией
    слитый ответ подходит, только если попался тот же вариант (10% — консервативно:
    у шаблона ≥ 50 вариантов). Детектор (`detect_leaks`, настройки по умолчанию) запускается
    каждые `detector_every` сессий направления (на стенде — после каждой 50-й сессии
    по всем шести направлениям, то есть ~каждые 8 сессий направления) и выводит помеченные.
    Направления считаются параллельно; у каждого свой seed, поэтому результат не зависит
    от числа процессов.
    """
    args = [
        (k, seed, n_per_spec, leaked_share, cheater_share, variant_match_prob, detector_every)
        for k in range(len(SPECS))
    ]
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            parts = list(pool.map(_leak_spec, args))
    else:
        parts = [_leak_spec(a) for a in args]
    cheater_ids = {str(x) for p in parts for x in p["cheater_ids"]}
    modes = []
    for mode, label in MODES:
        flagged = {i for p in parts for i in p[mode]["flagged"]}
        leaked = {i for p in parts for i in p[mode]["leaked"]}
        by_fast = {i for p in parts for i in p[mode]["by_fast"]}
        by_irt = {i for p in parts for i in p[mode]["by_irt"]}
        rows = [r for p in parts for r in p[mode]["rows"]]
        cheat = [r for r in rows if r[0]]
        honest = [r for r in rows if not r[0]]
        ip, ir = precision_recall(flagged, leaked)
        cand_flags = {str(x) for p in parts for x in p[mode]["cand_flags"]}
        cp, cr = precision_recall(cand_flags, cheater_ids)
        has_leak = bool(leaked)
        modes.append(
            {
                "mode": mode,
                "label": label,
                "cheater_inflated": float(np.mean([r[1] for r in cheat])),
                "honest_inflated": float(np.mean([r[1] for r in honest])),
                "cheater_bias": float(np.mean([r[2] for r in cheat])),
                "item_precision": ip if flagged else None,
                "item_recall": ir if has_leak else None,
                "false_flags": len(flagged - leaked),
                "recall_fast": precision_recall(by_fast, leaked)[1] if has_leak else None,
                "recall_irt": precision_recall(by_irt, leaked)[1] if has_leak else None,
                "items_flagged": len(flagged),
                "retired": sum(p[mode]["retired"] for p in parts),
                "cand_precision": cp if cand_flags else None,
                "cand_recall": cr,
                "cand_flagged": len(cand_flags),
            }
        )
    return {
        "n_per_spec": n_per_spec,
        "n_total": n_per_spec * len(SPECS),
        "leaked_items": sum(len(p["leaked"]) for p in parts),
        "bank_items": sum(len(spec_items(s)) for s in SPECS),
        "cheaters": len(cheater_ids),
        "detector_every": detector_every,
        "variant_match_prob": variant_match_prob,
        "modes": modes,
    }
