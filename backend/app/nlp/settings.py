"""Настройки модуля «Тексты и ИИ» (переменные окружения; без них всё работает на правилах)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class NlpSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM — любой OpenAI-совместимый endpoint (/chat/completions). Пустой ключ — только правила.
    # На стенде это своя открытая модель (llama.cpp в контейнере `llm`), ключ любой непустой.
    llm_provider: str = ""
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    # Таймаут по умолчанию и отдельные — для каждого места, где вызывается модель
    llm_timeout_sec: float = 20.0
    llm_draft_timeout_sec: float = 90.0
    llm_need_timeout_sec: float = 25.0
    llm_resume_timeout_sec: float = 40.0
    # Сколько черновиков задач на одну вакансию пишет модель (остальные — заготовки словаря)
    llm_max_drafts: int = 2
    # Передавать JSON-схему ответа (llama.cpp строит по ней грамматику — ответ всегда по схеме)
    llm_json_schema: bool = False
    # Как подписать модель в интерфейсе и работает ли она на нашем сервере (данные не уходят)
    llm_display_name: str = ""
    llm_local: bool = False
    # Выключатель: true — модель не вызывается вовсе, всё на правилах
    llm_disabled: bool = False

    # Загрузка резюме
    resume_max_bytes: int = 5 * 1024 * 1024
    resume_max_pages: int = 10
    # Куда сохранять загруженные PDF; пусто — файл не сохраняется (храним только разбор)
    resume_storage_dir: str = ""

    @property
    def llm_enabled(self) -> bool:
        if self.llm_disabled:
            return False
        return bool(self.llm_api_key and self.llm_base_url and self.llm_model)

    @property
    def llm_label(self) -> str:
        return self.llm_display_name or self.llm_model


@lru_cache
def get_nlp_settings() -> NlpSettings:
    return NlpSettings()
