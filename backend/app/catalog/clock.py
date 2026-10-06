"""Время платформы: даты в ответах API отдаём по Москве (+03:00), как в фикстурах data/seed.

asyncpg возвращает `timestamptz` в UTC; переводим в МСК, чтобы бэкенд на БД и фронт на моках
показывали одинаковые строки дат.
"""

from datetime import UTC, date, datetime, time, timedelta, timezone

MSK = timezone(timedelta(hours=3), "MSK")


def now_msk() -> datetime:
    return datetime.now(UTC).astimezone(MSK)


def as_msk(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(MSK)


def start_of_day_msk(value: date | None) -> datetime | None:
    """Дата (например, «тест доступен с») → начало этого дня по Москве."""
    if value is None:
        return None
    return datetime.combine(value, time.min, tzinfo=MSK)


def parse_dt(value: str | None) -> datetime | None:
    """ISO-строка фикстуры → aware datetime (без зоны считаем МСК)."""
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=MSK)
