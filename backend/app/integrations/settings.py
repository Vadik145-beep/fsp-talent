"""Настройки интеграции с ATS (переменные окружения с префиксом INTEGRATIONS_)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class IntegrationSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="INTEGRATIONS_", extra="ignore")

    # Таймаут одного запроса вебхука, секунд
    webhook_timeout_sec: float = 5
    # Сколько всего попыток доставки (первая + повторы)
    webhook_max_attempts: int = 5
    # Паузы перед повторами, секунд (последняя повторяется, если попыток больше)
    webhook_backoff_sec: list[int] = [60, 300, 1800, 7200]
    # Разрешить адреса localhost и частных сетей (для разработки и тестов). На проде — false.
    allow_private_urls: bool = True


@lru_cache
def get_integration_settings() -> IntegrationSettings:
    return IntegrationSettings()
