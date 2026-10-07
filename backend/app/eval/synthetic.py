"""Синтетический набор валидации (`data/validation/`): чтение и вид «глазами платформы».

Набор генерирует `scripts/validation/run_all.py`. Здесь — только чтение, чтобы эндпоинт
проверки CSV ранжировал синтетических кандидатов той же функцией, что и отчёт.
"""

from __future__ import annotations

import csv
import json
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import REPO_ROOT
from app.nlp.skills_lexicon import catalog, normalize_skill

RESULTS_FILE = "results.json"
CANDIDATES_FILE = "candidates.json"
NEEDS_FILE = "needs.json"
GOLD_FILE = "gold.csv"


def data_dir() -> Path:
    """Каталог набора; в Docker задаётся `VALIDATION_DIR` (по умолчанию data/validation)."""
    return Path(os.environ.get("VALIDATION_DIR") or REPO_ROOT / "data" / "validation")


def parse_stack(resume_skills: Sequence[str]) -> list[str]:
    """Стек резюме → коды справочника (как при разборе резюме). Неизвестное отбрасывается."""
    out: list[str] = []
    for s in resume_skills:
        code = normalize_skill(s)
        if code and code in catalog() and code not in out:
            out.append(code)
    return out


def system_view(
    c: dict[str, Any], *, use_test: bool = True, test_key: str = "test"
) -> dict[str, Any]:
    """Синтетический кандидат так, как его видит подбор (без скрытой правды)."""
    test = c.get(test_key) or {}
    category = test.get("category") if use_test else f"{c['specialization']}:{c['declared_grade']}"
    return {
        "id": c["id"],
        "stack": list(c["stack"]),
        "theta": test.get("theta") if use_test else None,
        "topic_scores": [],
        "fsp_id": c.get("fsp_id"),
        "fsp_score": c.get("fsp_score"),
        "fsp_badges": [],
        "privacy": {},
        "freshness": c.get("freshness") or 0.0,
        "min_salary": c.get("min_salary"),
        "work_formats": list(c.get("work_formats") or []),
        "category_label": None,
        "category": category,
    }


@dataclass
class Dataset:
    candidates: dict[str, dict[str, Any]] = field(default_factory=dict)
    needs: dict[str, dict[str, Any]] = field(default_factory=dict)
    gold: dict[tuple[str, str], int] = field(default_factory=dict)

    @property
    def available(self) -> bool:
        return bool(self.candidates and self.needs)


@lru_cache(maxsize=4)
def _load(path: str, stamp: float) -> Dataset:
    base = Path(path)
    ds = Dataset()
    try:
        cands = json.loads((base / CANDIDATES_FILE).read_text(encoding="utf-8"))
        needs = json.loads((base / NEEDS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ds
    ds.candidates = {c["id"]: c for c in cands}
    ds.needs = {n["id"]: n for n in needs}
    gold_path = base / GOLD_FILE
    if gold_path.exists():
        with gold_path.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                ds.gold[(row["need_id"], row["candidate_id"])] = int(row["relevance"])
    return ds


def load_dataset(base: Path | None = None) -> Dataset:
    """Набор с кэшем (перечитывается, если файл кандидатов изменился)."""
    path = base or data_dir()
    try:
        stamp = (path / CANDIDATES_FILE).stat().st_mtime
    except OSError:
        return Dataset()
    return _load(str(path), stamp)


def load_results(base: Path | None = None) -> dict[str, Any] | None:
    path = (base or data_dir()) / RESULTS_FILE
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data
