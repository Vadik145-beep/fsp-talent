"""Админка банка задач на БД: метрики, покрытие, предпросмотр, вывод из оборота, калибровка.

Метрики шаблона движка считаются по журналу `test_answers`:
- показы — счётчик `items.exposures` (растёт при каждой выдаче варианта);
- доля верных (факт) — верные / отвеченные;
- доля верных (ожидание) — среднее P(верно) по IRT при θ отвечавших без этой задачи.
У демо-записей из `data/seed/items.json` генератора нет: метрики и предпросмотр — из фикстуры.
"""

from __future__ import annotations

import secrets
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.audit import write_audit
from app.catalog.clock import as_msk
from app.catalog.models import Topic
from app.common import fixtures
from app.common.enums import GradeCode
from app.common.schemas import paginate
from app.core.errors import AppError, not_found
from app.core.security import CurrentUser
from app.testing import journal
from app.testing.bank import engine_template, ensure_bank, variants_count
from app.testing.formats import answer_payload, item_view
from app.testing.models import Item
from app.testing.settings import get_testing_settings

PREVIEW_COUNT = 3

STATS_SQL = text(
    """
    SELECT ta.item_id,
           COUNT(*) AS answered,
           COALESCE(SUM(CASE WHEN ta.correct THEN 1 ELSE 0 END), 0) AS n_correct,
           AVG(1.0 / (1.0 + EXP(-i.a * (ta.theta_loo - i.b))))
               FILTER (WHERE ta.theta_loo IS NOT NULL) AS expected
    FROM test_answers ta JOIN items i ON i.id = ta.item_id
    WHERE ta.answered_at IS NOT NULL
    GROUP BY ta.item_id
    """
)


class ItemsAdminService:
    def __init__(self, session: AsyncSession, actor: CurrentUser | None = None) -> None:
        self.session = session
        self.actor = actor

    async def _labels(self) -> dict[str, str]:
        rows = await self.session.execute(select(Topic.code, Topic.label))
        return dict(rows.all())  # type: ignore[arg-type]

    async def _stats(self) -> dict[int, tuple[int, int, float | None]]:
        rows = await self.session.execute(STATS_SQL)
        return {
            r.item_id: (
                int(r.answered),
                int(r.n_correct),
                None if r.expected is None else float(r.expected),
            )
            for r in rows
        }

    def _summary(
        self, item: Item, labels: dict[str, str], stats: dict[int, tuple[int, int, float | None]]
    ) -> dict[str, Any]:
        template = engine_template(item)
        fixture = None if template else fixtures.by_id("items", item.id)
        if fixture is not None and fixture.get("code") != item.code:
            fixture = None
        answered, n_correct, expected = stats.get(item.id, (0, 0, None))
        correct_rate = round(n_correct / answered, 3) if answered else None
        if fixture is not None and not answered:
            correct_rate = fixture.get("correct_rate")
            expected = fixture.get("expected_correct_rate")
        if template is not None:
            variants = variants_count(template.id)
        else:
            variants = int((fixture or {}).get("variants_count") or 1)
        return {
            "id": item.id,
            "code": item.code,
            "title": item.title,
            "specialization": item.specialization,
            "topic": item.topic,
            "topic_label": labels.get(item.topic, item.topic),
            "target_grade": item.target_grade,
            "format": item.format,
            "a": item.a,
            "b": item.b,
            "status": item.status,
            "source": item.source,
            "exposures": item.exposures,
            "correct_rate": correct_rate,
            "expected_correct_rate": None if expected is None else round(expected, 3),
            "leak_flag": item.leak_flag,
            "leak_score": max(item.leak_score or 0.0, 0.0),
            "variants_count": max(variants, 1),
            "created_at": as_msk(item.created_at),
        }

    async def items(
        self,
        specialization: str | None,
        topic: str | None,
        status: str | None,
        leak_flag: bool | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        await ensure_bank(self.session)
        stmt = select(Item).order_by(Item.id)
        if specialization:
            stmt = stmt.where(Item.specialization == specialization)
        if topic:
            stmt = stmt.where(Item.topic == topic)
        if status:
            stmt = stmt.where(Item.status == status)
        if leak_flag is not None:
            stmt = stmt.where(Item.leak_flag.is_(leak_flag))
        rows = list((await self.session.scalars(stmt)).all())
        labels, stats = await self._labels(), await self._stats()
        page_data = paginate(rows, page, page_size)
        page_data["items"] = [self._summary(i, labels, stats) for i in page_data["items"]]
        return page_data

    async def _get(self, item_id: int) -> Item:
        item = await self.session.get(Item, item_id)
        if item is None:
            raise not_found("item", item_id)
        return item

    async def item(self, item_id: int) -> dict[str, Any]:
        item = await self._get(item_id)
        labels = await self._labels()
        detail = self._summary(item, labels, await self._stats())
        detail["description"] = item.description
        template = engine_template(item)
        previews: list[dict[str, Any]] = []
        if template is not None:
            seeds: list[int] = []
            fingerprints: set[str] = set()
            # варианты из разных seed; повтор того же текста пропускаем
            for _ in range(PREVIEW_COUNT * 10):
                seed = secrets.randbelow(2**31)
                inst = template.generate(seed)
                if inst.fingerprint in fingerprints:
                    continue
                fingerprints.add(inst.fingerprint)
                seeds.append(seed)
                view = item_view(
                    inst,
                    instance_id=f"preview-{item.id}-{seed}",
                    topic=item.topic,
                    topic_label=labels.get(item.topic, item.topic),
                    time_limit_sec=int(item.time_limit_s or template.time_limit_s),
                )
                previews.append({**view, "seed": seed, "correct_answer": answer_payload(inst)})
                if len(previews) == PREVIEW_COUNT:
                    break
        else:
            fixture = fixtures.by_id("items", item.id) or {}
            if fixture.get("code") == item.code:
                previews = list(fixture.get("preview_variants") or [])
        detail["preview_variants"] = previews
        return detail

    async def retire(self, item_id: int) -> dict[str, Any]:
        item = await self._get(item_id)
        if item.status == "retired":
            raise AppError(409, "invalid_transition", "Шаблон уже выведен из оборота")
        before = item.status
        item.status = "retired"
        await write_audit(
            self.session,
            self.actor,
            "item_retired",
            "item",
            item.id,
            f"Шаблон «{item.title}» выведен из оборота",
            {"status": [before, "retired"]},
        )
        await self.session.commit()
        return await self.item(item_id)

    async def approve(self, item_id: int) -> dict[str, Any]:
        item = await self._get(item_id)
        if item.status != "draft":
            raise AppError(409, "invalid_transition", "Одобрить можно только черновик")
        item.status = "pilot"
        await write_audit(
            self.session,
            self.actor,
            "item_approved",
            "item",
            item.id,
            f"Черновик «{item.title}» одобрен: непроверочная задача (пилот)",
            {"status": ["draft", "pilot"]},
        )
        await self.session.commit()
        return await self.item(item_id)

    async def coverage(self) -> list[dict[str, Any]]:
        await ensure_bank(self.session)
        topics = (
            await self.session.execute(
                select(Topic.code, Topic.specialization, Topic.label).order_by(
                    Topic.specialization, Topic.code
                )
            )
        ).all()
        counts = await self.session.execute(
            select(Item.topic, Item.target_grade, Item.status, func.count())
            .where(Item.status.in_(("active", "pilot")))
            .group_by(Item.topic, Item.target_grade, Item.status)
        )
        by_key = {(t, g, s): n for t, g, s, n in counts.all()}
        return [
            {
                "specialization": spec,
                "topic": code,
                "topic_label": label,
                "grade": grade.value,
                "active": by_key.get((code, grade.value, "active"), 0),
                "pilot": by_key.get((code, grade.value, "pilot"), 0),
            }
            for code, spec, label in topics
            for grade in GradeCode
        ]

    async def recalibrate(self, min_responses: int | None) -> dict[str, Any]:
        n = min_responses or get_testing_settings().calibration_min_responses
        result = await journal.recalibrate(self.session, self.actor, min_responses=n)
        await self.session.commit()
        return {
            "started_at": result.started_at,
            "items_recalibrated": result.items_recalibrated,
            "pilot_promoted": result.pilot_promoted,
            "changes": result.changes,
        }

    async def leak_scan(self) -> dict[str, Any]:
        scan = await journal.leak_scan(self.session, self.actor)
        await self.session.commit()
        return {
            "scanned_at": scan.scanned_at,
            "answers_checked": scan.answers_checked,
            "items_checked": scan.items_checked,
            "retired": scan.retired,
            "flagged_candidates": scan.flagged_candidates,
        }
