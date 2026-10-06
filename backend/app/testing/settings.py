"""Настройки модуля тестирования (переменные окружения с префиксом TESTING_)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class TestingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="TESTING_", extra="ignore")
    __test__ = False

    # Длина теста и остановка (T4.3: до 20 задач, стоп при SE < 0,30, минимум 6)
    cat_max_items: int = 20
    cat_min_items: int = 6
    cat_se_stop: float = 0.30
    # Лимит экспозиции включается, только если в специализации столько активных шаблонов
    exposure_min_bank: int = 100
    # Сессия считается брошенной, если на текущую задачу нет ответа дольше лимита + столько минут
    abandon_after_min: int = 30
    # Детектор утечек запускается автоматически после каждой N-й завершённой сессии
    leak_scan_every: int = 50
    # Калибровка: шаблон пересчитывается, если у него не меньше стольких ответов
    calibration_min_responses: int = 30


@lru_cache
def get_testing_settings() -> TestingSettings:
    return TestingSettings()
