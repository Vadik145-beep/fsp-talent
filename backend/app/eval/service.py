"""Валидация: графики и метрики подбора по CSV. Настоящие расчёты — волна 5c (E11)."""

import csv
import io
from typing import Any

from app.core.errors import AppError, not_found
from app.eval.repository import EvalRepository

SEED = 20261011
REQUIRED_COLUMNS = {"need_id", "candidate_id"}


class EvalService:
    def __init__(self, repo: EvalRepository | None = None) -> None:
        self.repo = repo or EvalRepository()

    def overview(self) -> dict[str, Any]:
        return {
            "charts": self.repo.charts(),
            "generated_at": "2026-10-06T12:00:00+03:00",
            "seed": SEED,
        }

    def chart(self, chart_id: str) -> dict[str, Any]:
        chart = self.repo.chart(chart_id)
        if chart is None:
            raise not_found("chart", chart_id)
        return dict(chart)

    def evaluate_csv(self, filename: str, content: bytes) -> dict[str, Any]:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise AppError(422, "invalid_csv", "CSV должен быть в UTF-8") from exc
        reader = csv.DictReader(io.StringIO(text))
        columns = set(reader.fieldnames or [])
        if not columns >= REQUIRED_COLUMNS:
            raise AppError(
                422,
                "invalid_csv",
                "В CSV нужны колонки need_id и candidate_id (и необязательная relevant)",
                {"columns": sorted(columns)},
            )
        rows = list(reader)
        needs = sorted({r["need_id"] for r in rows})
        summary = (self.repo.chart("precision_at_10") or {}).get("summary", {})
        return {
            "filename": filename,
            "pairs_count": len(rows),
            "needs_count": len(needs),
            "precision_at_10": summary.get("precision_at_10", 0.0),
            "ndcg_at_10": summary.get("ndcg_at_10", 0.0),
            "relevant_in_top_share": summary.get("precision_at_10", 0.0),
            "baseline_precision_at_10": summary.get("baseline_precision_at_10", 0.0),
            "baseline_ndcg_at_10": summary.get("baseline_ndcg_at_10", 0.0),
            "per_need": [],
            "is_stub": True,
        }
