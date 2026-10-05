"""Банк задач: data_ml (T4.3). Шаблоны — в модулях папки, здесь только сборка."""

from __future__ import annotations

from ...templates import ItemTemplate
from . import (
    classic_ml,
    deep_learning,
    metrics,
    mlops,
    pandas_numpy,
    preprocessing,
    stats,
    validation,
)

TEMPLATES: tuple[ItemTemplate, ...] = (
    *metrics.TEMPLATES,
    *validation.TEMPLATES,
    *pandas_numpy.TEMPLATES,
    *stats.TEMPLATES,
    *preprocessing.TEMPLATES,
    *classic_ml.TEMPLATES,
    *deep_learning.TEMPLATES,
    *mlops.TEMPLATES,
)
