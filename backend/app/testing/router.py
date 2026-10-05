"""Опрос специализации, адаптивный тест, результат, категория и грейд (соискатель)."""

from typing import Any

from fastapi import APIRouter, status

from app.core.errors import AppError, error_responses
from app.core.security import CandidateUser, CurrentUser
from app.testing.schemas import (
    AnswerAck,
    AnswerSubmit,
    GradeStatus,
    SurveyQuestion,
    SurveyResult,
    SurveySubmit,
    TestResult,
    TestSession,
    TestSessionCreate,
    TestSessionState,
)
from app.testing.service import TestingService

router = APIRouter(prefix="/testing", tags=["testing"])
service = TestingService()

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
async def get_survey(user: CandidateUser) -> Any:
    return service.survey()


@router.post(
    "/survey",
    response_model=SurveyResult,
    summary="Отправить опрос → рекомендованная специализация и темы",
    responses=error_responses(*AUTH, 422),
)
async def submit_survey(body: SurveySubmit, user: CandidateUser) -> Any:
    return service.submit_survey(body)


@router.get(
    "/grade",
    response_model=GradeStatus,
    summary="Категория и грейд: статус, кулдауны, история",
    responses=error_responses(*AUTH, 404),
)
async def grade_status(user: CandidateUser) -> Any:
    return service.grade_status(_cid(user))


@router.get(
    "/sessions",
    response_model=list[TestSession],
    summary="Мои тесты",
    responses=error_responses(*AUTH),
)
async def list_sessions(user: CandidateUser) -> Any:
    return service.sessions(_cid(user))


@router.post(
    "/sessions",
    response_model=TestSessionState,
    status_code=status.HTTP_201_CREATED,
    summary="Начать тест",
    description="Пересдача на грейд ниже/выше — не чаще раза в 90 дней (409 `cooldown_active`).",
    responses=error_responses(
        *AUTH,
        (409, "cooldown_active", "Сменить грейд можно не чаще раза в 90 дней"),
        (409, "session_in_progress", "Сначала завершите начатый тест"),
        422,
    ),
)
async def start_session(body: TestSessionCreate, user: CandidateUser) -> Any:
    return service.create(body, _cid(user))


@router.get(
    "/sessions/{session_id}",
    response_model=TestSessionState,
    summary="Экран теста: текущая задача, прогресс, таймер",
    responses=error_responses(*AUTH, 404),
)
async def get_session(session_id: int, user: CandidateUser) -> Any:
    return service.get_state(session_id, _cid(user))


@router.post(
    "/sessions/{session_id}/answers",
    response_model=AnswerAck,
    summary="Ответить на текущую задачу",
    description="Верно/неверно не сообщается. Время считает сервер.",
    responses=error_responses(
        *AUTH,
        404,
        (409, "session_finished", "Тест уже завершён"),
        (409, "wrong_item", "Ответ не на текущую задачу"),
        422,
    ),
)
async def submit_answer(session_id: int, body: AnswerSubmit, user: CandidateUser) -> Any:
    return service.answer(session_id, _cid(user), body)


@router.get(
    "/sessions/{session_id}/result",
    response_model=TestResult,
    summary="Результат теста: категория, θ и интервал, разбор по темам",
    responses=error_responses(*AUTH, 404, (409, "session_not_finished", "Тест ещё не завершён")),
)
async def get_result(session_id: int, user: CandidateUser) -> Any:
    return service.result(session_id, _cid(user))
