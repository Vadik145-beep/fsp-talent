"""Backend-банк: состав (число шаблонов, грейды, темы, форматы) и базовые свойства."""

from collections import Counter

from app.testing.engine.bank.backend import TEMPLATES
from app.testing.engine.bank_examples import EXAMPLE_TEMPLATES
from app.testing.engine.templates import ItemFormat

GRADE_CENTER = {"intern": -1.5, "junior": -0.5, "middle": 0.5, "senior": 1.5}


def test_thirty_templates_with_planned_grades():
    assert len(TEMPLATES) == 30
    assert all(t.specialization == "backend" for t in TEMPLATES)
    grades = Counter(t.target_grade for t in TEMPLATES)
    assert grades == {"intern": 6, "junior": 8, "middle": 9, "senior": 7}


def test_topics_and_formats_balance():
    topics = Counter(t.topic for t in TEMPLATES)
    assert len(topics) >= 6
    assert max(topics.values()) <= 7
    assert {t.format for t in TEMPLATES} == set(ItemFormat)


def test_irt_params_match_grade():
    for t in TEMPLATES:
        assert 0.5 <= t.a <= 2.5, t.id
        assert abs(t.b - GRADE_CENTER[t.target_grade]) <= 0.8, t.id
        assert 90 <= t.time_limit_s <= 300, t.id
        assert t.title, t.id


def test_no_duplicates_of_examples():
    example_ids = {t.id for t in EXAMPLE_TEMPLATES}
    ids = [t.id for t in TEMPLATES]
    assert len(set(ids)) == len(ids)
    assert not example_ids & set(ids)
    # сложность циклов и JOIN уже есть в примерах — в банке их механик нет
    assert not {"backend.algo_complexity", "backend.sql_join_rows"} & set(ids)


def test_many_distinct_variants():
    for t in TEMPLATES:
        prints = {t.generate(seed).fingerprint for seed in range(400)}
        assert len(prints) >= 100, (t.id, len(prints))
