"""Помощники для тестов и ручной проверки: перезалить сид и выполнить SQL синхронно.

Каждый вызов открывает своё подключение (NullPool) в своём event loop, поэтому их можно
звать из обычных pytest-тестов рядом с TestClient приложения.
"""

import asyncio
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.seed.loader import SeedReport, run_seed


def reseed_sync(database_url: str | None = None) -> SeedReport:
    """Очистить таблицы и залить фикстуры заново."""
    return asyncio.run(run_seed(database_url, reset=True))


def seed_sync(database_url: str | None = None) -> SeedReport:
    """Догрузить фикстуры без очистки (идемпотентно)."""
    return asyncio.run(run_seed(database_url))


def sql_sync(statement: str, params: dict[str, Any] | None = None) -> list[Any]:
    """Выполнить SQL в отдельной транзакции; для SELECT вернуть строки."""

    async def run() -> list[Any]:
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                result = await conn.execute(text(statement), params or {})
                return list(result.all()) if result.returns_rows else []
        finally:
            await engine.dispose()

    return asyncio.run(run())
