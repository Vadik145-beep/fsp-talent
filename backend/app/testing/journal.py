"""Журнал ответов: доли показов, детектор утечек, аномалии кандидатов, калибровка (T4.7, T4.9).

Источник — таблица `test_answers`: каждый показ варианта (шаблон + seed), время по часам
сервера, верно ли, θ кандидата без этой задачи (`theta_loo`, пишется при завершении сессии).
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import distinct, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.audit import write_audit
from app.catalog.clock import now_msk
from app.core.errors import AppError
from app.core.security import CurrentUser
from app.testing.engine import (
    CandidateResponse,
    ItemObservation,
    activation_check,
    calibrate_item,
    candidate_anomalies,
    detect_leaks,
)
from app.testing.models import Item, ItemParamsLog, TestAnswer, TestSession

IN_ROTATION = ("active", "pilot")
RECALIBRATION_LOCK = 3_100_409  # ключ advisory-блокировки пересчёта калибровки


async def exposure_rates(session: AsyncSession, specialization: str) -> dict[str, float]:
    """Доля сессий специализации, в которых показан шаблон: код шаблона → доля."""
    base = (
        select(TestAnswer.item_id, TestAnswer.session_id)
        .join(TestSession, TestSession.id == TestAnswer.session_id)
        .where(TestSession.specialization == specialization)
    ).subquery()
    total = await session.scalar(select(func.count(distinct(base.c.session_id))))
    if not total:
        return {}
    rows = await session.execute(
        select(Item.code, func.count(distinct(base.c.session_id)))
        .join(base, base.c.item_id == Item.id)
        .group_by(Item.code)
    )
    return {code: n / total for code, n in rows.all()}


@dataclass
class AnswerRow:
    item_id: int
    code: str
    session_id: int
    candidate_id: int
    a: float
    b: float
    theta_loo: float
    correct: bool
    elapsed_s: float | None
    is_scored: bool


async def answer_rows(session: AsyncSession, *, in_rotation_only: bool = True) -> list[AnswerRow]:
    """Ответы с известной θ без задачи, в хронологическом порядке."""
    stmt = (
        select(
            TestAnswer.item_id,
            Item.code,
            TestAnswer.session_id,
            TestSession.candidate_id,
            Item.a,
            Item.b,
            TestAnswer.theta_loo,
            TestAnswer.correct,
            TestAnswer.response_time_ms,
            TestAnswer.is_scored,
        )
        .join(Item, Item.id == TestAnswer.item_id)
        .join(TestSession, TestSession.id == TestAnswer.session_id)
        .where(TestAnswer.theta_loo.is_not(None), TestAnswer.answered_at.is_not(None))
        .order_by(TestAnswer.answered_at, TestAnswer.id)
    )
    if in_rotation_only:
        stmt = stmt.where(Item.status.in_(IN_ROTATION))
    rows = await session.execute(stmt)
    return [
        AnswerRow(
            item_id=r[0],
            code=r[1],
            session_id=r[2],
            candidate_id=r[3],
            a=r[4],
            b=r[5],
            theta_loo=r[6],
            correct=bool(r[7]),
            elapsed_s=None if r[8] is None else r[8] / 1000,
            is_scored=bool(r[9]),
        )
        for r in rows.all()
    ]


@dataclass
class LeakScan:
    scanned_at: Any
    answers_checked: int = 0
    items_checked: int = 0
    retired: list[dict[str, Any]] = field(default_factory=list)
    flagged_candidates: list[dict[str, Any]] = field(default_factory=list)


def _typical_times(rows: list[AnswerRow]) -> dict[int, float]:
    times: dict[int, list[float]] = defaultdict(list)
    for r in rows:
        if r.elapsed_s is not None:
            times[r.item_id].append(r.elapsed_s)
    return {k: float(statistics.median(v)) for k, v in times.items()}


def _session_anomaly(rows: list[AnswerRow], typical: dict[int, float]) -> dict[str, Any] | None:
    scored = [r for r in rows if r.is_scored]
    if not scored:
        return None
    report = candidate_anomalies(
        [
            CandidateResponse(
                item_id=str(r.item_id),
                a=r.a,
                b=r.b,
                correct=r.correct,
                elapsed_s=r.elapsed_s,
                typical_time_s=typical.get(r.item_id),
            )
            for r in scored
        ]
    )
    if not report.flagged:
        return None
    return {
        "candidate_id": scored[0].candidate_id,
        "session_id": scored[0].session_id,
        "suspicious_item_ids": [int(i) for i in report.suspicious_item_ids],
        "lz": round(report.lz, 3),
        "reasons": list(report.reasons),
    }


async def check_session_anomaly(session: AsyncSession, session_id: int) -> dict[str, Any] | None:
    """Аномалии времени ответов одной сессии; при флаге — запись в журнал (повод проверить)."""
    rows = await answer_rows(session, in_rotation_only=False)
    flag = _session_anomaly([r for r in rows if r.session_id == session_id], _typical_times(rows))
    if flag:
        await write_audit(
            session,
            None,
            "candidate_anomaly",
            "candidate",
            flag["candidate_id"],
            "Подозрительно быстрые верные ответы на сложные задачи — нужна ручная проверка",
            flag,
        )
    return flag


async def leak_scan(
    session: AsyncSession, actor: CurrentUser | None, *, with_candidates: bool = True
) -> LeakScan:
    """Детектор утечек по журналу: помеченные шаблоны выводятся из оборота (коммит — снаружи)."""
    rows = await answer_rows(session)
    scan = LeakScan(scanned_at=now_msk(), answers_checked=len(rows))
    items = {
        i.code: i for i in await session.scalars(select(Item).where(Item.status.in_(IN_ROTATION)))
    }
    params = {code: (i.a, i.b) for code, i in items.items()}
    reports = detect_leaks(
        (ItemObservation(r.code, r.theta_loo, r.correct, r.elapsed_s) for r in rows), params
    )
    scan.items_checked = len(reports)
    for rep in reports:
        item = items[rep.item_id]
        item.leak_score = round(max(rep.z, 0.0), 3)
        if not rep.flagged:
            continue
        item.leak_flag = True
        item.status = "retired"
        entry = {
            "item_id": item.id,
            "code": item.code,
            "title": item.title,
            "n": rep.n,
            "observed_rate": round(rep.observed_rate, 3),
            "expected_rate": round(rep.expected_rate, 3),
            "z": round(rep.z, 3),
            "fast_correct": rep.fast_correct,
            "reasons": list(rep.reasons),
        }
        scan.retired.append(entry)
        await write_audit(
            session,
            actor,
            "item_leak_retired",
            "item",
            item.id,
            f"Возможная утечка: шаблон «{item.title}» выведен из оборота",
            entry,
        )
    if with_candidates:
        typical = _typical_times(rows)
        by_session: dict[int, list[AnswerRow]] = defaultdict(list)
        for r in rows:
            by_session[r.session_id].append(r)
        for sid in sorted(by_session):
            flag = _session_anomaly(by_session[sid], typical)
            if flag:
                scan.flagged_candidates.append(flag)
    await session.flush()
    return scan


async def finished_engine_sessions(session: AsyncSession) -> int:
    """Сколько сессий движка завершено (для автозапуска детектора каждые N сессий)."""
    return (
        await session.scalar(
            select(func.count())
            .select_from(TestSession)
            .where(TestSession.status != "in_progress", TestSession.engine_state.has_key("cat"))
        )
        or 0
    )


@dataclass
class Recalibration:
    started_at: Any
    items_recalibrated: int = 0
    pilot_promoted: int = 0
    changes: list[dict[str, Any]] = field(default_factory=list)


async def recalibrate(
    session: AsyncSession, actor: CurrentUser | None, *, min_responses: int
) -> Recalibration:
    """Пересчёт a, b по накопленным ответам; pilot → active по правилу активации."""
    locked = await session.scalar(
        text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": RECALIBRATION_LOCK}
    )
    if not locked:
        raise AppError(409, "recalibration_running", "Пересчёт уже идёт")
    result = Recalibration(started_at=now_msk())
    rows = await answer_rows(session)
    by_item: dict[int, list[AnswerRow]] = defaultdict(list)
    for r in rows:
        by_item[r.item_id].append(r)
    items = {
        i.id: i
        for i in await session.scalars(select(Item).where(Item.id.in_(list(by_item) or [0])))
    }
    for item_id, answers in sorted(by_item.items()):
        item = items[item_id]
        if len(answers) < min_responses:
            continue
        calib = calibrate_item(
            [r.theta_loo for r in answers], [r.correct for r in answers], a0=item.a, b0=item.b
        )
        if not calib.converged:
            continue
        a_new, b_new = round(calib.a, 3), round(calib.b, 3)
        reason = "recalibration"
        if item.status == "pilot":
            ok, _why = activation_check(calib)
            if ok:
                item.status = "active"
                result.pilot_promoted += 1
                reason = "activation"
        session.add(
            ItemParamsLog(
                item_id=item.id,
                a_before=item.a,
                a_after=a_new,
                b_before=item.b,
                b_after=b_new,
                responses_count=len(answers),
                reason=reason,
            )
        )
        result.changes.append(
            {
                "item_id": item.id,
                "a_before": item.a,
                "a_after": a_new,
                "b_before": item.b,
                "b_after": b_new,
            }
        )
        item.a, item.b = a_new, b_new
        result.items_recalibrated += 1
    await write_audit(
        session,
        actor,
        "items_recalibrated",
        "item",
        None,
        f"Пересчёт калибровки: обновлено {result.items_recalibrated}, "
        f"переведено в рабочие {result.pilot_promoted}",
        {"min_responses": min_responses},
    )
    await session.flush()
    return result
