"""Точка входа FastAPI: роутеры модулей, единый формат ошибок, логирование, /api/health."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.admin.router import reports_router
from app.admin.router import router as admin_router
from app.auth.router import router as auth_router
from app.candidates.router import router as candidates_router
from app.catalog.router import router as catalog_router
from app.companies.router import router as companies_router
from app.core.config import get_settings
from app.core.db import dispose_engine, get_engine
from app.core.errors import error_responses, register_error_handlers
from app.core.logging import register_request_logging, setup_logging
from app.eval.router import router as eval_router
from app.fsp.router import router as fsp_router
from app.invitations.router import router as invitations_router
from app.matching.router import router as matching_router
from app.tasks.router import router as tasks_router
from app.testing.router import router as testing_router
from app.users.router import router as users_router
from app.vacancies.router import applications_router
from app.vacancies.router import router as vacancies_router

DESCRIPTION = """
API платформы подбора IT-специалистов **fsp-talent** (спецтрек ФСП, ЛЦТ 2026).

**Авторизация до волны 2 — заглушка.** Роль передаётся заголовком `X-Demo-Role`
(`candidate` | `recruiter` | `admin`), необязательно — `X-Demo-User-Id`
(id пользователя из `data/seed/users.json`).
Без заголовка защищённые методы отвечают 401, с чужой ролью — 403.

Ошибки всегда в формате `{"code": "...", "message": "...", "details": {...}}`.
Данные заглушек — фикстуры `data/seed/*.json` (те же, что у моков фронтенда).
"""

TAGS = [
    {"name": "system", "description": "Служебное"},
    {"name": "auth", "description": "Регистрация, вход, токены, ФСП ID"},
    {"name": "users", "description": "Согласия 152-ФЗ"},
    {"name": "catalog", "description": "Справочники"},
    {"name": "candidates", "description": "Кабинет соискателя и банк кандидатов (обезличенно)"},
    {"name": "companies", "description": "Компания рекрутера"},
    {"name": "testing", "description": "Опрос, адаптивный тест, грейд"},
    {"name": "fsp", "description": "Достижения ФСП"},
    {"name": "matching", "description": "Потребности и подборка"},
    {"name": "invitations", "description": "Приглашения и выход на контакт"},
    {"name": "vacancies", "description": "Вакансии и отклики"},
    {"name": "tasks", "description": "Регулярные задания"},
    {"name": "admin", "description": "Кабинет администратора, жалобы"},
    {"name": "eval", "description": "Валидация и метрики"},
]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    db: Literal["ok", "error"]
    db_revision: str | None = None


system_router = APIRouter(tags=["system"])


@system_router.get(
    "/health",
    response_model=HealthResponse,
    summary="Проверка живости (с проверкой БД)",
    responses={503: {"model": HealthResponse, "description": "БД недоступна"}, **error_responses()},
)
async def health() -> Any:
    settings = get_settings()
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
            revision = (
                await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            ).scalar_one_or_none()
    except Exception as exc:
        body = HealthResponse(status="degraded", version=settings.app_version, db="error")
        return JSONResponse(
            status_code=503, content=body.model_dump() | {"error": type(exc).__name__}
        )
    return HealthResponse(status="ok", version=settings.app_version, db="ok", db_revision=revision)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)
    app = FastAPI(
        title="fsp-talent API",
        version=settings.app_version,
        description=DESCRIPTION,
        openapi_tags=TAGS,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        swagger_ui_oauth2_redirect_url="/api/docs/oauth2-redirect",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    register_request_logging(app)

    api = APIRouter(prefix="/api")
    for router in (
        system_router,
        auth_router,
        users_router,
        catalog_router,
        candidates_router,
        companies_router,
        testing_router,
        fsp_router,
        matching_router,
        invitations_router,
        vacancies_router,
        applications_router,
        tasks_router,
        admin_router,
        reports_router,
        eval_router,
    ):
        api.include_router(router)
    app.include_router(api)
    return app


app = create_app()
