"""Опрос специализации, адаптивный тест, результат, категория и грейд (соискатель)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates.grade_schemas import CandidateGradeStatus
from app.core.db import get_session
from app.core.errors import AppError, error_responses
from app.core.security import CandidateUser, CurrentUser
from app.testing.schemas import (
    AnswerAck,
    AnswerSubmit,
    SurveyQuestion,
    SurveyResult,
    SurveySubmit,
    TestResult,
    TestSession,
    TestSessionCreate,
    TestSessionState,
)
from app.testing.service import TestingDbService

router = APIRouter(prefix="/testing", tags=["testing"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]

AUTH = (401, 403)


def _cid(user: CurrentUser) -> int:
    if user.candidate_id is None:
        raise AppError(404, "not_found", "Профиль кандидата не найден")
    return user.candidate_id


@router.get(
    "/survey",
    response_model=list[SurveyQuestion],
    summary="Вопросы опроса по специализации",
    responses=error_responses(*AUTH),
)
async def get_survey(user: CandidateUser, session: SessionDep) -> Any:
    return TestingDbService(session).survey()


@router.post(
    "/survey",
    response_model=SurveyResult,
    summary="Отправить опрос → рекомендованная специализация и темы",
    responses=error_responses(*AUTH, 422),
)
async def submit_survey(body: SurveySubmit, user: CandidateUser, session: SessionDep) -> Any:
    return await TestingDbService(session).submit_survey(body, _cid(user))


@router.get(
    "/grade",
    response_model=CandidateGradeStatus,
    summary="Категория и грейд: статус, кулдауны, история",
    description="То же, что `GET /api/candidates/me/grade`: правила частоты считает движок.",
    responses=error_responses(*AUTH, 404),
)
async def grade_status(user: CandidateUser, session: SessionDep) -> Any:
    return await TestingDbService(session).grade_status(_cid(user))


@router.get(
    "/sessions",
    response_model=list[TestSession],
    summary="Мои тесты",
    responses=error_responses(*AUTH),
)
async def list_sessions(user: CandidateUser, session: SessionDep) -> Any:
    return await TestingDbService(session).sessions(_cid(user))


@router.post(
    "/sessions",
    response_model=TestSessionState,
    status_code=status.HTTP_201_CREATED,
    summary="Начать тест",
    description=(
        "Проверка частоты попыток — движок (`can_attempt`): смена грейда не чаще раза в 90 дней, "
        "повтор неудачной попытки на тот же грейд — через 30 дней (409 `cooldown_active`, "
        "в details — `reason_code` и `available_at`). Брошенная сессия считается неудачной "
        "попыткой. Одновременно — одна незавершённая сессия."
    ),
    responses=error_responses(
        *AUTH,
        (409, "cooldown_active", "Сменить грейд можно не чаще раза в 90 дней"),
        (409, "session_in_progress", "Сначала завершите начатый тест"),
        (409, "bank_empty", "Для специализации пока нет задач"),
        (422, "invalid_kind", "Вид теста не соответствует текущему грейду"),
        422,
    ),
)
async def start_session(body: TestSessionCreate, user: CandidateUser, session: SessionDep) -> Any:
    return await TestingDbService(session).create(body, _cid(user))


@router.get(
    "/sessions/{session_id}",
    response_model=TestSessionState,
    summary="Экран теста: текущая задача, прогресс, таймер",
    responses=error_responses(*AUTH, 404),
)
async def get_test_session(session_id: int, user: CandidateUser, session: SessionDep) -> Any:
    return await TestingDbService(session).get_state(session_id, _cid(user))


@router.post(
    "/sessions/{session_id}/answers",
    response_model=AnswerAck,
    summary="Ответить на текущую задачу",
    description=(
        "Верно/неверно не сообщается. Время считает сервер от выдачи задачи; ответ после "
        "лимита принимается, но засчитывается неверным (`time_expired: true`)."
    ),
    responses=error_responses(
        *AUTH,
        404,
        (409, "session_finished", "Тест уже завершён"),
        (409, "wrong_item", "Ответ не на текущую задачу"),
        422,
    ),
)
async def submit_answer(
    session_id: int, body: AnswerSubmit, user: CandidateUser, session: SessionDep
) -> Any:
    return await TestingDbService(session).answer(session_id, _cid(user), body)


@router.get(
    "/sessions/{session_id}/result",
    response_model=TestResult,
    summary="Результат теста: категория, θ и интервал, разбор по темам",
    responses=error_responses(*AUTH, 404, (409, "session_not_finished", "Тест ещё не завершён")),
)
async def get_result(session_id: int, user: CandidateUser, session: SessionDep) -> Any:
    return await TestingDbService(session).result(session_id, _cid(user))
