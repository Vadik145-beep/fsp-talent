"""Регулярные короткие задания: раздел «Задания» кандидата и рекрутера (БД, E9)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import AppError, error_responses
from app.core.security import AdminUser, CandidateUser, CurrentUser, RecruiterUser
from app.tasks.jobs import JobName, run_job
from app.tasks.schemas import (
    DistributionResult,
    RegularTask,
    RegularTaskCreate,
    SubmissionAnswer,
    SubmissionGrade,
    TaskInbox,
    TaskJobResult,
    TaskSubmission,
    TaskSubmissionForRecruiter,
)
from app.tasks.service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
AUTH = (401, 403)
TRANSITION = (409, "invalid_transition", "Действие недоступно в текущем статусе")
BLOCKED = (403, "company_blocked", "Компания заблокирована администратором платформы")


def _cid(user: CurrentUser) -> int:
    if user.candidate_id is None:
        raise AppError(404, "not_found", "Профиль кандидата не найден")
    return user.candidate_id


def _company(user: CurrentUser) -> int:
    if user.company_id is None or user.recruiter_id is None:
        raise AppError(404, "not_found", "Компания не найдена")
    return user.company_id


@router.get(
    "/inbox",
    response_model=TaskInbox,
    summary="Мои задания: задачи недели на выбор и история (кандидат)",
    description=(
        "До трёх задач от разных компаний; кандидат выбирает одну и отвечает. Задачи с "
        "прошедшим сроком без ответа при открытии становятся «истекло»."
    ),
    responses=error_responses(*AUTH, 404),
)
async def task_inbox(user: CandidateUser, session: SessionDep) -> Any:
    return await TaskService(session).inbox(_cid(user))


@router.post(
    "/submissions/{submission_id}/answer",
    response_model=TaskSubmission,
    summary="Ответить на задание (кандидат)",
    description=(
        "Ответ — текст, код или подход. Свежесть профиля растёт сразу после ответа; остальные "
        "задачи недели снимаются (статус `skipped`), новые придут в понедельник."
    ),
    responses=error_responses(
        *AUTH, 404, TRANSITION, (409, "submission_expired", "Срок ответа истёк"), 422
    ),
)
async def answer_task(
    submission_id: int, body: SubmissionAnswer, user: CandidateUser, session: SessionDep
) -> Any:
    return await TaskService(session).answer(submission_id, _cid(user), body)


@router.get(
    "",
    response_model=list[RegularTask],
    summary="Задания моей компании (рекрутер)",
    responses=error_responses(*AUTH),
)
async def list_tasks(user: RecruiterUser, session: SessionDep) -> Any:
    return await TaskService(session).list_tasks(_company(user))


@router.post(
    "",
    response_model=RegularTask,
    status_code=status.HTTP_201_CREATED,
    summary="Создать короткое задание (рекрутер)",
    description=(
        "Задание сразу попадает в задачи недели кандидатов категории, у кого меньше трёх задач "
        "и нет ответа на этой неделе; дальше — планировщиком по понедельникам. "
        "`submissions_count` — скольким предложено (без тех, кто выбрал другую задачу)."
    ),
    responses=error_responses(
        *AUTH, BLOCKED, 422, (422, "unknown_category", "Неизвестная категория")
    ),
)
async def create_task(body: RegularTaskCreate, user: RecruiterUser, session: SessionDep) -> Any:
    _company(user)
    return await TaskService(session).create_task(body, user)


@router.post(
    "/jobs/run",
    response_model=TaskJobResult,
    summary="Запустить периодическую работу заданий (админ)",
    description=(
        "То же, что `python -m app.tasks <job>` для планировщика: `distribute` — раздать "
        "задания, `daily` — просрочить задания без ответа и снизить свежесть профилей, "
        "`tick` — всё сразу."
    ),
    responses=error_responses(*AUTH, 422),
)
async def run_tasks_job(
    user: AdminUser,
    session: SessionDep,
    job: Annotated[JobName, Query(description="distribute | daily | tick")] = "tick",
) -> Any:
    return await run_job(session, job)


@router.get(
    "/{task_id}/submissions",
    response_model=list[TaskSubmissionForRecruiter],
    summary="Ответы кандидатов на задание (обезличенно)",
    responses=error_responses(*AUTH, 404),
)
async def task_submissions(task_id: int, user: RecruiterUser, session: SessionDep) -> Any:
    return await TaskService(session).task_submissions(task_id, _company(user))


@router.post(
    "/{task_id}/distribute",
    response_model=DistributionResult,
    summary="Раздать задание ещё раз (рекрутер)",
    description=(
        "Дополняет задачи недели кандидатов категории; `assigned` — скольким предложено "
        "именно это задание."
    ),
    responses=error_responses(*AUTH, BLOCKED, 404, TRANSITION),
)
async def distribute_task(task_id: int, user: RecruiterUser, session: SessionDep) -> Any:
    _company(user)
    return await TaskService(session).distribute_now(task_id, user)


@router.post(
    "/submissions/{submission_id}/grade",
    response_model=TaskSubmissionForRecruiter,
    summary="Оценить ответ 0–3 (рекрутер)",
    description=(
        "Оценка ставится один раз и поднимает свежесть профиля кандидата: +0,04 + 0,03 × балл. "
        "Повторная оценка — 409 `already_graded`."
    ),
    responses=error_responses(
        *AUTH, 404, TRANSITION, (409, "already_graded", "Оценка уже выставлена"), 422
    ),
)
async def grade_submission(
    submission_id: int, body: SubmissionGrade, user: RecruiterUser, session: SessionDep
) -> Any:
    _company(user)
    return await TaskService(session).grade(submission_id, body, user)
