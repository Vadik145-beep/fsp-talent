import numpy as np
import pytest

from app.testing.engine.irt import prob
from app.testing.engine.leak import (
    CandidateResponse,
    ItemObservation,
    LeakConfig,
    candidate_anomalies,
    detect_leaks,
    estimate_fast_baseline,
    flagged_item_ids,
    item_leak_report,
    poisson_sf,
    precision_recall,
)


def honest_obs(item_id, a, b, n, rng, median=60.0):
    out = []
    for _ in range(n):
        th = rng.normal()
        out.append(
            ItemObservation(
                item_id, th, bool(rng.random() < prob(th, a, b)), median * rng.lognormal(0, 0.35)
            )
        )
    return out


def leaked_obs(item_id, a, b, n, rng, share, fast=True, median=60.0):
    out = []
    for _ in range(n):
        th = rng.normal()
        if rng.random() < share:
            t = median * 0.2 if fast else median * rng.lognormal(0, 0.35)
            out.append(ItemObservation(item_id, th, True, t))
        else:
            out.append(
                ItemObservation(
                    item_id,
                    th,
                    bool(rng.random() < prob(th, a, b)),
                    median * rng.lognormal(0, 0.35),
                )
            )
    return out


def test_poisson_sf():
    assert poisson_sf(0, 2.0) == 1.0
    assert poisson_sf(1, 2.0) == pytest.approx(1 - np.exp(-2.0))
    assert poisson_sf(3, 0.0) == 0.0
    assert poisson_sf(10, 1.0) < 1e-6


def test_honest_item_not_flagged():
    rng = np.random.default_rng(0)
    for k in range(20):
        r = item_leak_report(f"i{k}", 1.3, 0.5, honest_obs(f"i{k}", 1.3, 0.5, 300, rng))
        assert not r.flagged, r


def test_irt_drift_detects_mass_leak():
    rng = np.random.default_rng(1)
    obs = leaked_obs("x", 1.3, 1.0, 300, rng, share=0.35, fast=False)
    r = item_leak_report("x", 1.3, 1.0, obs)
    assert "irt_drift" in r.reasons and r.diff > 0.1 and r.z > 3.5


def test_fast_correct_detects_small_leak():
    rng = np.random.default_rng(2)
    obs = leaked_obs("x", 1.3, 1.0, 120, rng, share=0.1, fast=True)
    r = item_leak_report("x", 1.3, 1.0, obs)
    assert "fast_correct" in r.reasons and r.fast_correct >= 8


def test_min_n_guard_and_window():
    rng = np.random.default_rng(3)
    few = leaked_obs("x", 1.3, 1.0, 20, rng, share=0.8)
    assert not item_leak_report("x", 1.3, 1.0, few).flagged
    # утечка давно закончилась: в окне последних 300 только честные ответы
    old = leaked_obs("x", 1.3, 1.0, 300, rng, share=0.5) + honest_obs("x", 1.3, 1.0, 300, rng)
    assert not item_leak_report("x", 1.3, 1.0, old, LeakConfig(window=300)).flagged
    assert item_leak_report("x", 1.3, 1.0, [], LeakConfig()).n == 0


def test_detect_leaks_over_bank():
    rng = np.random.default_rng(4)
    params = {f"i{k}": (1.3, float(rng.uniform(-1, 1))) for k in range(40)}
    leaked = {f"i{k}" for k in range(8)}
    obs = []
    for item_id, (a, b) in params.items():
        if item_id in leaked:
            obs += leaked_obs(item_id, a, b, 150, rng, share=0.15)
        else:
            obs += honest_obs(item_id, a, b, 150, rng)
    obs.append(ItemObservation("unknown", 0.0, True, 10.0))  # нет параметров — пропуск
    reports = detect_leaks(obs, params)
    flagged = set(flagged_item_ids(reports))
    precision, recall = precision_recall(flagged, leaked)
    assert precision == 1.0 and recall >= 0.85
    assert reports[0].flagged  # помеченные сверху
    assert all(r.item_id != "unknown" for r in reports)


def test_fast_baseline_is_robust_to_leaked_items():
    honest = [(1, 200)] * 60  # 0.5% быстрых верных
    leaked = [(40, 200)] * 40  # 20% быстрых верных
    assert estimate_fast_baseline(honest + leaked, trim=0.5, floor=0.001) == pytest.approx(0.005)
    assert estimate_fast_baseline([], floor=0.005) == 0.005


def test_candidate_anomalies():
    rng = np.random.default_rng(5)
    honest = [
        CandidateResponse(f"i{k}", 1.4, b, bool(rng.random() < prob(0.0, 1.4, b)), 60.0, 60.0)
        for k, b in enumerate(np.linspace(-1, 1, 12))
    ]
    assert not candidate_anomalies(honest).flagged
    # слабый кандидат быстро и верно отвечает на три сложные задачи
    cheater = [CandidateResponse(f"e{k}", 1.4, -1.5, k % 2 == 0, 60.0, 60.0) for k in range(8)]
    cheater += [CandidateResponse(f"h{k}", 1.4, 2.0, True, 8.0, 60.0) for k in range(3)]
    rep = candidate_anomalies(cheater)
    assert rep.flagged and "fast_hard_correct" in rep.reasons
    assert set(rep.suspicious_item_ids) == {"h0", "h1", "h2"}
    assert not candidate_anomalies([]).flagged


def test_precision_recall_edge_cases():
    assert precision_recall([], []) == (1.0, 1.0)
    assert precision_recall(["a", "b"], ["a"]) == (0.5, 1.0)
