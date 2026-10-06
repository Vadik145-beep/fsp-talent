"""Админка: тесты, собранные из текста вакансии (T4.8).

Отдельный файл, чтобы разбор вакансий (волна 3c) развивался независимо от остальной админки.
Логика — `app.nlp.vacancy_tests`.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.router import AUTH, service
from app.admin.schemas import VacancyTestRequest
from app.core.db import get_session
from app.core.errors import error_responses
from app.core.security import AdminUser
from app.nlp.schemas import VacancyTestOut
from app.nlp.vacancy_tests import VacancyTestService

router = APIRouter(prefix="/admin", tags=["admin"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get(
    "/vacancy-tests",
    response_model=list[VacancyTestOut],
    summary="Тесты, собранные из вакансий",
    description="Новые сверху. Пока ни одного не собрано — показываются демо-примеры.",
    responses=error_responses(*AUTH),
)
async def list_vacancy_tests(user: AdminUser, session: SessionDep) -> Any:
    built = await VacancyTestService(session).list()
    return built or service.vacancy_tests()


@router.post(
    "/vacancy-tests",
    response_model=VacancyTestOut,
    summary="Текст вакансии → темы → тест с объяснением",
    description=(
        "Специализация и грейд — правилами; темы — по словарю с уверенностью; по каждой теме "
        "шаблон банка, ближайший по грейду, с объяснением выбора. Для тем без шаблонов создаётся "
        "черновик в банке задач (status=draft, `drafts[].item_id`): LLM при наличии ключа, иначе "
        "заготовка словаря тем. Без ключа LLM всё работает (`parser: rules`)."
    ),
    responses=error_responses(*AUTH, 422),
)
async def build_vacancy_test(body: VacancyTestRequest, user: AdminUser, session: SessionDep) -> Any:
    return await VacancyTestService(session).build(body.text, body.specialization)
