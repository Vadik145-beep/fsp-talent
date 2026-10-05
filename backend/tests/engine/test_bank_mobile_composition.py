"""Mobile: состав банка (30 шаблонов, грейды, темы, форматы, IRT-параметры)."""

import re
from collections import Counter

from app.testing.engine.bank.mobile import TEMPLATES
from app.testing.engine.bank_examples import EXAMPLE_TEMPLATES
from app.testing.engine.templates import ItemFormat

TARGET_B = {"intern": -1.5, "junior": -0.5, "middle": 0.5, "senior": 1.5}


def test_mobile_bank_composition():
    assert len(TEMPLATES) == 30
    assert all(t.specialization == "mobile" for t in TEMPLATES)
    assert Counter(t.target_grade for t in TEMPLATES) == {
        "intern": 6,
        "junior": 8,
        "middle": 9,
        "senior": 7,
    }
    topics = Counter(t.topic for t in TEMPLATES)
    assert len(topics) >= 6, topics
    assert max(topics.values()) <= 7, topics
    assert {t.format for t in TEMPLATES} == set(ItemFormat)


def test_mobile_ids_titles_limits():
    ids = [t.id for t in TEMPLATES]
    assert len(set(ids)) == len(ids)
    example_ids = {t.id for t in EXAMPLE_TEMPLATES}
    for t in TEMPLATES:
        assert re.fullmatch(r"mobile\.[a-z0-9_]+", t.id), t.id
        assert t.id not in example_ids
        assert re.fullmatch(r"[a-z_]+", t.topic), t.topic
        assert re.search("[а-яА-Я]", t.title), t.title
        assert 90 <= t.time_limit_s <= 300, t.id


def test_mobile_irt_parameters():
    for t in TEMPLATES:
        assert 0.5 <= t.a <= 2.5, t.id
        assert abs(t.b - TARGET_B[t.target_grade]) <= 0.4, t.id
    # внутри грейда сложность не одна и та же
    for grade in TARGET_B:
        bs = {t.b for t in TEMPLATES if t.target_grade == grade}
        assert len(bs) >= 3, grade


def test_examples_not_duplicated():
    """Механики примеров (порядок колбэков Activity, find_bug_line по Kotlin) не повторяем."""
    for t in TEMPLATES:
        assert not (t.topic == "android_lifecycle" and t.format is ItemFormat.ORDERING)
        assert not (t.topic == "kotlin" and t.format is ItemFormat.FIND_BUG_LINE)
