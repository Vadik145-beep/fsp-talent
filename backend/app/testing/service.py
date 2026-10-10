"""Опрос, адаптивный тест, результат и грейд соискателя — на БД и движке `app.testing.engine`.

Как устроена сессия:
- при старте проверяется `can_attempt` (кулдауны) и что нет другой незавершённой сессии;
- состояние движка (`SessionState.to_dict()`) лежит в `test_sessions.engine_state["cat"]`;
- каждый показ — строка `test_answers`: шаблон, seed варианта, время выдачи по часам сервера,
  непрозрачный `instance_id` для клиента. Клиенту уходит только публичная часть варианта;
- ответ проверяет сервер; время = сейчас − время выдачи; после лимита ответ неверный;
- пилотные задачи не влияют на θ (это делает движок);
- при пересдаче шаблоны из прошлых попыток кандидата по этой специализации движок выдаёт
  в последнюю очередь (`avoid_ids`): сначала новые для кандидата, повтор — с новым seed;
- если на текущую задачу нет ответа дольше лимита + `abandon_after_min`, сессия брошена:
  текущая задача засчитывается неверной, сессия закрывается без смены грейда.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates.grading import attempts_of, last_grade_change
from app.candidates.models import CandidateProfile
from app.candidates.repository import CandidateDb, session_grade, session_record
from app.candidates.service import CandidateProfileService, declare
from app.catalog.clock import MSK, as_msk, now_msk
from app.catalog.models import Category, Specialization, Topic
from app.catalog.repository import CatalogDb
from app.common import fixtures
from app.common.fixtures import Record
from app.core.errors import AppError, not_found
from app.testing import journal
from app.testing.bank import engine_template, ensure_bank
from app.testing.engine import (
    GRADE_LABELS,
    GRADES,
    Attempt,
    BankItem,
    CATConfig,
    CATSession,
    GradeDecision,
    GradeThresholds,
    ItemBank,
    ItemInstance,
    can_attempt,
    check,
    decide,
    keep_grade_reason,
    leave_one_out_thetas,
    lower_test_needed,
    prior_for_grade,
)
from app.testing.formats import engine_response, item_view
from app.testing.models import GradeHistory, Item, TestAnswer, TestSession
from app.testing.schemas import AnswerSubmit, SurveySubmit, TestSessionCreate
from app.testing.settings import get_testing_settings
from app.testing.survey import evaluate

IN_ROTATION = ("active", "pilot")
ACTIONS = {
    "passed_claimed": "stay",
    "suggest_higher": "offer_higher",
    "suggest_lower": "offer_lower",
}


def _now() -> datetime:
    return now_msk()


def _elapsed(since: datetime, now: datetime) -> float:
    return max((now - since).total_seconds(), 0.0)


def _grade_idx(grade: str | None) -> int:
    return GRADES.index(grade) if grade else -1


def _assigned_grade(decision: GradeDecision, target: str, previous: str | None) -> str:
    """Грейд, который получает кандидат при подтверждённом тесте: заявленный,
    но не ниже действующего (принудительно не понижаем)."""
    granted = decision.granted_grade or target
    if previous and _grade_idx(granted) < _grade_idx(previous):
        return previous
    return granted


class TestingDbService:
    """Тест соискателя на БД. Коммит делает сервис (одна транзакция на запрос)."""

    __test__ = False

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_testing_settings()
        self.catalog = CatalogDb(session)
        self._topic_labels: dict[str, str] | None = None

    # ------------------------------------------------------------------ справочники

    async def topic_labels(self) -> dict[str, str]:
        if self._topic_labels is None:
            rows = await self.session.execute(select(Topic.code, Topic.label))
            self._topic_labels = {code: label for code, label in rows.all()}
        return self._topic_labels

    async def platform(self) -> Record:
        return await self.catalog.settings()

    async def thresholds(self, specialization: str) -> GradeThresholds:
        for row in (await self.platform()).get("grade_thresholds") or []:
            if row.get("specialization") == specialization:
                try:
                    return GradeThresholds(
                        float(row["junior_from"]),
                        float(row["middle_from"]),
                        float(row["senior_from"]),
                    )
                except (KeyError, TypeError, ValueError):
                    break
        return GradeThresholds()

    # ------------------------------------------------------------------ опрос

    def survey(self) -> list[Record]:
        return fixtures.all_records("survey_questions")

    async def submit_survey(self, body: SurveySubmit, candidate_id: int) -> dict[str, Any]:
        await ensure_bank(self.session)
        topics = (await self.session.execute(select(Topic.code, Topic.specialization))).all()
        by_spec: dict[str, list[str]] = {}
        for code, spec in topics:
            by_spec.setdefault(spec, []).append(code)
        covered = set(
            (
                await self.session.scalars(
                    select(Item.topic).where(Item.status == "active").distinct()
                )
            ).all()
        )
        spec_rows = await self.session.execute(select(Specialization.code, Specialization.label))
        labels: dict[str, str] = {code: label for code, label in spec_rows.all()}
        outcome = evaluate(
            self.survey(),
            [a.model_dump() for a in body.answers],
            spec_labels=labels,
            topics_by_spec=by_spec,
            covered_topics=covered,
        )
        self.session.add(
            GradeHistory(
                candidate_id=candidate_id,
                at=_now(),
                event="survey",
                specialization=outcome.specialization,
                comment=(
                    "Опрос рекомендовал специализацию "
                    f"{labels.get(outcome.specialization, outcome.specialization)}"
                ),
            )
        )
        await self.session.commit()
        return {
            "recommended_specialization": outcome.specialization,
            "alternatives": [{"specialization": s, "score": v} for s, v in outcome.scores[:3]],
            "suggested_grade": outcome.grade,
            "topics": outcome.topics,
            "explanation": outcome.explanation,
        }

    # ------------------------------------------------------------------ банк и движок

    async def _bank_items(self, specialization: str) -> list[Item]:
        rows = await self.session.scalars(
            select(Item)
            .where(Item.specialization == specialization, Item.status.in_(IN_ROTATION))
            .order_by(Item.id)
        )
        return [i for i in rows.all() if engine_template(i) is not None]

    @staticmethod
    def _bank_item(item: Item, status: str | None = None) -> BankItem:
        template = engine_template(item)
        limit = item.time_limit_s or (template.time_limit_s if template else None)
        return BankItem(
            item_id=item.code,
            topic=item.topic,
            a=item.a,
            b=item.b,
            status=status or item.status,
            time_limit_s=None if limit is None else float(limit),
        )

    def _config(self, stored: dict[str, Any] | None = None) -> CATConfig:
        s = self.settings
        cfg = stored or {}
        return CATConfig(
            se_target=float(cfg.get("se_target", s.cat_se_stop)),
            max_items=int(cfg.get("max_items", s.cat_max_items)),
            min_items=int(cfg.get("min_items", s.cat_min_items)),
            max_exposure_rate=float(cfg.get("max_exposure_rate", 1.0)),
        )

    async def _engine(
        self, ts: TestSession, pending: TestAnswer | None
    ) -> tuple[CATSession, dict[str, Item]]:
        """Восстановить сессию движка из БД."""
        state = ts.engine_state or {}
        items = await self._bank_items(ts.specialization)
        by_code = {i.code: i for i in items}
        bank = [self._bank_item(i) for i in items]
        if pending is not None:
            item = await self.session.get(Item, pending.item_id)
            assert item is not None
            by_code[item.code] = item
            if item.code not in {b.item_id for b in bank}:
                # шаблон вывели из оборота во время сессии — уже выданную задачу доводим
                bank.append(self._bank_item(item, "active" if pending.is_scored else "pilot"))
        cfg = state.get("config") or {}
        cat = CATSession.restore(
            ItemBank(bank),
            state["cat"],
            config=self._config(cfg),
            exposure_rates=cfg.get("exposure_rates") or None,
            avoid_ids=cfg.get("avoid_ids") or (),
        )
        return cat, by_code

    async def _past_item_codes(self, candidate_id: int, specialization: str) -> list[str]:
        """Шаблоны, которые кандидат уже видел в прошлых сессиях этой специализации."""
        rows = await self.session.scalars(
            select(Item.code)
            .join(TestAnswer, TestAnswer.item_id == Item.id)
            .join(TestSession, TestSession.id == TestAnswer.session_id)
            .where(
                TestSession.candidate_id == candidate_id,
                TestSession.specialization == specialization,
            )
            .distinct()
            .order_by(Item.code)
        )
        return list(rows.all())

    async def _pending(self, ts: TestSession) -> TestAnswer | None:
        pending: TestAnswer | None = await self.session.scalar(
            select(TestAnswer)
            .where(TestAnswer.session_id == ts.id, TestAnswer.answered_at.is_(None))
            .order_by(TestAnswer.position.desc())
            .limit(1)
        )
        return pending

    async def _issue(
        self, ts: TestSession, cat: CATSession, by_code: dict[str, Item]
    ) -> TestAnswer | None:
        """Выдать следующую задачу: запись показа (шаблон, seed, время сервера)."""
        nxt = cat.next_item()
        if nxt is None:
            return None
        item = by_code[nxt.item_id]
        position = (
            await self.session.scalar(
                select(TestAnswer.position)
                .where(TestAnswer.session_id == ts.id)
                .order_by(TestAnswer.position.desc())
                .limit(1)
            )
            or 0
        ) + 1
        answer = TestAnswer(
            session_id=ts.id,
            item_id=item.id,
            seed=secrets.randbelow(2**31),
            instance_id=secrets.token_hex(8),
            position=position,
            shown_at=_now(),
            is_scored=not nxt.is_pilot,
        )
        self.session.add(answer)
        item.exposures = (item.exposures or 0) + 1
        return answer

    def _instance(self, item: Item, answer: TestAnswer) -> ItemInstance:
        template = engine_template(item)
        assert template is not None
        return template.generate(answer.seed)

    async def _view(self, answer: TestAnswer, now: datetime) -> tuple[dict[str, Any], int]:
        item = await self.session.get(Item, answer.item_id)
        assert item is not None
        template = engine_template(item)
        assert template is not None
        limit = int(item.time_limit_s or template.time_limit_s)
        labels = await self.topic_labels()
        view = item_view(
            self._instance(item, answer),
            instance_id=answer.instance_id or "",
            topic=item.topic,
            topic_label=labels.get(item.topic, item.topic),
            time_limit_sec=limit,
        )
        left = max(int(limit - _elapsed(as_msk(answer.shown_at) or now, now)), 0)
        return view, left

    def _save_state(self, ts: TestSession, cat: CATSession, **extra: Any) -> None:
        state = dict(ts.engine_state or {})
        state["cat"] = cat.state.to_dict()
        state.update(extra)
        ts.engine_state = state  # новый dict — SQLAlchemy увидит изменение JSONB

    # ------------------------------------------------------------------ сессии

    async def _own(self, session_id: int, candidate_id: int, *, lock: bool = False) -> TestSession:
        stmt = select(TestSession).where(TestSession.id == session_id)
        if lock:
            stmt = stmt.with_for_update()
        ts = await self.session.scalar(stmt)
        if ts is None or ts.candidate_id != candidate_id:
            raise not_found("test_session", session_id)
        return ts

    async def _profile(self, candidate_id: int) -> CandidateProfile:
        profile = await self.session.get(CandidateProfile, candidate_id)
        if profile is None:
            raise not_found("candidate", candidate_id)
        return profile

    async def _expire_if_stale(self, ts: TestSession, now: datetime) -> bool:
        """Закрыть брошенную сессию. True — сессия только что истекла."""
        if ts.status != "in_progress" or "cat" not in (ts.engine_state or {}):
            return False
        pending = await self._pending(ts)
        if pending is None:
            return False
        item = await self.session.get(Item, pending.item_id)
        template = engine_template(item) if item else None
        limit = (item.time_limit_s if item else None) or (
            template.time_limit_s if template else 180
        )
        idle = _elapsed(as_msk(pending.shown_at) or now, now)
        if idle <= limit + self.settings.abandon_after_min * 60:
            return False
        cat, _ = await self._engine(ts, pending)
        assert item is not None
        record = cat.submit(item.code, False, idle)
        self._fill_answer(pending, record, None, now, cat)
        ts.items_answered += 1
        cat.abort("expired")
        await self._finalize(ts, cat, now, abandoned=True)
        return True

    async def _expire_candidate_sessions(self, candidate_id: int, now: datetime) -> None:
        rows = await self.session.scalars(
            select(TestSession)
            .where(TestSession.candidate_id == candidate_id, TestSession.status == "in_progress")
            .with_for_update()
        )
        changed = False
        for ts in rows.all():
            changed |= await self._expire_if_stale(ts, now)
        if changed:
            await self.session.commit()

    async def sessions(self, candidate_id: int) -> list[dict[str, Any]]:
        await self._expire_candidate_sessions(candidate_id, _now())
        rows = await CandidateDb(self.session).test_sessions(candidate_id)
        return [session_record(s) for s in rows]

    async def _attempts(self, candidate_id: int, specialization: str) -> list[Attempt]:
        sessions = [
            s
            for s in await CandidateDb(self.session).test_sessions(candidate_id)
            if s.specialization == specialization
        ]
        # брошенная сессия считается неудачной попыткой: иначе можно подсмотреть задачи и выйти
        abandoned = [
            Attempt(on=as_msk(s.finished_at).date(), target_grade=s.target_grade, passed=False)  # type: ignore[union-attr]
            for s in sessions
            if s.status == "abandoned" and s.finished_at is not None
        ]
        return attempts_of(sessions) + abandoned

    async def create(self, body: TestSessionCreate, candidate_id: int) -> dict[str, Any]:
        now = _now()
        await ensure_bank(self.session)
        profile = await self._profile(candidate_id)
        await self._expire_candidate_sessions(candidate_id, now)
        busy = await self.session.scalar(
            select(TestSession.id).where(
                TestSession.candidate_id == candidate_id, TestSession.status == "in_progress"
            )
        )
        if busy is not None:
            raise AppError(
                409,
                "session_in_progress",
                "Сначала завершите начатый тест",
                {"session_id": busy},
            )
        spec, target, kind = str(body.specialization), str(body.target_grade), str(body.kind)
        current = profile.grade if profile.specialization == spec else None
        if kind == "lower" and not (current and _grade_idx(target) < _grade_idx(current)):
            raise AppError(
                422, "invalid_kind", "Тест «ниже» — только на грейд ниже текущего", {"kind": kind}
            )
        if kind == "higher" and not (current and _grade_idx(target) > _grade_idx(current)):
            raise AppError(
                422, "invalid_kind", "Тест «выше» — только на грейд выше текущего", {"kind": kind}
            )
        platform = await self.platform()
        history = await CandidateDb(self.session).grade_history(candidate_id)
        changed_at = last_grade_change(history)
        verdict = can_attempt(
            target,
            now.date(),
            current_grade=current,
            last_grade_change=changed_at.date() if changed_at else None,
            attempts=await self._attempts(candidate_id, spec),
            change_cooldown_days=int(platform.get("grade_change_cooldown_days", 90)),
            retry_cooldown_days=int(platform.get("retry_cooldown_days", 30)),
        )
        if not verdict.allowed:
            available = verdict.available_from
            raise AppError(
                409,
                "cooldown_active",
                verdict.reason,
                {
                    "reason_code": verdict.code,
                    "available_at": None
                    if available is None
                    else datetime.combine(available, datetime.min.time(), MSK).isoformat(),
                },
            )
        items = await self._bank_items(spec)
        if not any(i.status == "active" for i in items):
            raise AppError(409, "bank_empty", "Для специализации пока нет задач")
        active = sum(1 for i in items if i.status == "active")
        cfg: dict[str, Any] = {
            "se_target": self.settings.cat_se_stop,
            "max_items": self.settings.cat_max_items,
            "min_items": self.settings.cat_min_items,
            "max_exposure_rate": 1.0,
        }
        if active >= self.settings.exposure_min_bank:
            cfg["max_exposure_rate"] = float(platform.get("exposure_max_share", 0.25))
            cfg["exposure_rates"] = await journal.exposure_rates(self.session, spec)
        # пересдача: прошлые задачи кандидата — в последнюю очередь (не запрет)
        if past := await self._past_item_codes(candidate_id, spec):
            cfg["avoid_ids"] = past
        cat = CATSession(
            ItemBank(self._bank_item(i) for i in items),
            target,
            config=self._config(cfg),
            seed=secrets.randbelow(2**31),
            exposure_rates=cfg.get("exposure_rates"),
            avoid_ids=cfg.get("avoid_ids") or (),
        )
        ts = TestSession(
            candidate_id=candidate_id,
            specialization=spec,
            target_grade=target,
            kind=kind,
            status="in_progress",
            started_at=now,
            items_answered=0,
            max_items=cfg["max_items"],
            topic_scores=[],
            engine_state={},
        )
        if kind == "placement" and profile.grade is None:
            # тест на заявленный грейд: до результата — «грейд не подтверждён» (FTT.4)
            declare(profile, spec, target)
        self.session.add(ts)
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            raise AppError(409, "session_in_progress", "Сначала завершите начатый тест") from None
        await self._issue(ts, cat, {i.code: i for i in items})
        self._save_state(ts, cat, config=cfg)
        await self.session.commit()
        return await self.state(ts)

    async def _adopt_legacy(self, ts: TestSession) -> None:
        """Незавершённая сессия из демо-данных без состояния движка: подхватить движком.

        Ответы из фикстуры не имеют записей — на θ они не влияют, счётчик продолжается.
        """
        items = await self._bank_items(ts.specialization)
        if not items:
            return
        cfg = {
            "se_target": self.settings.cat_se_stop,
            "max_items": self.settings.cat_max_items,
            "min_items": self.settings.cat_min_items,
            "max_exposure_rate": 1.0,
        }
        cat = CATSession(
            ItemBank(self._bank_item(i) for i in items),
            ts.target_grade,
            config=self._config(cfg),
            seed=secrets.randbelow(2**31),
        )
        await self._issue(ts, cat, {i.code: i for i in items})
        self._save_state(ts, cat, config=cfg, answered_offset=ts.items_answered)
        await self.session.commit()

    async def state(self, ts: TestSession) -> dict[str, Any]:
        now = _now()
        view, left = None, None
        if ts.status == "in_progress":
            pending = await self._pending(ts)
            if pending is not None:
                view, left = await self._view(pending, now)
        number = ts.items_answered + 1 if view is not None else ts.items_answered
        return {
            "session": session_record(ts),
            "current_item": view,
            "item_number": number,
            "time_left_sec": left,
        }

    async def get_state(self, session_id: int, candidate_id: int) -> dict[str, Any]:
        ts = await self._own(session_id, candidate_id, lock=True)
        if ts.status == "in_progress" and "cat" not in (ts.engine_state or {}):
            await self._adopt_legacy(ts)
        elif await self._expire_if_stale(ts, _now()):
            await self.session.commit()
        return await self.state(ts)

    def _fill_answer(
        self,
        row: TestAnswer,
        record: Any,
        payload: dict[str, Any] | None,
        now: datetime,
        cat: CATSession,
    ) -> None:
        est = cat.estimate()
        row.answered_at = now
        row.answer = payload
        row.correct = record.correct
        row.timed_out = record.timed_out
        row.response_time_ms = None if record.elapsed_s is None else int(record.elapsed_s * 1000)
        row.theta_after = round(est.theta, 4)
        row.se_after = round(est.se, 4)

    async def answer(
        self, session_id: int, candidate_id: int, body: AnswerSubmit
    ) -> dict[str, Any]:
        now = _now()
        ts = await self._own(session_id, candidate_id, lock=True)
        if ts.status == "in_progress" and "cat" not in (ts.engine_state or {}):
            await self._adopt_legacy(ts)
        if await self._expire_if_stale(ts, now):
            await self.session.commit()
        if ts.status != "in_progress":
            raise AppError(409, "session_finished", "Тест уже завершён")
        pending = await self._pending(ts)
        if pending is None or body.instance_id != pending.instance_id:
            raise AppError(409, "wrong_item", "Ответ не на текущую задачу")
        cat, by_code = await self._engine(ts, pending)
        item = await self.session.get(Item, pending.item_id)
        assert item is not None
        payload = body.answer.model_dump()
        inst = self._instance(item, pending)
        ok = check(inst, engine_response(inst, payload))
        elapsed = _elapsed(as_msk(pending.shown_at) or now, now)
        record = cat.submit(item.code, ok, elapsed)
        self._fill_answer(pending, record, payload, now, cat)
        if record.correct:
            item.correct_count = (item.correct_count or 0) + 1
        ts.items_answered += 1
        nxt = None if cat.finished else await self._issue(ts, cat, by_code)
        if cat.finished:
            await self._finalize(ts, cat, now)
        else:
            self._save_state(ts, cat)
        await self.session.flush()
        next_view = None
        if nxt is not None:
            next_view, _ = await self._view(nxt, now)
        await self.session.commit()
        return {
            "session_id": ts.id,
            "answered": ts.items_answered,
            "finished": ts.status != "in_progress",
            "next_item": next_view,
            "time_expired": record.timed_out,
        }

    # ------------------------------------------------------------------ итог

    async def _finalize(
        self, ts: TestSession, cat: CATSession, now: datetime, *, abandoned: bool = False
    ) -> None:
        """Итог сессии: решение по грейду, история, профиль, журнал для детектора."""
        res = cat.result()
        await self.session.flush()
        thresholds = await self.thresholds(ts.specialization)
        profile = await self._profile(ts.candidate_id)
        same_spec = profile.specialization == ts.specialization
        current = profile.grade if same_spec else None
        decision = decide(
            res.theta, res.se, ts.target_grade, current_grade=current, thresholds=thresholds
        )
        passed = decision.outcome != "suggest_lower" and not abandoned
        # Подтверждён — грейд сессии = присвоенный (его видит работодатель); уровень по θ
        # хранится отдельно (estimated_grade) и идёт только в рекомендацию.
        assigned = _assigned_grade(decision, ts.target_grade, current) if passed else None
        labels = await self.topic_labels()
        topic_scores = [
            {
                "topic": t.topic,
                "label": labels.get(t.topic, t.topic),
                "score": round(t.n_correct / t.n, 2) if t.n else 0.0,
                "level": t.level,
            }
            for t in res.topics
        ]
        await self._write_journal(ts, cat, res.theta)
        ts.status = "abandoned" if abandoned else "finished"
        ts.finished_at = now
        ts.theta = round(res.theta, 4)
        ts.se = round(res.se, 4)
        ts.result_grade = assigned or decision.estimated_grade
        ts.passed = passed
        ts.topic_scores = topic_scores
        self._save_state(
            ts,
            cat,
            ci_low=round(res.ci_low, 4),
            ci_high=round(res.ci_high, 4),
            decision={
                "outcome": "abandoned" if abandoned else decision.outcome,
                "granted_grade": assigned if passed else current,
                "estimated_grade": decision.estimated_grade,
                "suggested_grade": None if abandoned else decision.suggested_grade,
                "reason": "Тест не завершён: истекло время ответа."
                if abandoned
                else decision.reason,
                "n_scored": res.n_scored,
                "n_pilot": res.n_pilot,
                "n_timed_out": res.n_timed_out,
                "stop_reason": res.stop_reason,
            },
        )
        await self._apply_grade(ts, profile, decision, assigned, abandoned, now, topic_scores)
        await self.session.flush()
        await journal.check_session_anomaly(self.session, ts.id)
        every = self.settings.leak_scan_every
        if every > 0 and (await journal.finished_engine_sessions(self.session)) % every == 0:
            await journal.leak_scan(self.session, None, with_candidates=False)

    async def _write_journal(self, ts: TestSession, cat: CATSession, theta: float) -> None:
        """θ без каждой задачи (для детектора утечек и калибровки)."""
        records = cat.state.records
        scored = [r for r in records if r.scored]
        prior_mean, prior_sd = prior_for_grade(ts.target_grade, cat.config.prior_sd)
        loo = leave_one_out_thetas([(r.a, r.b, r.correct) for r in scored], prior_mean, prior_sd)
        theta_by_code = {r.item_id: th for r, th in zip(scored, loo, strict=True)}
        rows = await self.session.execute(
            select(TestAnswer, Item.code)
            .join(Item, Item.id == TestAnswer.item_id)
            .where(TestAnswer.session_id == ts.id, TestAnswer.answered_at.is_not(None))
        )
        for answer, code in rows.all():
            answer.theta_loo = round(theta_by_code.get(code, theta), 4)

    async def _apply_grade(
        self,
        ts: TestSession,
        profile: CandidateProfile,
        decision: GradeDecision,
        assigned: str | None,
        abandoned: bool,
        now: datetime,
        topic_scores: list[dict[str, Any]],
    ) -> None:
        spec = ts.specialization
        same_spec = profile.specialization == spec
        previous = profile.grade if same_spec else None
        theta_txt = f"θ = {ts.theta:.2f}"
        history: list[GradeHistory] = []

        def event(name: str, comment: str, grade_from: str | None, grade_to: str | None) -> None:
            history.append(
                GradeHistory(
                    candidate_id=ts.candidate_id,
                    at=now,
                    event=name,
                    specialization=spec,
                    grade_from=grade_from,
                    grade_to=grade_to,
                    test_session_id=ts.id,
                    comment=comment,
                )
            )

        profile.last_test_at = now
        if abandoned:
            event(
                "test_failed",
                f"Тест на {GRADE_LABELS[ts.target_grade]} не завершён: истекло время. {theta_txt}",
                previous,
                None,
            )
        elif assigned is None:
            keep = f" Грейд {GRADE_LABELS[previous]} сохраняется." if previous else ""
            event(
                "test_failed",
                f"Грейд {GRADE_LABELS[ts.target_grade]} не подтверждён, {theta_txt}.{keep}",
                previous,
                None,
            )
            if decision.suggested_grade:
                event(
                    "offer_lower",
                    f"Предложен тест на грейд {GRADE_LABELS[decision.suggested_grade]}",
                    previous,
                    decision.suggested_grade,
                )
        else:
            granted = assigned
            event(
                "test_passed",
                f"Подтверждён грейд {GRADE_LABELS[ts.target_grade]}, {theta_txt}",
                previous,
                granted,
            )
            category = f"{spec}:{granted}"
            if await self.session.get(Category, category) is None:
                category = profile.category or category
            if granted != profile.grade or not same_spec:
                label = await self.session.scalar(
                    select(Category.label).where(Category.code == category)
                )
                event(
                    "grade_changed",
                    f"Присвоена категория {label or category}",
                    previous,
                    granted,
                )
                if previous is not None:
                    profile.grade_changed_at = now
            if decision.outcome == "suggest_higher" and decision.suggested_grade:
                event(
                    "offer_higher",
                    f"Предложен тест на грейд {GRADE_LABELS[decision.suggested_grade]}",
                    granted,
                    decision.suggested_grade,
                )
            profile.specialization = spec
            profile.grade = granted
            profile.category = category
            profile.theta = ts.theta
            profile.theta_se = ts.se
            profile.topic_scores = topic_scores
        self.session.add_all(history)

    async def result(self, session_id: int, candidate_id: int) -> dict[str, Any]:
        ts = await self._own(session_id, candidate_id, lock=True)
        if await self._expire_if_stale(ts, _now()):
            await self.session.commit()
        if ts.status == "in_progress" or ts.theta is None or ts.se is None:
            raise AppError(409, "session_not_finished", "Тест ещё не завершён")
        state = ts.engine_state or {}
        stored = state.get("decision") or {}
        thresholds = await self.thresholds(ts.specialization)
        if stored:
            outcome = stored["outcome"]
            suggested = stored.get("suggested_grade")
            message = stored.get("reason", "")
        else:  # сессии из демо-данных: решение восстанавливаем по θ и SE
            d = decide(ts.theta, ts.se, ts.target_grade, thresholds=thresholds)
            outcome, suggested, message = d.outcome, d.suggested_grade, d.reason
        se = ts.se
        ci_low = state.get("ci_low", ts.theta - 1.645 * se)
        ci_high = state.get("ci_high", ts.theta + 1.645 * se)
        # Подтверждён — присвоенный грейд (как в профиле у работодателя), иначе — уровень по θ.
        result_grade = session_grade(ts) or thresholds.grade_for(ts.theta)
        category = f"{ts.specialization}:{result_grade}"
        label = await self.session.scalar(select(Category.label).where(Category.code == category))
        action = ACTIONS.get(outcome, "retry_later")
        available_at = None
        kept = stored.get("granted_grade")
        if outcome == "suggest_lower" and kept and not lower_test_needed(kept, suggested):
            # свой грейд не ниже предлагаемого уже есть (и для сессий до этого правила)
            grade = await CandidateProfileService(self.session).grade(candidate_id)
            days = int(grade.get("retry_cooldown_days") or 30)
            action, suggested = "retry_later", None
            message = keep_grade_reason(ts.target_grade, kept, days)
        if action in ("offer_lower", "offer_higher") and suggested:
            grade = await CandidateProfileService(self.session).grade(candidate_id)
            for option in (grade.get("lower"), grade.get("higher")):
                if option and option["target_grade"] == suggested and not option["allowed"]:
                    available_at = option["available_at"]
        scores = list(ts.topic_scores or [])
        return {
            "session_id": ts.id,
            "specialization": ts.specialization,
            "target_grade": ts.target_grade,
            "result_grade": result_grade,
            "category": category,
            "category_label": label or category,
            "theta": ts.theta,
            "se": se,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "passed": bool(ts.passed),
            "items_answered": ts.items_answered,
            "finished_at": as_msk(ts.finished_at) or _now(),
            "topic_scores": scores,
            "strong_topics": [t["label"] for t in scores if t.get("level") == "strong"],
            "weak_topics": [t["label"] for t in scores if t.get("level") == "weak"],
            "recommendation": {
                "action": action,
                "message": message,
                "available_at": available_at,
                "target_grade": suggested,
            },
            "outcome": outcome,
        }

    # ------------------------------------------------------------------ грейд

    async def grade_status(self, candidate_id: int) -> dict[str, Any]:
        """Тот же статус, что `GET /candidates/me/grade` (правила — в сервисе кандидатов)."""
        await self._expire_candidate_sessions(candidate_id, _now())
        return await CandidateProfileService(self.session).grade(candidate_id)
