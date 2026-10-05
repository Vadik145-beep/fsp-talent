"""Валидация: графики для админки и проверка подбора по CSV для жюри [ТЗ 6.1, 6.2]."""

from pydantic import ConfigDict, Field

from app.common import fixtures
from app.common.enums import ChartType
from app.common.schemas import OutModel


class ChartPoint(OutModel):
    x: float | str
    y: float


class ChartSeries(OutModel):
    name: str
    points: list[ChartPoint]


class ValidationChart(OutModel):
    """Один график валидации (запись `validation_charts.json`)."""

    model_config = ConfigDict(json_schema_extra=fixtures.first_example("validation_charts"))

    id: str = Field(examples=["grade_accuracy"])
    title: str
    description: str
    chart_type: ChartType
    x_label: str
    y_label: str
    series: list[ChartSeries]
    summary: dict[str, float] = Field(description="Итоговые метрики графика")
    is_stub: bool = Field(description="true — заглушечные данные до волны 5 (E11)")


class ValidationOverview(OutModel):
    charts: list[ValidationChart]
    generated_at: str
    seed: int


class NeedMetrics(OutModel):
    need_id: str
    precision_at_10: float
    ndcg_at_10: float
    relevant_total: int


class MatchingEvalResult(OutModel):
    """Метрики подбора по загруженному CSV пар «вакансия — кандидат» (T11.6)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "filename": "pairs.csv",
                    "pairs_count": 1000,
                    "needs_count": 100,
                    "precision_at_10": 0.71,
                    "ndcg_at_10": 0.78,
                    "relevant_in_top_share": 0.74,
                    "baseline_precision_at_10": 0.42,
                    "baseline_ndcg_at_10": 0.47,
                    "per_need": [],
                    "is_stub": True,
                }
            ]
        }
    )

    filename: str
    pairs_count: int
    needs_count: int
    precision_at_10: float
    ndcg_at_10: float
    relevant_in_top_share: float
    baseline_precision_at_10: float
    baseline_ndcg_at_10: float
    per_need: list[NeedMetrics]
    is_stub: bool
