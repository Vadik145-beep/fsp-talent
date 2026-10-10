"""Регулярные короткие задания: рекрутер создаёт, система раз в неделю предлагает кандидату
до трёх задач от разных компаний, кандидат выбирает одну и отвечает, рекрутер оценивает 0–3
[ТЗ 2.1, E9]."""

from datetime import datetime

from pydantic import ConfigDict, Field

from app.candidates.schemas import CandidateCard
from app.common import fixtures
from app.common.enums import AnswerKind, SubmissionStatus, TaskStatus
from app.common.schemas import ApiModel, OutModel


class RegularTaskCreate(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "Кэш для медленного API",
                    "statement": "Сервис отвечает 2 секунды. Предложите, как кэшировать ответы.",
                    "category": "backend:middle",
                    "deadline_days": 7,
                }
            ]
        }
    )

    title: str = Field(min_length=3, max_length=200)
    statement: str = Field(min_length=10, max_length=5000)
    category: str = Field(pattern=r"^[a-z_]+:[a-z]+$")
    deadline_days: int = Field(default=7, ge=1, le=30)


class RegularTask(OutModel):
    """Задание (запись `regular_tasks.json`)."""

    model_config = ConfigDict(json_schema_extra=fixtures.first_example("regular_tasks"))

    id: int
    company_id: int
    company_name: str
    recruiter_id: int
    title: str
    statement: str
    category: str
    category_label: str
    deadline_days: int
    status: TaskStatus
    submissions_count: int = 0
    created_at: datetime


class TaskSubmission(OutModel):
    """Предложенное кандидату задание и его ответ (запись `task_submissions.json`)."""

    model_config = ConfigDict(json_schema_extra=fixtures.first_example("task_submissions"))

    id: int
    task_id: int
    candidate_id: int
    task_title: str
    statement: str
    company_name: str
    status: SubmissionStatus
    assigned_at: datetime
    due_at: datetime
    answer_kind: AnswerKind | None = None
    answer_text: str | None = None
    submitted_at: datetime | None = None
    score: int | None = Field(default=None, ge=0, le=3)
    grader_comment: str | None = None
    graded_at: datetime | None = None


class TaskSubmissionForRecruiter(TaskSubmission):
    """Ответ в кабинете рекрутера — кандидат обезличен."""

    candidate: CandidateCard | None = None


class TaskInbox(OutModel):
    """Раздел «Задания» кандидата: задачи недели на выбор и история ответов."""

    offers: list[TaskSubmission] = Field(
        description="Задачи недели на выбор (до трёх, от разных компаний), ближайший срок — первым"
    )
    history: list[TaskSubmission] = Field(description="Отправленные и оценённые ответы")
    answered_this_week: bool = Field(
        description="Кандидат уже ответил на этой неделе — новые задачи придут в понедельник"
    )
    freshness: float = Field(ge=0, le=1)


class SubmissionAnswer(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "answer_kind": "approach",
                    "answer_text": "Кэш в Redis с TTL 60 секунд и инвалидацией по событию.",
                }
            ]
        }
    )

    answer_kind: AnswerKind
    answer_text: str = Field(min_length=1, max_length=10000)


class SubmissionGrade(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"score": 3, "comment": "Чётко и по делу"}]}
    )

    score: int = Field(ge=0, le=3)
    comment: str | None = Field(default=None, max_length=1000)


class DistributionResult(OutModel):
    """Итог ручной раздачи задания."""

    model_config = ConfigDict(json_schema_extra={"examples": [{"assigned": 3}]})

    assigned: int = Field(ge=0, description="Скольким кандидатам задание предложено")


class TaskJobResult(OutModel):
    """Итог периодической работы (раздача, просрочка, свежесть)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"job": "tick", "expired": 2, "assigned": 5, "freshness_factor": 0.977}]
        }
    )

    job: str
    expired: int = Field(ge=0, description="Сколько заданий просрочено")
    assigned: int = Field(ge=0, description="Сколько задач предложено кандидатам")
    freshness_factor: float = Field(ge=0, le=1, description="Множитель свежести профилей")
