"""Выдача для оценки качества подбора: настоящая формула 3b и базовая линия «ключевые слова».

`system_order` повторяет то, что видит рекрутер, и вызывает код подбора, а не копию формулы:
1. ярус 0 — кандидаты основной категории потребности (категория — по результату теста);
2. ярус 1 — рекомендованные соседние категории (`NeedService.recommended_categories`:
   грейд ±1 и смежная специализация того же грейда);
3. ярус 2 — остальные кандидаты с категорией, ярус 3 — без категории (тест не пройден);
внутри яруса — по счёту `app.matching.scoring.score_candidate` с весами платформы.
Так метрики «в топе выдачи» считаются по тому порядку, в котором рекрутер видит кандидатов,
а recall@50 учитывает переход в соседние категории, если основной не хватило.

`keyword_order` — базовая линия «поиск по ключевым словам резюме»: BM25 по тексту резюме
(как у обычной джоб-площадки), запрос — грейд, специализация и стек из потребности.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Callable, Hashable, Iterable, Mapping, Sequence
from typing import Any

from app.matching.scoring import NeedLike, score_candidate, weights_from
from app.matching.service import ADJACENT, GRADES

TIER_PRIMARY, TIER_RECOMMENDED, TIER_OTHER, TIER_NO_CATEGORY = 0, 1, 2, 3

_TOKEN = re.compile(r"[0-9a-zа-яё#+]+(?:\.[0-9a-zа-яё]+)*")


def recommended_categories(specialization: str, grade: str) -> list[str]:
    """Соседние категории, как в `NeedService.recommended_categories` (без основной)."""
    gi = GRADES.index(grade)
    out: list[str] = []
    if gi > 0:
        out.append(f"{specialization}:{GRADES[gi - 1]}")
    if gi < len(GRADES) - 1:
        out.append(f"{specialization}:{GRADES[gi + 1]}")
    out += [f"{adj}:{grade}" for adj in ADJACENT.get(specialization, [])]
    return out


def tier(need: dict[str, Any], category: str | None) -> int:
    if not category:
        return TIER_NO_CATEGORY
    if category == f"{need['specialization']}:{need['grade']}":
        return TIER_PRIMARY
    if category in recommended_categories(need["specialization"], need["grade"]):
        return TIER_RECOMMENDED
    return TIER_OTHER


def need_like(need: dict[str, Any]) -> NeedLike:
    return NeedLike(
        skills_required=list(need["skills_required"]),
        skills_desired=list(need["skills_desired"]),
        salary_from=int(need["salary_from"]),
        salary_to=int(need["salary_to"]),
        work_format=str(need["work_format"]),
        specialization=need.get("specialization"),
    )


def _plain_label(code: str) -> str:
    return code


def system_scores(
    need: dict[str, Any],
    candidates: Iterable[dict[str, Any]],
    weights: dict[str, float] | None = None,
    *,
    label: Callable[[str], str] = _plain_label,
) -> dict[Hashable, float]:
    """Счёт `score_candidate` (0..1) каждого кандидата для потребности."""
    w = weights if weights is not None else weights_from({})
    target = need_like(need)
    return {
        c["id"]: float(
            score_candidate(c, target, w, label, fsp_reason=c.get("fsp_reason"))["score"]
        )
        for c in candidates
    }


def system_order(
    need: dict[str, Any],
    candidates: Sequence[dict[str, Any]],
    weights: dict[str, float] | None = None,
    *,
    use_category: bool = True,
    category_key: str = "category",
    top_n: int | None = None,
) -> list[Hashable]:
    """id кандидатов в порядке выдачи платформы (ярус категории, затем счёт, затем id).

    use_category=False — ранжирование только по счёту, без категорий (для абляции).
    top_n — ускорение для больших баз: счёт считается только для целых ярусов, которые
    нужны, чтобы заполнить первые top_n мест; дальше порядок — по ярусу и id. Метрики
    с k ≤ top_n от этого не меняются.
    """
    tiers = {c["id"]: (tier(need, c.get(category_key)) if use_category else 0) for c in candidates}
    pool = list(candidates)
    rest: list[dict[str, Any]] = []
    if top_n is not None and use_category:
        pool, rest, filled = [], [], 0
        for t in sorted(set(tiers.values())):
            group = [c for c in candidates if tiers[c["id"]] == t]
            if filled < top_n:
                pool.extend(group)
                filled += len(group)
            else:
                rest.extend(group)
    scores = system_scores(need, pool, weights)

    def key(c: dict[str, Any]) -> tuple[int, float, str]:
        return tiers[c["id"]], -scores.get(c["id"], 0.0), str(c["id"]).zfill(12)

    return [c["id"] for c in sorted(pool, key=key) + sorted(rest, key=key)]


# --------------------------------------------------------------------------- базовая линия


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower().replace("ё", "е"))


class BM25:
    """Okapi BM25 по коллекции документов (k1 = 1,5, b = 0,75)."""

    def __init__(self, docs: Mapping[Any, str], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.tf = {doc_id: Counter(tokens(text)) for doc_id, text in docs.items()}
        self.len = {doc_id: sum(c.values()) for doc_id, c in self.tf.items()}
        n = len(docs)
        self.avg_len = (sum(self.len.values()) / n) if n else 0.0
        df: Counter[str] = Counter()
        for c in self.tf.values():
            df.update(c.keys())
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def score(self, query: str, doc_id: Hashable) -> float:
        tf, length = self.tf[doc_id], self.len[doc_id]
        norm = self.k1 * (1 - self.b + self.b * length / self.avg_len) if self.avg_len else 0.0
        total = 0.0
        for t in set(tokens(query)):
            f = tf.get(t, 0)
            if f:
                total += self.idf.get(t, 0.0) * f * (self.k1 + 1) / (f + norm)
        return total


def keyword_order(query: str, index: BM25, ids: Sequence[Hashable]) -> list[Hashable]:
    """id в порядке убывания BM25 (ничьи — по id)."""
    scored = [(index.score(query, i), str(i).zfill(12), i) for i in ids]
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [i for _, _, i in scored]


def overlap_order(need: dict[str, Any], candidates: Sequence[dict[str, Any]]) -> list[Hashable]:
    """Ключевые слова для данных платформы (текста резюме нет): число совпавших технологий
    стека потребности и кандидата, ничьи — по порядку строк."""
    want = set(need["skills_required"]) | set(need["skills_desired"])
    indexed = list(enumerate(candidates))
    indexed.sort(key=lambda x: (-len(want & set(x[1].get("stack") or [])), x[0]))
    return [c["id"] for _, c in indexed]
