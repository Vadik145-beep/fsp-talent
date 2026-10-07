# ruff: noqa: I001 — `common` подключает backend в sys.path и должен импортироваться до `app.*`
"""Валидация решения одной командой (E11): синтетика → тест → утечка → подбор → графики → отчёт.

    python scripts/validation/run_all.py            # из корня репозитория, ~3–4 минуты

Нужны зависимости бэкенда (`pip install -e "backend[dev]"`) и matplotlib (только для PNG;
в зависимости бэкенда не входит: `pip install matplotlib`). БД не нужна.
Seed фиксирован: повторный запуск даёт те же файлы (кроме даты прогона в results.json).

Пишет:
- data/validation/candidates.json, needs.json, gold.csv — синтетический набор и эталон;
- data/validation/example_pairs.csv — пример CSV для проверки через /api/eval/matching;
- data/validation/results.json — графики для экрана «Валидация» и все цифры;
- docs/validation/img/*.png, docs/validation/report.md — отчёт.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
from dataclasses import asdict
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import common
import numpy as np
from common import DATA_DIR, DOCS_DIR, IMG_DIR, N_CANDIDATES, N_NEEDS, SEED

import charts
import matching_sim
import report
import synth
import testing_sim
from app.eval.service import Pair, evaluate_synthetic
from app.eval.synthetic import Dataset, parse_stack


def _log(t0: float, msg: str) -> None:
    print(f"[{time.perf_counter() - t0:6.1f} с] {msg}", flush=True)


def write_candidates(cands: list[dict[str, Any]]) -> None:
    lines = ",\n".join(json.dumps(c, ensure_ascii=False, separators=(",", ":")) for c in cands)
    (DATA_DIR / "candidates.json").write_text(
        "[\n" + lines + "\n]\n", encoding="utf-8", newline="\n"
    )


def write_csv(path: Any, header: list[str], rows: list[list[Any]]) -> None:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8", newline="\n")


def _sample(rng: np.random.Generator, pool: list[str], k: int) -> list[str]:
    k = min(k, len(pool))
    return [pool[i] for i in sorted(rng.choice(len(pool), size=k, replace=False).tolist())]


def example_pairs(
    needs: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    gold: dict[tuple[str, str], int],
    seed: int,
    per_need: int = 40,
) -> list[list[Any]]:
    """Пример CSV для жюри: по одной потребности каждого направления, по 40 кандидатов.

    Кандидаты выбраны НЕЗАВИСИМО от выдачи платформы (иначе пример был бы подогнан):
    до 10 подходящих, до 5 частично подходящих, остальные — неподходящие (60% того же
    направления, 40% других). relevant = 1 только для «подходит» (оценка 2). Строки
    перемешаны: порядок не важен, ранжирует платформа.
    """
    rng = np.random.default_rng(seed)
    rows: list[list[Any]] = []
    for spec in common.SPECS:
        need = next(
            n
            for n in needs
            if n["specialization"] == spec
            and sum(1 for c in candidates if gold.get((n["id"], c["id"])) == 2) >= 10
        )
        nid = need["id"]
        rel2 = [c["id"] for c in candidates if gold.get((nid, c["id"])) == 2]
        rel1 = [c["id"] for c in candidates if gold.get((nid, c["id"])) == 1]
        same = [
            c["id"]
            for c in candidates
            if not gold.get((nid, c["id"])) and c["specialization"] == spec
        ]
        other = [c["id"] for c in candidates if c["specialization"] != spec]
        ids = _sample(rng, rel2, 10) + _sample(rng, rel1, 5)
        rest = per_need - len(ids)
        n_same = round(rest * 0.6)
        ids += _sample(rng, same, n_same) + _sample(rng, other, rest - n_same)
        for i in rng.permutation(len(ids)).tolist():
            cid = ids[i]
            rows.append([nid, cid, 1 if gold.get((nid, cid)) == 2 else 0])
    return rows


def strip(obj: Any, drop: set[str]) -> Any:
    if isinstance(obj, dict):
        return {k: strip(v, drop) for k, v in obj.items() if k not in drop}
    if isinstance(obj, list):
        return [strip(v, drop) for v in obj]
    if isinstance(obj, tuple):
        return [strip(v, drop) for v in obj]
    if isinstance(obj, float):
        return round(obj, 4)
    return obj


def main() -> None:
    parser = argparse.ArgumentParser(description="Валидация fsp-talent (E11)")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--workers", type=int, default=min(6, os.cpu_count() or 1))
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    seed = args.seed
    t0 = time.perf_counter()

    candidates = synth.make_candidates(N_CANDIDATES, seed)
    needs, attempts = synth.make_needs(N_NEEDS, candidates, seed + 1)
    gold_rows = synth.gold_rows(needs, candidates)
    _log(
        t0,
        f"синтетика: {len(candidates)} кандидатов, {len(needs)} потребностей "
        f"({attempts} попыток), эталон {len(gold_rows)} ненулевых пар",
    )

    main_res = testing_sim.run_main(candidates, seed)
    for c in candidates:
        c["stack"] = parse_stack(c["resume_skills"])
        c["test"] = main_res["categories"][c["id"]]
        c["retest"] = main_res["categories_retest"][c["id"]]
    _log(t0, "тест: онбординг и повтор")
    noise = testing_sim.run_noise(candidates, seed)
    sizes = testing_sim.run_bank_sizes(candidates, seed)
    _log(t0, "тест: ошибка калибровки и размер банка")
    leak = testing_sim.run_leak(seed, workers=args.workers)
    _log(t0, "тест: утечка")

    match = matching_sim.run_matching(candidates, needs, gold_rows, seed)
    _log(t0, "подбор: платформа, базовые линии, абляции")

    gold = {(n, c): int(r) for n, c, r in gold_rows}
    ex_rows = example_pairs(needs, candidates, gold, seed + 5)
    ds = Dataset({c["id"]: c for c in candidates}, {n["id"]: n for n in needs}, gold)
    ex_metrics = evaluate_synthetic([Pair(n, c, int(r)) for n, c, r in ex_rows], ds)

    testing = {k: v for k, v in main_res.items() if k not in ("categories", "categories_retest")}
    testing["final_se"] = [c["test"]["first_se"] for c in candidates]
    testing["noise"] = noise
    testing["bank_sizes"] = sizes
    results: dict[str, Any] = {
        "testing": testing,
        "leak": leak,
        "matching": {k: v for k, v in match.items() if k != "main_orders"},
    }
    chart_list = charts.build(results, IMG_DIR)
    msk = datetime.now(UTC) + timedelta(hours=3)
    generated = os.environ.get("VALIDATION_DATE") or msk.strftime("%Y-%m-%d")
    config = {
        "seed": seed,
        "candidates": len(candidates),
        "needs": len(needs),
        "need_attempts": attempts,
        "gold_pairs": len(gold_rows),
        "cat_config": asdict(testing_sim.stand_config()),
        "bank_items": leak["bank_items"],
    }
    metrics = strip(
        {
            "config": config,
            "testing": testing,
            "leak": leak,
            "matching": results["matching"],
            "example_pairs": ex_metrics,
        },
        {"scatter", "points", "final_se", "per_need"},
    )
    common.write_json(
        DATA_DIR / "results.json",
        {"generated_at": generated, "seed": seed, "charts": chart_list, "metrics": metrics},
    )
    write_candidates(candidates)
    common.write_json(DATA_DIR / "needs.json", needs)
    write_csv(DATA_DIR / "gold.csv", ["need_id", "candidate_id", "relevance"], gold_rows)
    write_csv(DATA_DIR / "example_pairs.csv", ["need_id", "candidate_id", "relevant"], ex_rows)
    (DOCS_DIR / "report.md").write_text(
        report.render(metrics, generated), encoding="utf-8", newline="\n"
    )
    _log(t0, "готово: data/validation/*, docs/validation/report.md, docs/validation/img/*.png")
    sy = match["systems"]
    acc = main_res["accuracy"]
    print(
        f"theta: r={acc['corr_theta']:.3f}; категория точно {main_res['category']['exact']:.1%}; "
        f"P@10 платформа {sy['system']['p10']:.3f} / слова {sy['keywords']['p10']:.3f} / "
        f"случайно {sy['random']['p10']:.3f}"
    )


if __name__ == "__main__":
    main()
