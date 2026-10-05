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

    # Запасной режим для прототипа и заглушек: если нет `Authorization: Bearer`, пользователь
    # берётся из заголовков X-Demo-Role / X-Demo-User-Id, а пользователи, которых ещё нет в БД, —
    # из фикстур data/seed. На проде выключить.
    demo_auth_enabled: bool = True

    # Сессии: JWT access (HS256) в теле ответа + refresh в httpOnly cookie (хеш — в БД).
    jwt_secret: str = "change-me-in-production"
    access_token_ttl_min: int = 15
    refresh_token_ttl_days: int = 30
    # None — secure-cookie везде, кроме APP_ENV=dev
    refresh_cookie_secure: bool | None = None

    # Письма со ссылками: подтверждение почты и сброс пароля
    email_verify_ttl_hours: int = 24
    password_reset_ttl_min: int = 60
    email_resend_interval_sec: int = 60

    # Ограничение попыток входа: не больше N неудачных за окно на пару почта+IP
    login_max_attempts: int = 5
    login_window_min: int = 15

    # Администратор по умолчанию: создаётся при старте, если такой почты ещё нет в БД
    admin_email: str = "admin@example.com"
    admin_password: str = "demo1234"
    admin_full_name: str = "Администратор платформы"

    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = False
    smtp_timeout_sec: float = 10
    smtp_from: str = "noreply@fsp-talent.example.com"
    public_frontend_url: str = "http://localhost:15173"

    keycloak_public_url: str = "http://localhost:18180"
    keycloak_internal_url: str = "http://keycloak:8080"
    keycloak_realm: str = "fsp"
    keycloak_client_id: str = "fsp-talent"

    fsp_registry_url: str = "http://fsp-registry-mock:8000"

    cors_origins: list[str] = ["http://localhost:15173", "http://127.0.0.1:15173"]

    @property
    def cookie_secure(self) -> bool:
        if self.refresh_cookie_secure is not None:
            return self.refresh_cookie_secure
        return self.app_env != "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()
