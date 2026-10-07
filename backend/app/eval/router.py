"""Валидация: графики для админки и проверка подбора по CSV для жюри (без авторизации)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import error_responses
from app.eval.schemas import MatchingEvalResult, ValidationChart, ValidationOverview
from app.eval.service import MAX_BYTES, EvalService

router = APIRouter(prefix="/eval", tags=["eval"])
service = EvalService()
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get(
    "/validation",
    response_model=ValidationOverview,
    summary="Все графики валидации",
    description="Результаты `python scripts/validation/run_all.py` "
    "(`data/validation/results.json`, "
    "фиксированный seed). Файла нет — пустой список графиков.",
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
    description=(
        "Колонки: `need_id`, `candidate_id`, необязательно `relevant` (0/1 или 0/1/2). "
        "Кандидатов каждой потребности ранжирует сама платформа (формула подбора), порядок "
        "строк не важен. id — из синтетического набора (`N001`, `C0001`, пример — "
        "`data/validation/example_pairs.csv`) или потребностей и кандидатов стенда; "
        "иначе оценивается порядок строк файла."
    ),
    responses=error_responses(
        (422, "invalid_csv", "Неверный формат CSV"),
        (413, "file_too_large", "Файл больше 10 МБ"),
    ),
)
async def evaluate_matching(
    file: Annotated[UploadFile, File(description="CSV в UTF-8")], session: SessionDep
) -> Any:
    content = await file.read(MAX_BYTES + 1)
    return await service.evaluate_csv(file.filename or "pairs.csv", content, session)
