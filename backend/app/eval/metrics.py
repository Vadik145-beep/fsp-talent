"""Метрики качества подбора и согласованности (T11.3, T11.5). Чистые функции без БД.

Все метрики ранжирования принимают **оценки релевантности в порядке выдачи**:
`ranked = [2, 0, 1, ...]` — первая строка выдачи «точно подходит», вторая — нет и т.д.
Шкала: 0 — не подходит, 1 — подходит частично, 2 — подходит. Бинарный ответ «релевантен»
по умолчанию — оценка ≥ `min_rel` (для CSV с колонкой 0/1 — просто 1).

- precision@k — доля релевантных среди первых k строк выдачи. Если в списке меньше k строк,
  делим на длину списка (иначе короткие списки из CSV жюри штрафуются ни за что);
- recall@k — доля всех релевантных, попавших в первые k;
- nDCG@k — DCG первых k / DCG идеального порядка; выигрыш строки 2^rel − 1
  (оценка 2 весит втрое больше оценки 1), дисконт log2(позиция + 1).
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence

import numpy as np


def _binary(ranked: Sequence[float], min_rel: float) -> list[int]:
    return [1 if r >= min_rel else 0 for r in ranked]


def precision_at_k(ranked: Sequence[float], k: int, min_rel: float = 1) -> float:
    top = _binary(ranked[:k], min_rel)
    return sum(top) / len(top) if top else 0.0


def recall_at_k(
    ranked: Sequence[float], k: int, total_relevant: int | None = None, min_rel: float = 1
) -> float:
    """total_relevant — сколько релевантных всего (по умолчанию — в самом списке)."""
    total = sum(_binary(ranked, min_rel)) if total_relevant is None else total_relevant
    if total <= 0:
        return 0.0
    return sum(_binary(ranked[:k], min_rel)) / total


def dcg(gains: Sequence[float]) -> float:
    return float(sum((2.0**g - 1.0) / math.log2(i + 2) for i, g in enumerate(gains)))


def ndcg_at_k(ranked: Sequence[float], k: int, ideal: Sequence[float] | None = None) -> float:
    """ideal — все оценки, из которых строится идеальный порядок (по умолчанию — сам список).

    Если в выдачу попала не вся база, в `ideal` передают оценки всех кандидатов:
    тогда пропущенные релевантные снижают nDCG.
    """
    pool = list(ranked if ideal is None else ideal)
    best = dcg(sorted(pool, reverse=True)[:k])
    return dcg(list(ranked[:k])) / best if best > 0 else 0.0


def mean(values: Sequence[float]) -> float:
    return float(np.mean(values)) if len(values) else 0.0


def bootstrap_ci(
    values: Sequence[float],
    *,
    stat: Callable[[Sequence[float]], float] = mean,
    n_boot: int = 1000,
    seed: int = 0,
    level: float = 0.95,
) -> tuple[float, float]:
    """Перцентильный бутстреп-интервал среднего по потребностям (фиксированный seed)."""
    if not values:
        return 0.0, 0.0
    rng = np.random.default_rng(seed)
    arr = np.asarray(values, dtype=float)
    idx = rng.integers(0, len(arr), size=(n_boot, len(arr)))
    stats = np.array([stat(arr[row].tolist()) for row in idx])
    lo, hi = np.percentile(stats, [(1 - level) / 2 * 100, (1 + level) / 2 * 100])
    return float(lo), float(hi)


def overlap_at_k(a: Sequence[object], b: Sequence[object], k: int) -> float:
    """Доля общих элементов в первых k двух выдач (порядок внутри топа не важен)."""
    top_a, top_b = set(a[:k]), set(b[:k])
    size = min(k, len(a), len(b))
    return len(top_a & top_b) / size if size else 0.0


def random_precision_at_k(ranked: Sequence[float], k: int, min_rel: float = 1) -> float:
    """Ожидаемая precision@k случайного порядка тех же строк: доля релевантных в списке."""
    rel = _binary(ranked, min_rel)
    return sum(rel) / len(rel) if rel else 0.0


def random_ndcg_at_k(
    ranked: Sequence[float],
    k: int,
    ideal: Sequence[float] | None = None,
    *,
    n_shuffles: int = 200,
    seed: int = 0,
) -> float:
    """Ожидаемый nDCG@k случайного порядка (Монте-Карло, фиксированный seed)."""
    rows = list(ranked)
    if not rows:
        return 0.0
    rnd = random.Random(seed)
    total = 0.0
    for _ in range(n_shuffles):
        rnd.shuffle(rows)
        total += ndcg_at_k(rows, k, ideal if ideal is not None else ranked)
    return total / n_shuffles


def pearson(x: Sequence[float], y: Sequence[float]) -> float:
    xa, ya = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if xa.size < 2 or xa.std() == 0 or ya.std() == 0:
        return 0.0
    return float(np.corrcoef(xa, ya)[0, 1])


def cohens_kappa(a: Sequence[str], b: Sequence[str]) -> float:
    """Каппа Коэна: согласие двух разметок с поправкой на случайное совпадение."""
    if len(a) != len(b):
        raise ValueError("Разметки разной длины")
    n = len(a)
    if n == 0:
        return 0.0
    cats = sorted(set(a) | set(b))
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    pe = sum((list(a).count(c) / n) * (list(b).count(c) / n) for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0
