"""Опрос специализации, адаптивный тест, результат, грейд и история.

Движок CAT живёт в `app/testing/engine` (трек 0b); здесь — только контракт API.
Правильные ответы кандидату не отдаются никогда (защита банка от утечек).
"""

from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from app.candidates.schemas import TopicScore
from app.common import fixtures
from app.common.enums import (
    GradeCode,
    GradeEventType,
    ItemFormat,
    SpecializationCode,
    TestSessionKind,
    TestSessionStatus,
)
from app.common.schemas import ApiModel, OutModel

# ---------- опрос ----------


class SurveyOption(OutModel):
    id: str
    label: str
    specializations: list[SpecializationCode] = Field(
        default_factory=list, description="За какие специализации голосует вариант"
    )


class SurveyQuestion(OutModel):
    model_config = ConfigDict(json_schema_extra=fixtures.first_example("survey_questions"))

    id: str
    text: str
    kind: Literal["single", "multi", "text"]
    required: bool = True
    options: list[SurveyOption] = Field(default_factory=list)


class SurveyAnswer(ApiModel):
    question_id: str
    option_ids: list[str] = Field(default_factory=list)
    text: str | None = Field(default=None, max_length=1000)


class SurveySubmit(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "answers": [
                        {"question_id": "q1", "option_ids": ["q1_api"]},
                        {"question_id": "q2", "option_ids": ["q2_python", "q2_sql"]},
                    ]
                }
            ]
        }
    )

    answers: list[SurveyAnswer] = Field(min_length=1)


class SpecializationScore(OutModel):
    specialization: SpecializationCode
    score: float = Field(ge=0, le=1)


class SurveyResult(OutModel):
    """Рекомендованная специализация и темы теста. Баллом не оценивается."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "recommended_specialization": "backend",
                    "alternatives": [
                        {"specialization": "backend", "score": 0.72},
                        {"specialization": "data_ml", "score": 0.18},
                    ],
                    "suggested_grade": "middle",
                    "topics": ["backend.http_api", "backend.databases"],
                    "explanation": ["Вы чаще выбирали задачи про API и базы данных"],
                }
            ]
        }
    )

    recommended_specialization: SpecializationCode
    alternatives: list[SpecializationScore]
    suggested_grade: GradeCode
    topics: list[str]
    explanation: list[str]


# ---------- тест ----------


class ChoiceOption(OutModel):
    id: str
    text: str


class ItemView(OutModel):
    """Вариант задачи, как его видит кандидат (без правильного ответа)."""

    instance_id: str = Field(description="Id варианта (шаблон + seed), отправляется с ответом")
    format: ItemFormat
    topic: str
    topic_label: str
    prompt: str
    code: str | None = Field(default=None, description="Код для code_output / find_error_line")
    options: list[ChoiceOption] | None = Field(default=None, description="Для выбора вариантов")
    steps: list[ChoiceOption] | None = Field(default=None, description="Для упорядочивания")
    unit: str | None = Field(default=None, description="Единица для численного ответа")
    time_limit_sec: int = Field(gt=0)


class AnswerPayload(ApiModel):
    """Ответ кандидата; заполняется поле по формату задачи."""

    choice_ids: list[str] | None = Field(default=None, description="single/multiple_choice")
    value: float | None = Field(default=None, description="numeric")
    text: str | None = Field(default=None, max_length=500, description="short_text, code_output")
    line: int | None = Field(default=None, ge=1, description="find_error_line")
    order: list[str] | None = Field(default=None, description="ordering: id шагов по порядку")


class TestSessionCreate(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"specialization": "backend", "target_grade": "middle", "kind": "placement"}
            ]
        }
    )

    specialization: SpecializationCode
    target_grade: GradeCode
    kind: TestSessionKind = TestSessionKind.placement


class TestSession(OutModel):
    """Сессия теста (запись `test_sessions.json`)."""

    model_config = ConfigDict(json_schema_extra=fixtures.first_example("test_sessions"))

    id: int
    candidate_id: int
    specialization: SpecializationCode
    target_grade: GradeCode
    kind: TestSessionKind
    status: TestSessionStatus
    started_at: datetime
    finished_at: datetime | None = None
    items_answered: int = Field(ge=0)
    max_items: int = Field(default=15, gt=0)
    theta: float | None = None
    se: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    result_grade: GradeCode | None = None
    result_category: str | None = None
    passed: bool | None = Field(default=None, description="Подтверждён ли заявленный грейд")
    topic_scores: list[TopicScore] = Field(default_factory=list)


class TestSessionState(OutModel):
    """Экран теста: прогресс, текущая задача, остаток времени (считает сервер)."""

    session: TestSession
    current_item: ItemView | None
    item_number: int = Field(ge=0, description="Номер текущей задачи, с 1")
    time_left_sec: int | None = None


class AnswerSubmit(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"instance_id": "it-0001-s42", "answer": {"choice_ids": ["b"]}}]
        }
    )

    instance_id: str
    answer: AnswerPayload


class AnswerAck(OutModel):
    """Ответ принят. Верно/неверно не сообщаем."""

    session_id: int
    answered: int
    finished: bool
    next_item: ItemView | None = None
    time_expired: bool = Field(default=False, description="Ответ пришёл после лимита времени")


class Recommendation(OutModel):
    action: Literal["stay", "offer_lower", "offer_higher", "retry_later"]
    message: str
    available_at: datetime | None = None


class TestResult(OutModel):
    """Результат: категория, θ с интервалом, разбор по темам [ТЗ 2, T4.6]."""

    session_id: int
    specialization: SpecializationCode
    target_grade: GradeCode
    result_grade: GradeCode
    category: str
    category_label: str
    theta: float
    se: float
    ci_low: float
    ci_high: float
    passed: bool
    items_answered: int
    finished_at: datetime
    topic_scores: list[TopicScore]
    strong_topics: list[str]
    weak_topics: list[str]
    recommendation: Recommendation


# ---------- грейд ----------


class GradeHistoryEntry(OutModel):
    """Событие истории грейда (запись `grade_history.json`)."""

    model_config = ConfigDict(json_schema_extra=fixtures.first_example("grade_history"))

    id: int
    candidate_id: int
    at: datetime
    event: GradeEventType
    specialization: SpecializationCode | None = None
    grade_from: GradeCode | None = None
    grade_to: GradeCode | None = None
    test_session_id: int | None = None
    comment: str = ""


class GradeStatus(OutModel):
    """Экран «Категория и грейд»: статус, кулдауны, история."""

    candidate_id: int
    specialization: SpecializationCode | None
    grade: GradeCode | None
    category: str | None
    category_label: str | None
    theta: float | None
    grade_changed_at: datetime | None
    grade_change_cooldown_days: int = 90
    retry_cooldown_days: int = 30
    can_test_lower: bool
    lower_available_at: datetime | None
    can_test_higher: bool
    higher_available_at: datetime | None
    history: list[GradeHistoryEntry]
    tests: list[TestSession]
