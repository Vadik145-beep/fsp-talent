"""Подготовка БД при старте приложения: администратор по умолчанию и резерв id фикстур.

Запускается из lifespan роутера auth (FastAPI сливает lifespan подключённых роутеров с lifespan
приложения), поэтому `main.py` трогать не нужно. Если БД недоступна или миграции не применены —
пишем предупреждение в лог и продолжаем: health покажет проблему.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import hash_password
from app.common import fixtures
from app.common.enums import Role
from app.core.config import get_settings
from app.core.db import get_session

logger = logging.getLogger("app.auth.bootstrap")

# таблица -> фикстура с теми же id (загрузчик демо-данных сохраняет id фикстур)
FIXTURE_ID_TABLES = {
    "users": "users",
    "companies": "companies",
    "recruiters": "recruiters",
    "candidate_profiles": "candidates",
}


async def reserve_fixture_ids(session: AsyncSession) -> None:
    """Сдвинуть последовательности id за максимальный id фикстур.

    Тогда пользователи, компании и профили, созданные через API, не займут id демо-данных, и
    загрузчик демо-данных сможет вставить фикстуры со своими id. Последовательность только растёт.
    """
    for table, fixture in FIXTURE_ID_TABLES.items():
        target = max((int(r["id"]) for r in fixtures.load(fixture)), default=0)
        if target == 0:
            continue
        seq = (
            await session.execute(text(f"SELECT pg_get_serial_sequence('{table}', 'id')"))
        ).scalar_one_or_none()
        if seq is None:
            continue
        last_value, is_called = (
            await session.execute(text(f"SELECT last_value, is_called FROM {seq}"))
        ).one()
        current = last_value if is_called else last_value - 1
        if current < target:
            await session.execute(
                text("SELECT setval(CAST(:seq AS regclass), :value)"), {"seq": seq, "value": target}
            )
    await session.commit()


async def ensure_default_admin(session: AsyncSession) -> None:
    """Создать администратора из ADMIN_EMAIL / ADMIN_PASSWORD, если такой почты ещё нет."""
    from app.users.models import User

    settings = get_settings()
    email = settings.admin_email.strip().lower()
    if not email:
        return
    exists = (await session.execute(select(User.id).where(func.lower(User.email) == email))).first()
    if exists is not None:
        return
    if settings.app_env != "dev" and settings.admin_password in ("demo1234", "change-me"):
        logger.warning("ADMIN_PASSWORD по умолчанию вне dev — смените его в .env")
    user = User(
        email=email,
        password_hash=hash_password(settings.admin_password),
        role=str(Role.admin),
        full_name=settings.admin_full_name,
        email_verified=True,
    )
    # если такой админ есть в фикстурах — берём его id, чтобы id в БД совпадали с фикстурами
    fixture = next((u for u in fixtures.load("users") if u["email"] == email), None)
    if (
        fixture is not None
        and fixture.get("role") == Role.admin
        and await session.get(User, int(fixture["id"])) is None
    ):
        user.id = int(fixture["id"])
        user.full_name = fixture.get("full_name") or user.full_name
    session.add(user)
    await session.commit()
    logger.info("Создан администратор по умолчанию: %s (id=%s)", email, user.id)


async def bootstrap() -> None:
    try:
        async for session in get_session():
            await reserve_fixture_ids(session)
            await ensure_default_admin(session)
    except Exception as exc:  # БД ещё не готова — не мешаем старту приложения
        logger.warning("Подготовка БД для авторизации пропущена: %s", exc)


@asynccontextmanager
async def auth_lifespan(_: FastAPI) -> AsyncIterator[None]:
    await bootstrap()
    yield
