"""Админка: тесты, собранные из текста вакансии (T4.8).

Отдельный файл, чтобы разбор вакансий (волна 3c) развивался независимо от остальной админки.
"""

from typing import Any

from fastapi import APIRouter

from app.admin.router import AUTH, service
from app.admin.schemas import VacancyTestRequest, VacancyTestResult
from app.core.errors import error_responses
from app.core.security import AdminUser

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/vacancy-tests",
    response_model=list[VacancyTestResult],
    summary="Примеры: тесты, собранные из вакансий",
    responses=error_responses(*AUTH),
)
async def list_vacancy_tests(user: AdminUser) -> Any:
    return service.vacancy_tests()


@router.post(
    "/vacancy-tests",
    response_model=VacancyTestResult,
    summary="Текст вакансии → темы → тест с объяснением",
    description="Заглушка: возвращает ближайший пример. Настоящий разбор — волна 3c (T4.8).",
    responses=error_responses(
        *AUTH, 422, (503, "llm_unavailable", "LLM недоступна, работаем по словарю")
    ),
)
async def build_vacancy_test(body: VacancyTestRequest, user: AdminUser) -> Any:
    return service.build_vacancy_test(body)
