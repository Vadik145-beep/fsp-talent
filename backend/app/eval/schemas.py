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
    is_stub: bool = Field(description="true — заглушечные данные; результаты make validate — false")


class ValidationOverview(OutModel):
    charts: list[ValidationChart]
    generated_at: str = Field(description="Дата прогона scripts/validation/run_all.py")
    seed: int


class NeedMetrics(OutModel):
    need_id: str
    precision_at_10: float
    ndcg_at_10: float
    relevant_total: int
    candidates_total: int = Field(0, description="Сколько кандидатов этой потребности в файле")
    baseline_precision_at_10: float = 0.0
    baseline_ndcg_at_10: float = 0.0


class MatchingEvalResult(OutModel):
    """Метрики подбора по загруженному CSV пар «потребность — кандидат» (T11.6)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "filename": "example_pairs.csv",
                    "pairs_count": 150,
                    "needs_count": 5,
                    "precision_at_10": 0.68,
                    "ndcg_at_10": 0.74,
                    "recall_at_50": 1.0,
                    "relevant_in_top_share": 0.5,
                    "baseline_precision_at_10": 0.4,
                    "baseline_ndcg_at_10": 0.42,
                    "random_precision_at_10": 0.38,
                    "random_ndcg_at_10": 0.37,
                    "per_need": [],
                    "ranking": "synthetic",
                    "note": "Синтетический набор: кандидатов каждой потребности ранжирует формула",
                    "warnings": [],
                    "is_stub": False,
                }
            ]
        }
    )

    filename: str
    pairs_count: int
    needs_count: int
    precision_at_10: float = Field(description="Доля подходящих среди первых 10 выдачи")
    ndcg_at_10: float = Field(description="nDCG@10: подходящие выше — лучше")
    recall_at_50: float = Field(0.0, description="Доля всех подходящих в первых 50")
    relevant_in_top_share: float = Field(
        description="Сколько из всех подходящих в файле попало в топ-10 (по всем потребностям)"
    )
    baseline_precision_at_10: float = Field(description="precision@10 поиска по ключевым словам")
    baseline_ndcg_at_10: float
    random_precision_at_10: float = Field(0.0, description="Ожидание при случайном порядке")
    random_ndcg_at_10: float = 0.0
    per_need: list[NeedMetrics]
    ranking: str = Field(
        "synthetic",
        description="Кто ранжировал: synthetic / platform — формула платформы на синтетическом "
        "наборе или данных стенда; file_order — порядок строк файла",
    )
    note: str = ""
    warnings: list[str] = Field(default_factory=list)
    is_stub: bool
