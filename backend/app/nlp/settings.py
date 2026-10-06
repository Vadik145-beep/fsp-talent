"""Настройки модуля «Тексты и ИИ» (переменные окружения; без них всё работает на правилах)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class NlpSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM — любой OpenAI-совместимый endpoint (/chat/completions). Пустой ключ — только правила.
    llm_provider: str = ""
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout_sec: float = 20.0

    # Загрузка резюме
    resume_max_bytes: int = 5 * 1024 * 1024
    resume_max_pages: int = 10
    # Куда сохранять загруженные PDF; пусто — файл не сохраняется (храним только разбор)
    resume_storage_dir: str = ""

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key and self.llm_base_url and self.llm_model)


@lru_cache
def get_nlp_settings() -> NlpSettings:
    return NlpSettings()
