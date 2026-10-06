"""Настройки загрузчика демо-данных (переменные окружения)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class SeedSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # SEED_ON_STARTUP=true — бэкенд при старте сам загружает data/seed (только для dev).
    # Загрузка идемпотентна: существующие строки не трогаются, дубликатов нет.
    seed_on_startup: bool = False


@lru_cache
def get_seed_settings() -> SeedSettings:
    return SeedSettings()
