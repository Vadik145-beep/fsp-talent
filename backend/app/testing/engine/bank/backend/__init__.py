"""Банк задач: backend (T4.3). Шаблоны — в модулях папки, здесь только сборка."""

from __future__ import annotations

from ...templates import ItemTemplate
from . import (
    algorithms,
    caching_queues,
    concurrency,
    distributed,
    http_api,
    python_lang,
    security,
    sql,
)

TEMPLATES: tuple[ItemTemplate, ...] = (
    *algorithms.TEMPLATES,
    *python_lang.TEMPLATES,
    *sql.TEMPLATES,
    *http_api.TEMPLATES,
    *concurrency.TEMPLATES,
    *caching_queues.TEMPLATES,
    *security.TEMPLATES,
    *distributed.TEMPLATES,
)
