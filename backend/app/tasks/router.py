"""Регулярные короткие задания: раздел «Задания» кандидата и рекрутера."""

from typing import Any

from fastapi import APIRouter, status

from app.core.errors import AppError, error_responses
from app.core.security import CandidateUser, CurrentUser, RecruiterUser
from app.tasks.schemas import (
    RegularTask,
    RegularTaskCreate,
    SubmissionAnswer,
    SubmissionGrade,
    TaskInbox,
    TaskSubmission,
    TaskSubmissionForRecruiter,
)
from app.tasks.service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])
service = TaskService()

AUTH = (401, 403)
TRANSITION = (409, "invalid_transition", "Действие недоступно в текущем статусе")


def _cid(user: CurrentUser) -> int:
    if user.candidate_id is None:
        raise AppError(404, "not_found", "Профиль кандидата не найден")
    return user.candidate_id


def _company(user: CurrentUser) -> int:
    if user.company_id is None:
        raise AppError(404, "not_found", "Компания не найдена")
    return user.company_id


@router.get(
    "/inbox",
    response_model=TaskInbox,
    summary="Мои задания: активное и история (кандидат)",
    responses=error_responses(*AUTH, 404),
)
async def task_inbox(user: CandidateUser) -> Any:
    return service.inbox(_cid(user))


@router.post(
    "/submissions/{submission_id}/answer",
    response_model=TaskSubmission,
    summary="Ответить на задание (кандидат)",
    responses=error_responses(*AUTH, 404, TRANSITION, 422),
)
async def answer_task(submission_id: int, body: SubmissionAnswer, user: CandidateUser) -> Any:
    return service.answer(submission_id, _cid(user), body)


@router.get(
    "",
    response_model=list[RegularTask],
    summary="Задания моей компании (рекрутер)",
    responses=error_responses(*AUTH),
)
async def list_tasks(user: RecruiterUser) -> Any:
    return service.list_tasks(_company(user))


@router.post(
    "",
    response_model=RegularTask,
    status_code=status.HTTP_201_CREATED,
    summary="Создать короткое задание (рекрутер)",
    responses=error_responses(*AUTH, (422, "unknown_category", "Неизвестная категория")),
)
async def create_task(body: RegularTaskCreate, user: RecruiterUser) -> Any:
    assert user.recruiter_id is not None
    return service.create_task(body, _company(user), user.recruiter_id)


@router.get(
    "/{task_id}/submissions",
    response_model=list[TaskSubmissionForRecruiter],
    summary="Ответы кандидатов на задание (обезличенно)",
    responses=error_responses(*AUTH, 404),
)
async def task_submissions(task_id: int, user: RecruiterUser) -> Any:
    return service.task_submissions(task_id, _company(user))


@router.post(
    "/submissions/{submission_id}/grade",
    response_model=TaskSubmissionForRecruiter,
    summary="Оценить ответ 0–3 (рекрутер)",
    responses=error_responses(*AUTH, 404, TRANSITION, 422),
)
async def grade_submission(submission_id: int, body: SubmissionGrade, user: RecruiterUser) -> Any:
    return service.grade(submission_id, _company(user), body)
