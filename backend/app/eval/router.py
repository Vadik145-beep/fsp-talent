"""Валидация: графики для админки и проверка подбора по CSV для жюри (без авторизации)."""

from typing import Annotated, Any

from fastapi import APIRouter, File, UploadFile

from app.core.errors import error_responses
from app.eval.schemas import MatchingEvalResult, ValidationChart, ValidationOverview
from app.eval.service import EvalService

router = APIRouter(prefix="/eval", tags=["eval"])
service = EvalService()


@router.get(
    "/validation",
    response_model=ValidationOverview,
    summary="Все графики валидации",
    description="До волны 5c данные заглушечные (`is_stub: true`).",
)
async def validation_overview() -> Any:
    return service.overview()


@router.get(
    "/charts/{chart_id}",
    response_model=ValidationChart,
    summary="Один график валидации",
    responses=error_responses(404),
)
async def get_chart(chart_id: str) -> Any:
    return service.chart(chart_id)


@router.post(
    "/matching",
    response_model=MatchingEvalResult,
    summary="Загрузить CSV пар «потребность — кандидат» → метрики подбора",
    description="Колонки: `need_id`, `candidate_id`, необязательно `relevant` (0/1).",
    responses=error_responses(
        (422, "invalid_csv", "Неверный формат CSV"),
        (413, "file_too_large", "Файл больше 10 МБ"),
    ),
)
async def evaluate_matching(file: Annotated[UploadFile, File(description="CSV в UTF-8")]) -> Any:
    content = await file.read()
    return service.evaluate_csv(file.filename or "pairs.csv", content)
