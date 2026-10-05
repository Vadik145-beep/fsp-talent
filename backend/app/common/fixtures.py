"""Чтение фикстур `data/seed/*.json` — общий источник данных для заглушек API и моков фронта.

Каждый файл — массив объектов с полем `id`. Данные кэшируются в памяти процесса;
заглушки их не меняют (мутации возвращают результат, но не сохраняют его).
"""

import json
from functools import cache
from pathlib import Path
from typing import Any

from app.core.config import get_settings

Record = dict[str, Any]


def seed_dir() -> Path:
    return Path(get_settings().seed_dir)


@cache
def load(name: str) -> tuple[Record, ...]:
    path = seed_dir() / f"{name}.json"
    if not path.exists():
        return ()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Фикстура {path} должна быть массивом объектов")
    return tuple(data)


def all_records(name: str) -> list[Record]:
    """Копия списка (сами объекты не копируются — не мутировать)."""
    return list(load(name))


def by_id(name: str, obj_id: object) -> Record | None:
    for record in load(name):
        if record.get("id") == obj_id:
            return record
    return None


def where(name: str, **filters: object) -> list[Record]:
    return [r for r in load(name) if all(r.get(k) == v for k, v in filters.items())]


def first_example(name: str) -> dict[str, Any]:
    """Пример для OpenAPI (`json_schema_extra`) из первой записи фикстуры."""
    records = load(name)
    return {"examples": [records[0]]} if records else {}


def clear_cache() -> None:
    load.cache_clear()
