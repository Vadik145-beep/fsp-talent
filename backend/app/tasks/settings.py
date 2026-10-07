"""Настройки регулярных заданий (переменные окружения с префиксом TASKS_)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class TaskSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="TASKS_", extra="ignore")

    # Сколько кандидатов получает одно задание за один проход раздачи
    max_assign_per_run: int = 50
    # Свежесть профиля 0..1: прибавка за отправленный ответ и за оценку (база + за балл 0–3)
    freshness_answer_bonus: float = 0.08
    freshness_grade_base: float = 0.04
    freshness_grade_per_point: float = 0.03
    # Без новых заданий свежесть падает вдвое за столько дней
    freshness_half_life_days: float = 30


@lru_cache
def get_task_settings() -> TaskSettings:
    return TaskSettings()
