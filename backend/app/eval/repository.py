"""Данные валидации. До волны 5c — заглушечные графики `validation_charts.json`."""

from app.common import fixtures
from app.common.fixtures import Record


class EvalRepository:
    def charts(self) -> list[Record]:
        return fixtures.all_records("validation_charts")

    def chart(self, chart_id: str) -> Record | None:
        return fixtures.by_id("validation_charts", chart_id)
