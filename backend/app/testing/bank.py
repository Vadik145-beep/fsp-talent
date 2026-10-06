"""Банк шаблонов движка в БД: синхронизация `bank_registry()` → таблица `items`.

Решения:
- шаблон движка = строка `items` с `code` = id шаблона и `generator` = id шаблона;
  id строк выдаёт последовательность, поэтому шаблоны движка идут после 30 фикстурных
  (id 1–30 из `data/seed/items.json`);
- фикстурные записи — демо: генератора в движке у них нет, в адаптивный тест они не попадают,
  в админке видны с метриками и предпросмотром из фикстуры;
- синхронизация идемпотентна: новые шаблоны добавляются со стартовыми a, b и статусом из кода,
  у существующих обновляются только описательные поля (название, тема, грейд, формат, лимит
  времени). a, b, статус, флаг утечки и счётчики — данные БД (калибровка, вывод из оборота),
  синхронизация их не трогает;
- тема шаблона в БД — тема справочника (`topics`), общая для опроса, профиля, подбора
  и заданий из вакансий. Тема движка сохраняется в `generator_params.engine_topic`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import cache

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import Topic
from app.testing.engine import ItemTemplate, TemplateRegistry
from app.testing.engine.bank import bank_registry
from app.testing.formats import api_format
from app.testing.models import Item

logger = logging.getLogger("app.testing.bank")

# Тема движка → тема справочника, если `<spec>.<topic>` в справочнике нет
TOPIC_MAP: dict[str, dict[str, str]] = {
    "backend": {
        "sql": "databases",
        "caching_queues": "architecture",
        "distributed_systems": "architecture",
        "python": "algorithms",
    },
    "frontend": {
        "javascript": "js_core",
        "javascript_async": "js_core",
        "css": "css_layout",
        "accessibility": "css_layout",
        "browser_network": "browser",
        "dom_events": "browser",
        "web_security": "browser",
    },
    "mobile": {
        "android_lifecycle": "lifecycle",
        "app_lifecycle": "lifecycle",
        "kotlin": "language",
        "swift": "language",
        "concurrency": "language",
        "navigation": "ui",
        "performance": "ui",
        "data_storage": "networking",
        "networking_offline": "networking",
        "publishing_permissions": "release",
    },
    "data_ml": {
        "classic_ml": "ml_basics",
        "mlops": "ml_basics",
        "model_validation": "metrics",
        "pandas_numpy": "sql_data",
        "preprocessing": "sql_data",
    },
    "qa": {
        "bug_reports": "process",
        "test_management": "process",
        "security": "api_testing",
        "sql": "api_testing",
    },
    "devops": {
        "bash": "linux",
        "networking": "linux",
        "kubernetes": "containers",
        "incidents": "monitoring",
    },
}

VARIANT_SAMPLE = 200  # по скольким seed считаем число различных вариантов


@cache
def registry() -> TemplateRegistry:
    """Реестр шаблонов движка (один на процесс)."""
    return bank_registry()


def engine_template(item: Item) -> ItemTemplate | None:
    """Шаблон движка для строки банка; None — демо-запись без генератора."""
    reg = registry()
    for key in (item.generator, item.code):
        if key in reg:
            return reg.get(key)
    return None


@cache
def variants_count(template_id: str) -> int:
    """Сколько различных вариантов шаблон дал на первых VARIANT_SAMPLE seed."""
    t = registry().get(template_id)
    return len({t.generate(seed).fingerprint for seed in range(VARIANT_SAMPLE)})


def catalog_topic(spec: str, engine_topic: str, known: set[str]) -> str | None:
    """Тема справочника для темы движка. None — подходящей темы в справочнике нет."""
    direct = f"{spec}.{engine_topic}"
    if direct in known:
        return direct
    mapped = TOPIC_MAP.get(spec, {}).get(engine_topic)
    if mapped and f"{spec}.{mapped}" in known:
        return f"{spec}.{mapped}"
    fallback = sorted(t for t in known if t.startswith(f"{spec}."))
    return fallback[0] if fallback else None


@dataclass
class SyncReport:
    total: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0

    def format(self) -> str:
        return (
            f"Шаблонов движка: {self.total}; добавлено: {self.created}, "
            f"обновлено: {self.updated}, пропущено (нет темы в справочнике): {self.skipped}"
        )


def _description(t: ItemTemplate) -> str:
    return (
        f"Параметрический шаблон движка ({t.id}): числа, имена, данные и порядок вариантов "
        "зависят от seed, у каждого кандидата свой вариант."
    )


async def sync_bank(session: AsyncSession) -> SyncReport:
    """Синхронизировать шаблоны движка в таблицу `items` (коммит — за вызывающим)."""
    reg = registry()
    report = SyncReport(total=len(reg))
    known = set((await session.scalars(select(Topic.code))).all())
    existing = {
        i.code: i
        for i in (await session.scalars(select(Item).where(Item.code.in_([t.id for t in reg]))))
    }
    new_rows = []
    for t in reg:
        topic = catalog_topic(t.specialization, t.topic, known)
        if topic is None:
            logger.warning("Шаблон %s пропущен: нет темы %s в справочнике", t.id, t.topic)
            report.skipped += 1
            continue
        params = {"engine_topic": t.topic, "variants_count": variants_count(t.id)}
        fields = {
            "title": (t.title or t.id)[:200],
            "description": _description(t),
            "specialization": t.specialization,
            "topic": topic,
            "target_grade": t.target_grade,
            "format": api_format(t.format),
            "generator": t.id,
            "generator_params": params,
            "time_limit_s": int(t.time_limit_s),
        }
        item = existing.get(t.id)
        if item is None:
            new_rows.append(
                {
                    "code": t.id,
                    **fields,
                    "a": float(t.a),
                    "b": float(t.b),
                    "status": str(t.status),
                    "source": "expert",
                }
            )
            continue
        changed = False
        for key, value in fields.items():
            if getattr(item, key) != value:
                setattr(item, key, value)
                changed = True
        report.updated += int(changed)
    if new_rows:
        result = await session.execute(
            pg_insert(Item).values(new_rows).on_conflict_do_nothing(index_elements=["code"])
        )
        report.created = max(result.rowcount or 0, 0)  # type: ignore[attr-defined]
    await session.flush()
    return report


async def ensure_bank(session: AsyncSession) -> None:
    """Догрузить шаблоны движка, если их нет в БД (после пересева или на чистой базе)."""
    codes = [t.id for t in registry()]
    present = await session.scalar(select(func.count()).where(Item.code.in_(codes)))
    if (present or 0) < len(codes):
        report = await sync_bank(session)
        await session.commit()
        logger.info(report.format())
