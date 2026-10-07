"""Метрики валидации и выдача для оценки (T11.3, T11.5) на примерах с известным ответом."""

import math
from typing import Any

import pytest

from app.eval import metrics as m
from app.eval.ranking import (
    BM25,
    TIER_NO_CATEGORY,
    TIER_OTHER,
    TIER_PRIMARY,
    TIER_RECOMMENDED,
    keyword_order,
    overlap_order,
    recommended_categories,
    system_order,
    system_scores,
    tier,
)
from app.matching.scoring import NeedLike, score_candidate, weights_from


def test_precision_at_k() -> None:
    ranked = [1, 0, 1, 1, 0, 0, 0, 0, 0, 0, 1]
    assert m.precision_at_k(ranked, 10) == pytest.approx(0.3)
    assert m.precision_at_k(ranked, 1) == 1.0
    # короткий список: делим на его длину, а не на k
    assert m.precision_at_k([1, 0], 10) == 0.5
    assert m.precision_at_k([], 10) == 0.0
    # оценки 0/1/2: «релевантен» = не ниже min_rel
    assert m.precision_at_k([2, 1, 0, 2], 4, min_rel=2) == 0.5
    assert m.precision_at_k([2, 1, 0, 2], 4, min_rel=1) == 0.75


def test_recall_at_k() -> None:
    ranked = [1, 0, 1, 0, 1]
    assert m.recall_at_k(ranked, 2) == pytest.approx(1 / 3)
    assert m.recall_at_k(ranked, 5) == 1.0
    # релевантные, которых нет в выдаче, снижают полноту
    assert m.recall_at_k(ranked, 5, total_relevant=6) == 0.5
    assert m.recall_at_k([0, 0], 2) == 0.0


def test_ndcg_known_values() -> None:
    assert m.ndcg_at_k([1, 1, 0], 3) == 1.0
    # [0, 1]: DCG = 1/log2(3), идеал [1, 0]: DCG = 1
    assert m.ndcg_at_k([0, 1], 2) == pytest.approx(1 / math.log2(3))
    # оценки 2/1: выигрыш 2^rel − 1 → 3 и 1
    got = m.ndcg_at_k([1, 2], 2)
    want = (1 + 3 / math.log2(3)) / (3 + 1 / math.log2(3))
    assert got == pytest.approx(want)
    # идеал по всей базе: пропущенный релевантный снижает nDCG
    assert m.ndcg_at_k([1, 0], 2, ideal=[1, 0, 1]) == pytest.approx(1 / (1 + 1 / math.log2(3)))
    assert m.ndcg_at_k([0, 0], 2) == 0.0


def test_random_baselines() -> None:
    assert m.random_precision_at_k([1, 0, 0, 1], 2) == 0.5
    perfect = m.ndcg_at_k([1, 1, 0, 0], 2)
    rnd = m.random_ndcg_at_k([1, 1, 0, 0], 2, seed=1)
    assert 0 < rnd < perfect
    assert rnd == m.random_ndcg_at_k([1, 1, 0, 0], 2, seed=1)  # фиксированный seed


def test_bootstrap_ci_is_deterministic_and_covers_mean() -> None:
    vals = [0.1, 0.5, 0.9, 0.4, 0.6]
    lo, hi = m.bootstrap_ci(vals, seed=3)
    assert lo <= m.mean(vals) <= hi
    assert (lo, hi) == m.bootstrap_ci(vals, seed=3)
    assert m.bootstrap_ci([], seed=3) == (0.0, 0.0)


def test_kappa_pearson_overlap() -> None:
    assert m.cohens_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == 1.0
    # po = 0.5, pe = 0.5 → 0
    assert m.cohens_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"]) == 0.0
    # po = 0.8, pe = 0.5 → 0.6
    a = ["y"] * 5 + ["n"] * 5
    b = ["y", "y", "y", "y", "n", "n", "n", "n", "n", "y"]
    assert m.cohens_kappa(a, b) == pytest.approx(0.6)
    with pytest.raises(ValueError):
        m.cohens_kappa(["a"], [])
    assert m.pearson([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0)
    assert m.pearson([1, 1], [1, 2]) == 0.0
    assert m.overlap_at_k([1, 2, 3, 4], [2, 1, 9, 8], 2) == 1.0
    assert m.overlap_at_k([1, 2, 3, 4], [3, 4, 1, 2], 2) == 0.0


NEED = {
    "specialization": "backend",
    "grade": "middle",
    "skills_required": ["python", "postgresql"],
    "skills_desired": ["redis"],
    "salary_from": 200_000,
    "salary_to": 260_000,
    "work_format": "remote",
}


def cand(
    cid: str, category: str | None, stack: list[str], theta: float | None = 0.5
) -> dict[str, Any]:
    return {
        "id": cid,
        "category": category,
        "stack": stack,
        "theta": theta,
        "topic_scores": [],
        "fsp_id": None,
        "fsp_score": None,
        "fsp_badges": [],
        "privacy": {},
        "freshness": 0.0,
        "min_salary": 180_000,
        "work_formats": ["remote"],
        "category_label": None,
    }


def test_tiers_follow_recommended_categories() -> None:
    assert recommended_categories("backend", "middle") == [
        "backend:junior",
        "backend:senior",
        "devops:middle",
        "data_ml:middle",
    ]
    assert recommended_categories("mobile", "intern") == ["mobile:junior", "frontend:intern"]
    assert tier(NEED, "backend:middle") == TIER_PRIMARY
    assert tier(NEED, "backend:senior") == TIER_RECOMMENDED
    assert tier(NEED, "qa:middle") == TIER_OTHER
    assert tier(NEED, None) == TIER_NO_CATEGORY


def test_system_order_uses_category_then_real_score() -> None:
    cands = [
        cand("a", "backend:senior", ["python", "postgresql", "redis"]),  # сосед, идеальный стек
        cand("b", "backend:middle", ["python"]),
        cand("c", "backend:middle", ["питон", "постгрес"]),  # синонимы → полный стек
        cand("d", None, ["python", "postgresql"]),
        cand("e", "qa:middle", ["python", "postgresql"]),
    ]
    order = system_order(NEED, cands)
    assert order == ["c", "b", "a", "e", "d"]
    # счёт — ровно score_candidate из подбора 3b
    weights = weights_from({})
    target = NeedLike(["python", "postgresql"], ["redis"], 200_000, 260_000, "remote")
    scores = system_scores(NEED, cands, weights)
    for c in cands:
        assert scores[c["id"]] == score_candidate(c, target, weights, str)["score"]
    # без категорий — только по счёту: идеальный стек соседа выходит первым
    assert system_order(NEED, cands, use_category=False)[0] == "a"
    # top_n: досчитываются только нужные ярусы, первые места не меняются
    assert system_order(NEED, cands, top_n=2)[:2] == ["c", "b"]


def test_keyword_baselines() -> None:
    docs = {
        "1": "Middle Backend-разработчик. Навыки: Python, PostgreSQL",
        "2": "Senior Frontend-разработчик. Навыки: React",
        "3": "Middle Backend. Навыки: питон, постгрес",  # синонимы BM25 не узнаёт
    }
    index = BM25(docs)
    order = keyword_order("Middle backend Python PostgreSQL", index, ["1", "2", "3"])
    assert order[0] == "1"
    assert index.score("Python", "3") == 0.0
    cands = [{"id": 1, "stack": ["react"]}, {"id": 2, "stack": ["python", "postgresql"]}]
    assert overlap_order(NEED, cands) == [2, 1]
