"""Банк задач: mobile (T4.3). Шаблоны — в модулях папки, здесь только сборка."""

from __future__ import annotations

from ...templates import ItemTemplate
from . import (
    concurrency,
    kotlin,
    lifecycle,
    navigation,
    network,
    performance,
    permissions,
    storage,
    swift,
)

TEMPLATES: tuple[ItemTemplate, ...] = (
    *kotlin.TEMPLATES,
    *swift.TEMPLATES,
    *concurrency.TEMPLATES,
    *lifecycle.TEMPLATES,
    *storage.TEMPLATES,
    *network.TEMPLATES,
    *performance.TEMPLATES,
    *navigation.TEMPLATES,
    *permissions.TEMPLATES,
)
