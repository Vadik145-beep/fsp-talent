"""Настройки приложения из переменных окружения (.env)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> корень репозитория
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    app_version: str = "0.1.0"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://fsp:fsp@localhost:15432/fsp_talent"

    # Каталог фикстур (data/seed). В Docker задаётся через SEED_DIR.
    seed_dir: Path = REPO_ROOT / "data" / "seed"

    # До волны 2 роль и пользователь берутся из заголовков X-Demo-Role / X-Demo-User-Id.
    demo_auth_enabled: bool = True

    jwt_secret: str = "change-me-in-production"
    access_token_ttl_min: int = 15
    refresh_token_ttl_days: int = 30

    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    smtp_from: str = "noreply@fsp-talent.example.com"
    public_frontend_url: str = "http://localhost:15173"

    keycloak_public_url: str = "http://localhost:18180"
    keycloak_internal_url: str = "http://keycloak:8080"
    keycloak_realm: str = "fsp"
    keycloak_client_id: str = "fsp-talent"

    fsp_registry_url: str = "http://fsp-registry-mock:8000"

    cors_origins: list[str] = ["http://localhost:15173", "http://127.0.0.1:15173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
