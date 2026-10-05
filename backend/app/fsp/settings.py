"""Настройки модуля ФСП (вебхук реестра, клиент реестра, вход через ФСП ID).

Адреса Keycloak и реестра — в общих настройках (`app/core/config.py`: KEYCLOAK_*,
FSP_REGISTRY_URL). Здесь — только то, что нужно одному модулю fsp.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class FspSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FSP_", extra="ignore")

    # Общий секрет HMAC-SHA256 для вебхука реестра (заголовок X-FSP-Signature).
    # На проде обязательно поменять; пустая строка выключает вебхук (503).
    webhook_secret: str = "dev-fsp-webhook-secret"
    # Событие с полем sent_at старше этого срока отклоняется (защита от повтора)
    webhook_max_age_sec: int = 300

    # Сервисный токен для реестра (в моке — FSP_MOCK_API_TOKEN); пусто — без заголовка
    registry_token: str = ""
    registry_timeout_sec: float = 5.0
    # Повторы при сетевой ошибке или 5xx (итого попыток = retries + 1)
    registry_retries: int = 2

    # Сколько живёт попытка входа через ФСП ID (state + code_verifier в подписанной cookie)
    oidc_state_ttl_sec: int = 600
    # Ключ подписи cookie со state; пусто — берётся JWT_SECRET
    oidc_state_secret: str = ""
    keycloak_timeout_sec: float = 5.0


@lru_cache
def get_fsp_settings() -> FspSettings:
    return FspSettings()
