"""Адаптивная тестовая сессия (CAT).

Как выбирается следующая задача:
1. Текущая оценка θ — EAP по уже данным проверочным ответам; априор — по заявленному грейду.
2. Из доступных задач убираются: уже показанные, жёстко исключённые вызывающим кодом
   (`exclude_ids`), задачи с превышенной долей показов (контроль экспозиции) и темы,
   которых в тесте уже слишком много (баланс тем).
3. Каждой задаче считается информация Фишера в текущей θ, поделённая на (1 + k·штраф),
   где k — сколько задач этой темы уже было.
4. Прошлые задачи — в последнюю очередь (`avoid_ids`, например шаблоны из прошлых попыток
   кандидата): если среди новых для кандидата задач есть достаточно информативные
   (не меньше `repeat_info_ratio` от лучшей), выбор идёт только среди них; иначе — среди
   всех, и прошлая задача выдаётся заново (с новыми параметрами генератора). Это
   предпочтение, а не запрет: тест не обрывается раньше, даже если банк маленький.
5. Берётся случайная задача из топ-5 по этой величине (randomesque): у двух кандидатов
   с одинаковыми ответами наборы задач всё равно расходятся.

В 1–2 заранее выбранные позиции (в первых min_items показах) вставляются пилотные
(непроверочные) задачи: кандидат их не отличает, но на θ они не влияют — ответы идут
только в калибровку.

Остановка: SE < 0,35 (не раньше 6 проверочных задач) или 15 проверочных задач.
Время на задачу считает сервер и передаёт в `submit`; ответ после лимита — неверный.

Сессия не держит скрытого состояния: всё, что нужно для продолжения, лежит в
`SessionState` (сериализуется в JSON), а случайность выводится из seed и номера шага.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from .constants import check_grade
from .irt import ThetaEstimate, estimate_theta, information, prior_for_grade, prob
from .templates import ItemTemplate, TemplateStatus

SCORED_STATUS = "active"
PILOT_STATUS = "pilot"


@dataclass(frozen=True, slots=True)
class BankItem:
    """Задача банка глазами CAT: только то, что нужно для выбора (без генерации)."""

    item_id: str
    topic: str
    a: float
    b: float
    status: str = SCORED_STATUS  # "active" — проверочная, "pilot" — непроверочная
    time_limit_s: float | None = None

    @property
    def is_pilot(self) -> bool:
        return self.status == PILOT_STATUS

    @classmethod
    def from_template(cls, t: ItemTemplate) -> BankItem:
        return cls(
            item_id=t.id,
            topic=t.topic,
            a=t.a,
            b=t.b,
            status=str(t.status),
            time_limit_s=float(t.time_limit_s),
        )


class ItemBank:
    """Банк задач для CAT: массивы a, b, темы. Черновики и выведенные задачи отбрасываются."""

    def __init__(self, items: Iterable[BankItem]) -> None:
        kept = [i for i in items if i.status in (SCORED_STATUS, PILOT_STATUS)]
        ids = [i.item_id for i in kept]
        if len(set(ids)) != len(ids):
            raise ValueError("В банке повторяются item_id")
        self.items: tuple[BankItem, ...] = tuple(kept)
        self._index = {item.item_id: n for n, item in enumerate(self.items)}
        self.a = np.array([i.a for i in self.items], dtype=np.float64)
        self.b = np.array([i.b for i in self.items], dtype=np.float64)
        self.pilot = np.array([i.is_pilot for i in self.items], dtype=bool)
        self.topic_names: tuple[str, ...] = tuple(dict.fromkeys(i.topic for i in self.items))
        topic_pos = {t: n for n, t in enumerate(self.topic_names)}
        self.topic_idx = np.array([topic_pos[i.topic] for i in self.items], dtype=np.int64)

    @classmethod
    def from_templates(cls, templates: Iterable[ItemTemplate]) -> ItemBank:
        return cls(
            BankItem.from_template(t)
            for t in templates
            if t.status in (TemplateStatus.ACTIVE, TemplateStatus.PILOT)
        )

    def __len__(self) -> int:
        return len(self.items)

    def __contains__(self, item_id: object) -> bool:
        return item_id in self._index

    def position(self, item_id: str) -> int | None:
        return self._index.get(item_id)

    def get(self, item_id: str) -> BankItem | None:
        pos = self._index.get(item_id)
        return None if pos is None else self.items[pos]


@dataclass(frozen=True)
class CATConfig:
    se_target: float = 0.35
    max_items: int = 15  # максимум проверочных задач
    min_items: int = 6  # минимум проверочных задач до остановки по SE
    top_k: int = 5  # randomesque: случайная из топ-k по информации
    max_exposure_rate: float = 0.25  # задача не выдаётся, если её показали > 25% сессий
    max_topic_share: float = 0.34  # не больше ~трети теста из одной темы
    topic_penalty: float = 0.1  # мягкий штраф за повтор темы
    # прошлые задачи кандидата (avoid_ids) уступают новым, если у новых информация
    # не ниже этой доли от лучшей доступной; иначе выбираются наравне
    repeat_info_ratio: float = 0.25
    pilot_min: int = 1
    pilot_max: int = 2
    time_limit_s: float = 180.0  # если у задачи свой лимит не задан
    prior_sd: float = 1.0
    ci_z: float = 1.645  # 90% доверительный интервал

    def __post_init__(self) -> None:
        if not 1 <= self.min_items <= self.max_items:
            raise ValueError("Нужно 1 ≤ min_items ≤ max_items")
        if not 0 <= self.pilot_min <= self.pilot_max < self.min_items:
            raise ValueError("Нужно 0 ≤ pilot_min ≤ pilot_max < min_items")
        if self.top_k < 1:
            raise ValueError("top_k ≥ 1")
        if not 0 <= self.repeat_info_ratio <= 1:
            raise ValueError("Нужно 0 ≤ repeat_info_ratio ≤ 1")

    @property
    def max_per_topic(self) -> int:
        return max(2, math.ceil(self.max_topic_share * self.max_items))


@dataclass(frozen=True, slots=True)
class AnswerRecord:
    item_id: str
    topic: str
    a: float
    b: float
    scored: bool  # False — пилотная задача, на θ не влияет
    correct: bool  # итог с учётом лимита времени
    raw_correct: bool  # что прислал проверяющий код
    elapsed_s: float | None = None
    timed_out: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> AnswerRecord:
        return cls(
            item_id=str(d["item_id"]),
            topic=str(d["topic"]),
            a=float(d["a"]),
            b=float(d["b"]),
            scored=bool(d["scored"]),
            correct=bool(d["correct"]),
            raw_correct=bool(d.get("raw_correct", d["correct"])),
            elapsed_s=None if d.get("elapsed_s") is None else float(d["elapsed_s"]),
            timed_out=bool(d.get("timed_out", False)),
        )


@dataclass
class SessionState:
    """Всё состояние сессии. Хранится в БД как JSON между запросами."""

    claimed_grade: str
    seed: int
    pilot_slots: tuple[int, ...] = ()
    records: list[AnswerRecord] = field(default_factory=list)
    pending_item_id: str | None = None
    finished: bool = False
    stop_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "claimed_grade": self.claimed_grade,
            "seed": self.seed,
            "pilot_slots": list(self.pilot_slots),
            "records": [r.to_dict() for r in self.records],
            "pending_item_id": self.pending_item_id,
            "finished": self.finished,
            "stop_reason": self.stop_reason,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> SessionState:
        return cls(
            claimed_grade=str(d["claimed_grade"]),
            seed=int(d["seed"]),
            pilot_slots=tuple(int(x) for x in d.get("pilot_slots", ())),
            records=[AnswerRecord.from_dict(r) for r in d.get("records", ())],
            pending_item_id=d.get("pending_item_id"),
            finished=bool(d.get("finished", False)),
            stop_reason=d.get("stop_reason"),
        )


@dataclass(frozen=True, slots=True)
class TopicStat:
    """Разбор по теме: сколько задач, сколько верно и сколько ожидалось при итоговой θ."""

    topic: str
    n: int
    n_correct: int
    expected_correct: float
    level: str  # "strong" / "ok" / "weak"


@dataclass(frozen=True)
class CATResult:
    claimed_grade: str
    theta: float
    se: float
    ci_low: float
    ci_high: float
    n_scored: int
    n_pilot: int
    n_timed_out: int
    finished: bool
    stop_reason: str | None
    topics: tuple[TopicStat, ...]
    records: tuple[AnswerRecord, ...]


class SessionFinishedError(RuntimeError):
    """Сессия уже завершена."""


class CATSession:
    """Адаптивная сессия. Время и проверку ответа делает вызывающий код."""

    def __init__(
        self,
        bank: ItemBank | Sequence[BankItem],
        claimed_grade: str,
        *,
        config: CATConfig | None = None,
        seed: int = 0,
        exposure_rates: Mapping[str, float] | None = None,
        exclude_ids: Iterable[str] = (),
        avoid_ids: Iterable[str] = (),
        state: SessionState | None = None,
    ) -> None:
        self.bank = bank if isinstance(bank, ItemBank) else ItemBank(bank)
        self.config = config or CATConfig()
        check_grade(claimed_grade)
        self.prior_mean, self.prior_sd = prior_for_grade(claimed_grade, self.config.prior_sd)
        rates = exposure_rates or {}
        self._exposure = np.array(
            [float(rates.get(i.item_id, 0.0)) for i in self.bank.items], dtype=np.float64
        )
        self._excluded = frozenset(exclude_ids)
        avoid = frozenset(avoid_ids)
        self._avoid = np.array([i.item_id in avoid for i in self.bank.items], dtype=bool)
        if state is None:
            state = SessionState(
                claimed_grade=claimed_grade, seed=int(seed), pilot_slots=self._plan_pilots(seed)
            )
        elif state.claimed_grade != claimed_grade:
            raise ValueError("claimed_grade не совпадает с сохранённым состоянием")
        self.state = state

    @classmethod
    def restore(
        cls,
        bank: ItemBank | Sequence[BankItem],
        state: SessionState | Mapping[str, Any],
        *,
        config: CATConfig | None = None,
        exposure_rates: Mapping[str, float] | None = None,
        exclude_ids: Iterable[str] = (),
        avoid_ids: Iterable[str] = (),
    ) -> CATSession:
        """Восстановить сессию из сохранённого состояния (например, из JSON в БД)."""
        st = state if isinstance(state, SessionState) else SessionState.from_dict(state)
        return cls(
            bank,
            st.claimed_grade,
            config=config,
            seed=st.seed,
            exposure_rates=exposure_rates,
            exclude_ids=exclude_ids,
            avoid_ids=avoid_ids,
            state=st,
        )

    # ------------------------------------------------------------------ свойства

    @property
    def finished(self) -> bool:
        return self.state.finished

    @property
    def stop_reason(self) -> str | None:
        return self.state.stop_reason

    @property
    def records(self) -> list[AnswerRecord]:
        return self.state.records

    @property
    def n_scored(self) -> int:
        return sum(1 for r in self.state.records if r.scored)

    @property
    def n_pilot(self) -> int:
        return sum(1 for r in self.state.records if not r.scored)

    def estimate(self) -> ThetaEstimate:
        """Текущая оценка θ только по проверочным ответам."""
        return estimate_theta(
            ((r.a, r.b, r.correct) for r in self.state.records if r.scored),
            self.prior_mean,
            self.prior_sd,
        )

    # ------------------------------------------------------------------ шаги

    def next_item(self) -> BankItem | None:
        """Следующая задача (повторный вызов до ответа вернёт ту же). None — тест окончен."""
        st = self.state
        if st.finished:
            return None
        if st.pending_item_id is not None:
            pending = self.bank.get(st.pending_item_id)
            if pending is not None:
                return pending
            st.pending_item_id = None  # задачу убрали из банка — выбираем заново
        rng = random.Random(f"{st.seed}:{len(st.records)}")
        used = {r.item_id for r in st.records} | self._excluded
        item = None
        if len(st.records) in st.pilot_slots:
            item = self._select_pilot(used, rng)
        if item is None:
            item = self._select_scored(used, rng)
        if item is None:
            self._finish("bank_exhausted")
            return None
        st.pending_item_id = item.item_id
        return item

    def submit(self, item_id: str, correct: bool, elapsed_s: float | None = None) -> AnswerRecord:
        """Записать ответ на выданную задачу. elapsed_s — время по часам сервера."""
        st = self.state
        if st.finished:
            raise SessionFinishedError("Сессия уже завершена")
        if st.pending_item_id != item_id:
            raise ValueError(f"Ожидался ответ на {st.pending_item_id!r}, получен {item_id!r}")
        item = self.bank.get(item_id)
        if item is None:
            raise ValueError(f"Задачи {item_id!r} нет в банке")
        if elapsed_s is not None and elapsed_s < 0:
            raise ValueError("elapsed_s не может быть отрицательным")
        limit = item.time_limit_s if item.time_limit_s is not None else self.config.time_limit_s
        timed_out = elapsed_s is not None and elapsed_s > limit
        record = AnswerRecord(
            item_id=item.item_id,
            topic=item.topic,
            a=item.a,
            b=item.b,
            scored=not item.is_pilot,
            correct=bool(correct) and not timed_out,
            raw_correct=bool(correct),
            elapsed_s=None if elapsed_s is None else float(elapsed_s),
            timed_out=timed_out,
        )
        st.records.append(record)
        st.pending_item_id = None
        self._check_stop()
        return record

    def abort(self, reason: str = "aborted") -> None:
        """Прервать сессию (кандидат ушёл, истекло общее время и т. п.)."""
        if not self.state.finished:
            self._finish(reason)

    def result(self) -> CATResult:
        est = self.estimate()
        lo, hi = est.interval(self.config.ci_z)
        scored = [r for r in self.state.records if r.scored]
        return CATResult(
            claimed_grade=self.state.claimed_grade,
            theta=est.theta,
            se=est.se,
            ci_low=lo,
            ci_high=hi,
            n_scored=len(scored),
            n_pilot=self.n_pilot,
            n_timed_out=sum(1 for r in self.state.records if r.timed_out),
            finished=self.state.finished,
            stop_reason=self.state.stop_reason,
            topics=topic_breakdown(scored, est.theta),
            records=tuple(self.state.records),
        )

    # ------------------------------------------------------------------ внутреннее

    def _plan_pilots(self, seed: int) -> tuple[int, ...]:
        n_pilot_items = int(self.bank.pilot.sum())
        if n_pilot_items == 0 or self.config.pilot_max == 0:
            return ()
        rng = random.Random(f"{seed}:pilots")
        count = min(rng.randint(self.config.pilot_min, self.config.pilot_max), n_pilot_items)
        return tuple(sorted(rng.sample(range(1, self.config.min_items), count)))

    def _select_pilot(self, used: set[str], rng: random.Random) -> BankItem | None:
        bank = self.bank
        cands = [n for n in np.flatnonzero(bank.pilot) if bank.items[n].item_id not in used]
        if not cands:
            return None
        # новые для кандидата и реже показанные пилотные — вперёд: так калибровка набирает
        # ответы равномерно, а прошлые задачи кандидата идут в последнюю очередь
        cands.sort(key=lambda n: (bool(self._avoid[n]), self._exposure[n]))
        return bank.items[rng.choice(cands[:3])]

    def _select_scored(self, used: set[str], rng: random.Random) -> BankItem | None:
        bank = self.bank
        if len(bank) == 0:
            return None
        mask = ~bank.pilot
        if used:
            mask &= np.array([i.item_id not in used for i in bank.items], dtype=bool)
        if not mask.any():
            return None
        cfg = self.config
        by_exposure = mask & (self._exposure < cfg.max_exposure_rate)
        if by_exposure.any():
            mask = by_exposure
        counts = Counter(r.topic for r in self.state.records if r.scored)
        topic_counts = np.array([counts.get(t, 0) for t in bank.topic_names], dtype=np.float64)[
            bank.topic_idx
        ]
        by_topic = mask & (topic_counts < cfg.max_per_topic)
        if by_topic.any():
            mask = by_topic
        theta = self.estimate().theta
        score = information(theta, bank.a, bank.b) / (1.0 + cfg.topic_penalty * topic_counts)
        fresh = mask & ~self._avoid
        if fresh.any() and (fresh != mask).any():
            # прошлые задачи — в последнюю очередь: только если новых подходящих не осталось
            best = float(score[mask].max())
            good_fresh = fresh & (score >= cfg.repeat_info_ratio * best)
            if good_fresh.any():
                mask = good_fresh
        cands = np.flatnonzero(mask)
        top = cands[np.argsort(-score[cands], kind="stable")[: cfg.top_k]]
        return bank.items[int(top[rng.randrange(len(top))])]

    def _check_stop(self) -> None:
        n = self.n_scored
        cfg = self.config
        if n >= cfg.max_items:
            self._finish("max_items")
        elif n >= cfg.min_items and self.estimate().se < cfg.se_target:
            self._finish("se_target")

    def _finish(self, reason: str) -> None:
        self.state.finished = True
        self.state.stop_reason = reason
        self.state.pending_item_id = None


def topic_breakdown(
    records: Sequence[AnswerRecord], theta: float, margin: float = 0.2
) -> tuple[TopicStat, ...]:
    """Сильные и слабые темы: доля верных против ожидаемой при итоговой θ.

    Адаптивный тест подбирает задачи так, что в среднем верна примерно половина, поэтому
    сравнивать надо не «сколько верно», а «насколько больше или меньше ожидаемого».
    """
    groups: dict[str, list[AnswerRecord]] = {}
    for r in records:
        groups.setdefault(r.topic, []).append(r)
    out = []
    for topic, rs in groups.items():
        n = len(rs)
        n_correct = sum(1 for r in rs if r.correct)
        expected = float(sum(prob(theta, r.a, r.b) for r in rs))
        delta = (n_correct - expected) / n
        if n >= 2 and delta >= margin:
            level = "strong"
        elif n >= 2 and delta <= -margin:
            level = "weak"
        else:
            level = "ok"
        out.append(TopicStat(topic, n, n_correct, round(expected, 3), level))
    return tuple(sorted(out, key=lambda s: s.topic))
