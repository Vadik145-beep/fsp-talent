"""Валидация: графики из `data/validation/results.json` и проверка подбора по CSV (T11.6).

CSV пар «потребность — кандидат» (UTF-8, разделитель `,` или `;`):
- `need_id` — id потребности: синтетической (`N001`…) или созданной на платформе (число);
- `candidate_id` — id кандидата: синтетического (`C0001`…) или профиля на платформе (число);
- `relevant` — необязательно: 1 — подходит, 0 — нет (можно 0/1/2: 2 — подходит,
  1 — частично; тогда «релевантен» = 2, а nDCG учитывает обе оценки).

Порядок строк не важен: кандидатов каждой потребности **ранжирует сама платформа**
(`app.eval.ranking.system_order` — код подбора 3b), а метрики показывают, сколько
подходящих оказалось наверху. Для сравнения те же кандидаты ранжируются поиском
по ключевым словам и случайно.

Режимы (определяются по id):
1. `synthetic` — все id из синтетического набора; без `relevant` берётся эталон набора;
2. `platform` — все id есть в БД платформы; без `relevant` подходящим считается кандидат,
   чья категория совпала с категорией потребности;
3. `file_order` — id не найдены: оценивается порядок строк файла как готовая выдача
   (нужна колонка `relevant`).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.repository import CatalogDb
from app.core.errors import AppError, not_found
from app.eval import metrics as m
from app.eval.ranking import (
    BM25,
    keyword_order,
    overlap_order,
    system_order,
)
from app.eval.synthetic import Dataset, load_dataset, load_results, system_view
from app.matching.models import Need
from app.matching.repository import CandidatePool
from app.matching.scoring import weights_from

SEED = 20261011
K = 10
K_RECALL = 50
MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 200_000

NOTES = {
    "synthetic": "Синтетический набор: кандидатов каждой потребности ранжирует формула платформы "
    "(категория из теста + счёт). Без колонки relevant берётся эталон набора.",
    "platform": "Данные платформы: кандидатов каждой потребности ранжирует формула подбора "
    "с текущими весами. Без колонки relevant подходящим считается кандидат той же категории.",
    "file_order": "id не найдены ни в синтетическом наборе, ни на платформе: оценён порядок "
    "строк файла как готовая выдача. Поиск по словам здесь недоступен — базовая линия = "
    "исходный порядок.",
}


@dataclass(frozen=True)
class Pair:
    need_id: str
    candidate_id: str
    relevant: int | None


def _invalid(message: str, details: dict[str, Any] | None = None) -> AppError:
    return AppError(422, "invalid_csv", message, details or {})


def parse_pairs(content: bytes) -> list[Pair]:
    if len(content) > MAX_BYTES:
        raise AppError(413, "file_too_large", "Файл больше 10 МБ")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise _invalid("CSV должен быть в UTF-8") from exc
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        raise _invalid("В файле нет строк с данными")
    delimiter = ";" if lines[0].count(";") > lines[0].count(",") else ","
    reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter=delimiter)
    columns = {(c or "").strip().lower(): c for c in reader.fieldnames or []}
    if not {"need_id", "candidate_id"} <= set(columns):
        raise _invalid(
            "В CSV нужны колонки need_id и candidate_id (и необязательная relevant)",
            {"columns": sorted(columns)},
        )
    rel_col = columns.get("relevant")
    pairs: list[Pair] = []
    seen: set[tuple[str, str]] = set()
    for n, row in enumerate(reader, start=2):
        need = (row.get(columns["need_id"]) or "").strip()
        cand = (row.get(columns["candidate_id"]) or "").strip()
        if not need or not cand:
            raise _invalid(f"Строка {n}: пустой need_id или candidate_id", {"row": n})
        rel: int | None = None
        raw = (row.get(rel_col) or "").strip() if rel_col else ""
        if raw:
            try:
                rel = int(float(raw.replace(",", ".")))
            except ValueError as exc:
                raise _invalid(f"Строка {n}: relevant должно быть 0, 1 или 2", {"row": n}) from exc
            if rel not in (0, 1, 2):
                raise _invalid(f"Строка {n}: relevant должно быть 0, 1 или 2", {"row": n})
        if (need, cand) in seen:
            continue  # повтор пары — считаем один раз
        seen.add((need, cand))
        pairs.append(Pair(need, cand, rel))
        if len(pairs) > MAX_ROWS:
            raise AppError(413, "file_too_large", f"Больше {MAX_ROWS} пар")
    return pairs


def _group(pairs: Sequence[Pair]) -> dict[str, list[Pair]]:
    groups: dict[str, list[Pair]] = {}
    for p in pairs:
        groups.setdefault(p.need_id, []).append(p)
    return groups


def score_groups(
    rels: dict[str, dict[str, int]],
    system: dict[str, list[Hashable]],
    baseline: dict[str, list[Hashable]],
    *,
    min_rel: int,
) -> dict[str, Any]:
    """Метрики по потребностям: rels — оценки строк, system/baseline — порядок id."""
    per_need = []
    sums: dict[str, list[float]] = {k: [] for k in ("p", "n", "r", "bp", "bn", "rp", "rn")}
    rel_top = rel_all = 0
    skipped: list[str] = []
    for need_id, order in system.items():
        g = rels[need_id]
        ranked = [g[str(c)] for c in order]
        base = [g[str(c)] for c in baseline[need_id]]
        total = sum(1 for v in ranked if v >= min_rel)
        if total == 0:
            skipped.append(need_id)
            continue
        p10 = m.precision_at_k(ranked, K, min_rel)
        nd = m.ndcg_at_k(ranked, K)
        bp, bn = m.precision_at_k(base, K, min_rel), m.ndcg_at_k(base, K)
        rel_top += sum(1 for v in ranked[:K] if v >= min_rel)
        rel_all += total
        sums["p"].append(p10)
        sums["n"].append(nd)
        sums["r"].append(m.recall_at_k(ranked, K_RECALL, total, min_rel))
        sums["bp"].append(bp)
        sums["bn"].append(bn)
        sums["rp"].append(m.random_precision_at_k(ranked, K, min_rel))
        sums["rn"].append(m.random_ndcg_at_k(ranked, K, seed=SEED))
        per_need.append(
            {
                "need_id": need_id,
                "precision_at_10": round(p10, 3),
                "ndcg_at_10": round(nd, 3),
                "relevant_total": total,
                "candidates_total": len(ranked),
                "baseline_precision_at_10": round(bp, 3),
                "baseline_ndcg_at_10": round(bn, 3),
            }
        )

    def avg(key: str) -> float:
        return round(m.mean(sums[key]), 3)

    return {
        "needs_count": len(system),
        "precision_at_10": avg("p"),
        "ndcg_at_10": avg("n"),
        "recall_at_50": avg("r"),
        "relevant_in_top_share": round(rel_top / rel_all, 3) if rel_all else 0.0,
        "baseline_precision_at_10": avg("bp"),
        "baseline_ndcg_at_10": avg("bn"),
        "random_precision_at_10": avg("rp"),
        "random_ndcg_at_10": avg("rn"),
        "per_need": per_need,
        "skipped": skipped,
    }


def evaluate_synthetic(pairs: Sequence[Pair], ds: Dataset) -> dict[str, Any]:
    """Синтетический режим (используется эндпоинтом и скриптом отчёта)."""
    groups = _group(pairs)
    weights = weights_from({})
    rels: dict[str, dict[str, int]] = {}
    system: dict[str, list[Hashable]] = {}
    baseline: dict[str, list[Hashable]] = {}
    all_cands = {p.candidate_id for p in pairs}
    index = BM25({cid: ds.candidates[cid]["resume_text"] for cid in sorted(all_cands)})
    graded = any(p.relevant == 2 for p in pairs) or any(p.relevant is None for p in pairs)
    for need_id, rows in groups.items():
        need = ds.needs[need_id]
        rels[need_id] = {
            p.candidate_id: p.relevant
            if p.relevant is not None
            else ds.gold.get((need_id, p.candidate_id), 0)
            for p in rows
        }
        views = [system_view(ds.candidates[p.candidate_id]) for p in rows]
        system[need_id] = system_order(need, views, weights)
        baseline[need_id] = keyword_order(
            need.get("keyword_query", ""), index, [p.candidate_id for p in rows]
        )
    return score_groups(rels, system, baseline, min_rel=2 if graded else 1)


class EvalService:
    def overview(self) -> dict[str, Any]:
        data = load_results()
        if data is None:
            return {"charts": [], "generated_at": "", "seed": SEED}
        return {
            "charts": data.get("charts", []),
            "generated_at": data.get("generated_at", ""),
            "seed": data.get("seed", SEED),
        }

    def chart(self, chart_id: str) -> dict[str, Any]:
        for c in self.overview()["charts"]:
            if c["id"] == chart_id:
                return dict(c)
        raise not_found("chart", chart_id)

    async def evaluate_csv(
        self, filename: str, content: bytes, session: AsyncSession
    ) -> dict[str, Any]:
        pairs = parse_pairs(content)
        warnings: list[str] = []
        ds = load_dataset()
        need_ids = {p.need_id for p in pairs}
        cand_ids = {p.candidate_id for p in pairs}
        if ds.available and need_ids <= set(ds.needs) and cand_ids <= set(ds.candidates):
            mode = "synthetic"
            result = evaluate_synthetic(pairs, ds)
        elif (platform := await self._platform(pairs, session)) is not None:
            mode, result = "platform", platform
        else:
            mode = "file_order"
            result = self._file_order(pairs)
            warnings.append(
                "Не все id найдены: оценён порядок строк файла. Чтобы платформа ранжировала "
                "сама, используйте id синтетического набора или потребностей и кандидатов стенда."
            )
        if result["skipped"]:
            warnings.append(
                "Без подходящих кандидатов (в средние не входят): "
                + ", ".join(result["skipped"][:20])
            )
        return {
            "filename": filename,
            "pairs_count": len(pairs),
            **{k: v for k, v in result.items() if k != "skipped"},
            "ranking": mode,
            "note": NOTES[mode],
            "warnings": warnings,
            "is_stub": False,
        }

    @staticmethod
    def _file_order(pairs: Sequence[Pair]) -> dict[str, Any]:
        if any(p.relevant is None for p in pairs):
            raise _invalid(
                "id не найдены в синтетическом наборе и на платформе — "
                "для оценки готовой выдачи нужна колонка relevant у каждой строки"
            )
        groups = _group(pairs)
        rels = {
            n: {p.candidate_id: int(p.relevant or 0) for p in rows} for n, rows in groups.items()
        }
        order: dict[str, list[Hashable]] = {
            n: [p.candidate_id for p in rows] for n, rows in groups.items()
        }
        graded = any(p.relevant == 2 for p in pairs)
        return score_groups(rels, order, order, min_rel=2 if graded else 1)

    async def _platform(
        self, pairs: Sequence[Pair], session: AsyncSession
    ) -> dict[str, Any] | None:
        try:
            need_ids = sorted({int(p.need_id) for p in pairs})
            cand_ids = sorted({int(p.candidate_id) for p in pairs})
        except ValueError:
            return None
        rows = (await session.scalars(select(Need).where(Need.id.in_(need_ids)))).all()
        needs = {n.id: n for n in rows}
        if len(needs) != len(need_ids):
            return None
        records = await CandidatePool(session).records(cand_ids)
        if len(records) != len(cand_ids):
            return None
        weights = weights_from(await CatalogDb(session).settings())
        rels: dict[str, dict[str, int]] = {}
        system: dict[str, list[Hashable]] = {}
        baseline: dict[str, list[Hashable]] = {}
        for need_id, group in _group(pairs).items():
            n = needs[int(need_id)]
            need = {
                "specialization": n.specialization,
                "grade": n.grade,
                "skills_required": list(n.skills_required or []),
                "skills_desired": list(n.skills_desired or []),
                "salary_from": n.salary_from,
                "salary_to": n.salary_to,
                "work_format": n.work_format,
            }
            cands = [dict(records[int(p.candidate_id)]) for p in group]
            for c in cands:
                c["id"] = str(c["id"])
            rels[need_id] = {
                p.candidate_id: p.relevant
                if p.relevant is not None
                else int(records[int(p.candidate_id)].get("category") == n.category)
                for p in group
            }
            system[need_id] = system_order(need, cands, weights)
            baseline[need_id] = overlap_order(need, cands)
        graded = any(p.relevant == 2 for p in pairs)
        return score_groups(rels, system, baseline, min_rel=2 if graded else 1)
