import json
import random
from collections import Counter

import pytest

from app.testing.engine.bank_examples import EXAMPLE_TEMPLATES
from app.testing.engine.cat import (
    AnswerRecord,
    BankItem,
    CATConfig,
    CATSession,
    ItemBank,
    SessionFinishedError,
    SessionState,
    topic_breakdown,
)
from app.testing.engine.irt import estimate_theta, prob
from app.testing.engine.templates import TemplateStatus, check, correct_response


def make_bank(n=120, n_topics=6, n_pilot=6, seed=0, a=1.3):
    rng = random.Random(seed)
    items = [
        BankItem(f"i{k}", f"t{k % n_topics}", a * rng.uniform(0.8, 1.2), rng.uniform(-3, 3))
        for k in range(n)
    ]
    items += [BankItem(f"p{k}", "pilot_topic", 1.0, 0.0, status="pilot") for k in range(n_pilot)]
    return ItemBank(items)


def run(session: CATSession, theta: float, rng: random.Random, elapsed=None):
    while (item := session.next_item()) is not None:
        session.submit(item.item_id, rng.random() < prob(theta, item.a, item.b), elapsed)
    return session.result()


def test_session_respects_length_limits():
    bank = make_bank()
    rng = random.Random(1)
    for seed in range(30):
        s = CATSession(bank, "middle", seed=seed)
        res = run(s, rng.gauss(0, 1), rng)
        assert s.finished
        assert 6 <= res.n_scored <= 15
        assert res.stop_reason in ("se_target", "max_items")
        if res.stop_reason == "se_target":
            assert res.se < 0.35
        assert 1 <= res.n_pilot <= 2


def test_no_stop_before_min_items_even_with_precise_items():
    bank = make_bank(a=4.0, n_pilot=0)
    s = CATSession(bank, "middle", seed=3, config=CATConfig(se_target=0.9))
    res = run(s, 0.3, random.Random(3))
    assert res.n_scored == 6 and res.stop_reason == "se_target"


def test_next_item_is_idempotent_and_submit_validates():
    s = CATSession(make_bank(), "junior", seed=5)
    first = s.next_item()
    assert s.next_item() == first
    with pytest.raises(ValueError):
        s.submit("not-this-one", True)
    with pytest.raises(ValueError):
        s.submit(first.item_id, True, elapsed_s=-1)
    s.submit(first.item_id, True)
    assert s.next_item() != first
    s.abort()
    assert s.finished and s.next_item() is None
    with pytest.raises(SessionFinishedError):
        s.submit("x", True)


def test_timeout_makes_answer_wrong():
    bank = ItemBank([BankItem("a", "t", 1.0, 0.0, time_limit_s=60), *make_bank().items])
    s = CATSession(bank, "middle", seed=1)
    item = s.next_item()
    rec = s.submit(item.item_id, True, elapsed_s=(item.time_limit_s or 180) + 1)
    assert rec.timed_out and not rec.correct and rec.raw_correct
    item = s.next_item()
    rec = s.submit(item.item_id, True, elapsed_s=5)
    assert rec.correct and not rec.timed_out
    assert s.result().n_timed_out == 1


def test_pilot_items_do_not_affect_theta():
    bank = make_bank()
    results = []
    for pilot_answer in (True, False):
        rng = random.Random(7)
        s = CATSession(bank, "middle", seed=11)
        while (item := s.next_item()) is not None:
            correct = pilot_answer if item.is_pilot else rng.random() < prob(0.5, item.a, item.b)
            s.submit(item.item_id, correct)
        results.append(s.result())
    assert results[0].theta == pytest.approx(results[1].theta)
    assert results[0].n_pilot >= 1
    res = results[0]
    scored = [(r.a, r.b, r.correct) for r in res.records if r.scored]
    assert res.theta == pytest.approx(estimate_theta(scored, 0.5, 1.0).theta)
    # пилотные задачи стоят среди первых min_items показов
    positions = [n for n, r in enumerate(res.records) if not r.scored]
    assert all(1 <= p < CATConfig().min_items for p in positions)


def test_exposure_limit_excludes_overexposed_items():
    bank = make_bank(n_pilot=0)
    s0 = CATSession(bank, "middle", seed=0)
    first = s0.next_item()
    seen_first = set()
    for seed in range(40):
        s = CATSession(bank, "middle", seed=seed, exposure_rates={first.item_id: 0.9})
        res = run(s, 0.5, random.Random(seed))
        assert first.item_id not in {r.item_id for r in res.records}
        seen_first.add(res.records[0].item_id)
    assert len(seen_first) > 1


def test_randomesque_spreads_first_item_among_top5():
    bank = make_bank(n_pilot=0)
    firsts = Counter(CATSession(bank, "senior", seed=s).next_item().item_id for s in range(200))
    assert 2 <= len(firsts) <= 5
    # старт от заявленного грейда: первая задача — около θ = 1.5
    for item_id in firsts:
        assert bank.get(item_id).b > 0.3


def test_topic_balance_caps_topics():
    bank = make_bank(n=200, n_topics=5, n_pilot=0)
    cfg = CATConfig(se_target=0.01)  # всегда 15 задач
    for seed in range(20):
        res = run(CATSession(bank, "middle", seed=seed, config=cfg), 0.0, random.Random(seed))
        counts = Counter(r.topic for r in res.records if r.scored)
        assert res.n_scored == 15
        assert max(counts.values()) <= cfg.max_per_topic


def test_exclude_ids_and_bank_exhaustion():
    items = [BankItem(f"i{k}", "t", 1.0, k - 2.0) for k in range(4)]
    s = CATSession(items, "middle", seed=0, exclude_ids={"i0"})
    res = run(s, 0.0, random.Random(0))
    ids = {r.item_id for r in res.records}
    assert "i0" not in ids and len(ids) == 3
    assert res.stop_reason == "bank_exhausted"


def test_state_roundtrip_continues_identically():
    bank = make_bank()
    rng = random.Random(4)
    whole = CATSession(bank, "junior", seed=99)
    split = CATSession(bank, "junior", seed=99)
    for _ in range(4):
        item = whole.next_item()
        assert split.next_item() == item
        ans = rng.random() < 0.5
        whole.submit(item.item_id, ans, 30)
        split.submit(item.item_id, ans, 30)
    split.next_item()  # задача выдана, ответа ещё нет — тоже сохраняется
    raw = json.loads(json.dumps(split.state.to_dict()))
    restored = CATSession.restore(bank, raw)
    assert restored.next_item() == whole.next_item()
    assert restored.estimate() == whole.estimate()
    assert SessionState.from_dict(raw).to_dict() == raw


def test_restore_rejects_other_grade():
    bank = make_bank()
    state = CATSession(bank, "junior", seed=1).state
    with pytest.raises(ValueError):
        CATSession(bank, "senior", state=state)


def test_config_validation():
    with pytest.raises(ValueError):
        CATConfig(min_items=20, max_items=15)
    with pytest.raises(ValueError):
        CATConfig(pilot_max=6, min_items=6)
    assert CATConfig().max_per_topic == 6


def test_item_bank_from_templates_skips_draft_and_retired():
    import dataclasses

    t0, t1, t2, *_ = EXAMPLE_TEMPLATES
    draft = dataclasses.replace(t0, status=TemplateStatus.DRAFT)
    retired = dataclasses.replace(t1, status=TemplateStatus.RETIRED)
    bank = ItemBank.from_templates([draft, retired, t2])
    assert len(bank) == 1 and t2.id in bank


def test_end_to_end_with_example_templates():
    """Сессия на реальных шаблонах: генерируем вариант, проверяем ответ, отдаём результат."""
    bank = ItemBank.from_templates(EXAMPLE_TEMPLATES)
    by_id = {t.id: t for t in EXAMPLE_TEMPLATES}
    s = CATSession(bank, "middle", seed=2026)
    variant_seed = 1000
    while (item := s.next_item()) is not None:
        inst = by_id[item.item_id].generate(variant_seed)
        variant_seed += 1
        s.submit(item.item_id, check(inst, correct_response(inst)), elapsed_s=20)
    res = s.result()
    assert res.stop_reason == "bank_exhausted"  # в примере всего 12 шаблонов
    assert res.n_scored == 12 and res.theta > 1.5


def test_topic_breakdown_levels():
    recs = [AnswerRecord(f"a{k}", "sql", 1.5, 0.0, True, True, True) for k in range(3)]
    recs += [AnswerRecord(f"b{k}", "css", 1.5, 0.0, True, False, False) for k in range(3)]
    recs += [AnswerRecord("c", "docker", 1.5, 0.0, True, True, True)]
    stats = {s.topic: s for s in topic_breakdown(recs, 0.0)}
    assert stats["sql"].level == "strong" and stats["css"].level == "weak"
    assert stats["docker"].level == "ok"  # одна задача — выводов не делаем
    assert stats["sql"].expected_correct == pytest.approx(1.5)
