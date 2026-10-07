# ruff: noqa: I001 — `common` подключает backend в sys.path и должен импортироваться до `app.*`
"""Метрики подбора на синтетике (T11.5): настоящая выдача платформы против базовых линий.

Платформа видит только то, что видела бы в жизни (`app.eval.synthetic.system_view`): стек
из резюме (приведённый к справочнику тем же `normalize_skill`, что и разбор резюме),
категорию и θ̂ из теста, зарплату, форматы, ФСП-скор, свежесть.
Выдача — `app.eval.ranking.system_order` (код подбора 3b).
Эталон — `synth.relevance` (по скрытой правде).
"""

from __future__ import annotations

import random
from collections.abc import Callable, Hashable, Sequence
from typing import Any
from unittest import mock

import numpy as np
from common import SPECS

from app.eval import metrics as m
from app.eval.ranking import BM25, keyword_order, system_order, tier
from app.matching.scoring import weights_from
from app.nlp import skills_lexicon
from app.eval.synthetic import system_view
from app.nlp.skills_lexicon import catalog

K = 10
K_RECALL = 50


def raw_stack(resume_skills: Sequence[str]) -> list[str]:
    """Стек «как написано»: совпадает с кодом только при точном написании кода.

    Остальное помечаем префиксом, который справочник синонимов не распознаёт
    (иначе `normalize_skill` внутри `stack_match` всё равно найдёт синоним)."""
    out = []
    for s in resume_skills:
        low = s.strip().lower()
        out.append(low if low in catalog() else f"zzzz{low.replace(' ', '_')}")
    return out


def evaluate(
    orders: dict[str, list[Hashable]],
    gold: dict[str, dict[str, int]],
    all_ids: Sequence[str],
) -> dict[str, Any]:
    """Метрики по потребностям для заданного порядка выдачи."""
    rows = []
    for need_id, order in orders.items():
        g = gold.get(need_id, {})
        ranked = [g.get(str(cid), 0) for cid in order]
        ideal = [g.get(cid, 0) for cid in all_ids]
        n_rel = sum(1 for v in g.values() if v == 2)
        rows.append(
            {
                "need_id": need_id,
                "p10": m.precision_at_k(ranked, K, min_rel=2),
                "p10_soft": m.precision_at_k(ranked, K, min_rel=1),
                "ndcg10": m.ndcg_at_k(ranked, K, ideal),
                "r50": m.recall_at_k(ranked, K_RECALL, n_rel, min_rel=2),
                "r10": m.recall_at_k(ranked, K, n_rel, min_rel=2),
                "relevant_total": n_rel,
            }
        )
    return summarize(rows)


def summarize(rows: list[dict[str, Any]], seed: int = 7) -> dict[str, Any]:
    out: dict[str, Any] = {"per_need": rows}
    for key in ("p10", "p10_soft", "ndcg10", "r50", "r10"):
        vals = [r[key] for r in rows]
        out[key] = m.mean(vals)
        out[f"{key}_ci"] = m.bootstrap_ci(vals, seed=seed)
    total_rel = sum(r["relevant_total"] for r in rows)
    out["relevant_in_top_share"] = (
        sum(r["r10"] * r["relevant_total"] for r in rows) / total_rel if total_rel else 0.0
    )
    return out


def run_matching(
    candidates: list[dict[str, Any]],
    needs: list[dict[str, Any]],
    gold_rows: list[list[Any]],
    seed: int,
) -> dict[str, Any]:
    gold: dict[str, dict[str, int]] = {}
    for need_id, cid, rel in gold_rows:
        gold.setdefault(need_id, {})[cid] = int(rel)
    all_ids = [c["id"] for c in candidates]
    weights = weights_from({})
    views = [system_view(c) for c in candidates]
    views_retest = [system_view(c, test_key="retest") for c in candidates]
    views_declared = [system_view(c, use_test=False) for c in candidates]

    def orders_for(
        vs: Sequence[dict[str, Any]],
        w: dict[str, float] = weights,
        use_category: bool = True,
    ) -> dict[str, list[Hashable]]:
        return {
            n["id"]: system_order(n, vs, w, use_category=use_category, top_n=K_RECALL)
            for n in needs
        }

    def without(factor: str) -> dict[str, float]:
        return weights_from({"ranking_weights": {**weights, factor: 0.0}})

    systems: dict[str, dict[str, Any]] = {}
    main_orders = orders_for(views)
    systems["system"] = evaluate(main_orders, gold, all_ids)

    # Базовая линия 1: ключевые слова резюме (BM25 по всей базе)
    index = BM25({c["id"]: c["resume_text"] for c in candidates})
    kw_orders = {n["id"]: keyword_order(n["keyword_query"], index, all_ids) for n in needs}
    systems["keywords"] = evaluate(kw_orders, gold, all_ids)

    # Базовая линия 2: случайный порядок всей базы (ожидание, 20 перестановок)
    systems["random"] = _random_eval(needs, gold, all_ids, seed, lambda n, ids: ids)
    # Только категория из теста, внутри — случайно (вклад категоризации без формулы счёта)
    view_by_id = {v["id"]: v for v in views}
    systems["category_random"] = _random_eval(
        needs,
        gold,
        all_ids,
        seed + 1,
        lambda n, ids: sorted(ids, key=lambda i: tier(n, view_by_id[i]["category"])),
    )

    # Абляции: что даёт каждый компонент
    ablations = {
        "no_theta": orders_for(views, without("theta")),
        "no_fsp": orders_for(views, without("fsp")),
        "no_stack": orders_for(views, without("stack")),
        "no_category": orders_for(views, use_category=False),
        "no_test": orders_for(views_declared),
    }
    with mock.patch.dict(skills_lexicon.ADJACENCY, clear=True):
        raw_views = [
            {**v, "stack": raw_stack(c["resume_skills"])}
            for v, c in zip(views, candidates, strict=True)
        ]
        ablations["no_proximity"] = orders_for(raw_views)
    for name, orders in ablations.items():
        systems[name] = evaluate(orders, gold, all_ids)

    # Чувствительность к весу θ (остальные веса пропорционально)
    theta_sweep = []
    for wt in (0.0, 0.1, 0.25, 0.4):
        w = weights_from({"ranking_weights": {**weights, "theta": wt}})
        res = evaluate(orders_for(views, w), gold, all_ids)
        theta_sweep.append({"theta_weight": wt, "p10": res["p10"], "ndcg10": res["ndcg10"]})

    # Устойчивость выдачи: кандидаты прошли тест второй раз — насколько совпал топ-10
    retest_orders = orders_for(views_retest)
    overlaps = [m.overlap_at_k(main_orders[n["id"]], retest_orders[n["id"]], K) for n in needs]

    # Сравнение по потребностям: где платформа лучше ключевых слов по nDCG@10
    wins = ties = losses = 0
    for a, b in zip(systems["system"]["per_need"], systems["keywords"]["per_need"], strict=True):
        if a["ndcg10"] > b["ndcg10"] + 1e-9:
            wins += 1
        elif a["ndcg10"] < b["ndcg10"] - 1e-9:
            losses += 1
        else:
            ties += 1

    per_spec = {}
    for spec in SPECS:
        ids = {n["id"] for n in needs if n["specialization"] == spec}

        def avg(sysname: str, key: str, ids: set[str] = ids) -> float:
            vals = [r[key] for r in systems[sysname]["per_need"] if r["need_id"] in ids]
            return m.mean(vals)

        per_spec[spec] = {
            "needs": len(ids),
            "system_p10": avg("system", "p10"),
            "keywords_p10": avg("keywords", "p10"),
            "system_ndcg10": avg("system", "ndcg10"),
            "keywords_ndcg10": avg("keywords", "ndcg10"),
        }
    rel_counts = [systems["system"]["per_need"][i]["relevant_total"] for i in range(len(needs))]
    primary_sizes = [sum(1 for v in views if v["category"] == n["category"]) for n in needs]
    return {
        "systems": systems,
        "theta_sweep": theta_sweep,
        "stability_overlap10": m.mean(overlaps),
        "stability_overlap10_min": float(min(overlaps)),
        "wins_ties_losses": [wins, ties, losses],
        "per_spec": per_spec,
        "relevant_per_need_mean": m.mean(rel_counts),
        "relevant_per_need_min": int(min(rel_counts)),
        "relevant_per_need_max": int(max(rel_counts)),
        "partial_per_need_mean": m.mean(
            [sum(1 for v in gold.get(n["id"], {}).values() if v == 1) for n in needs]
        ),
        "primary_pool_mean": m.mean(primary_sizes),
        "main_orders": main_orders,
    }


def _random_eval(
    needs: list[dict[str, Any]],
    gold: dict[str, dict[str, int]],
    all_ids: list[str],
    seed: int,
    arrange: Callable[[dict[str, Any], list[str]], list[str]],
    reps: int = 20,
) -> dict[str, Any]:
    rnd = random.Random(seed)
    per_rep = []
    for _ in range(reps):
        orders = {}
        for n in needs:
            ids = list(all_ids)
            rnd.shuffle(ids)
            orders[n["id"]] = arrange(n, ids)
        per_rep.append(evaluate(orders, gold, all_ids)["per_need"])
    rows = []
    for i, n in enumerate(needs):
        row = {"need_id": n["id"], "relevant_total": per_rep[0][i]["relevant_total"]}
        for key in ("p10", "p10_soft", "ndcg10", "r50", "r10"):
            row[key] = float(np.mean([rep[i][key] for rep in per_rep]))
        rows.append(row)
    return summarize(rows)
