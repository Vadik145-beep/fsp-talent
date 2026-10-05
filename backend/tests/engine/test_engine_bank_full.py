"""Общие проверки рабочего банка задач: любой новый шаблон обязан их проходить."""

import re
from collections import Counter

import pytest

from app.testing.engine.bank import BANK_TEMPLATES, bank_registry
from app.testing.engine.templates import ItemFormat, ItemInstance, correct_response

SEEDS = range(150)
GRADE_ORDER = {"intern": 0, "junior": 1, "middle": 2, "senior": 3}


def _wrong_response(inst: ItemInstance):
    """Заведомо неверный ответ того же вида (как в test_engine_bank_examples)."""
    key = inst.key
    fmt = inst.format
    if fmt is ItemFormat.SINGLE_CHOICE:
        return (key + 1) % len(inst.public.options)
    if fmt is ItemFormat.MULTI_CHOICE:
        return sorted(set(key) ^ {0})
    if fmt is ItemFormat.NUMERIC:
        return key.value + 1
    if fmt is ItemFormat.SHORT_TEXT:
        return "неверный ответ"
    if fmt is ItemFormat.CODE_OUTPUT:
        return " ".join(reversed(key.split())) + " x"
    if fmt is ItemFormat.FIND_BUG_LINE:
        return key % len(inst.public.code.split("\n")) + 1
    if fmt is ItemFormat.ORDERING:
        k = list(key)
        k[0], k[1] = k[1], k[0]
        return k
    raise AssertionError(fmt)


def test_ids_unique_and_registry_builds():
    ids = [t.id for t in BANK_TEMPLATES]
    dupes = [i for i, n in Counter(ids).items() if n > 1]
    assert not dupes, dupes
    assert len(bank_registry()) == len(BANK_TEMPLATES)


@pytest.mark.parametrize("template", BANK_TEMPLATES, ids=lambda t: t.id)
def test_template_contract(template):
    assert template.id.startswith(f"{template.specialization}."), template.id
    assert 0.5 <= template.a <= 2.5
    assert abs(template.b - (GRADE_ORDER[template.target_grade] - 1.5)) <= 0.8, template.id
    fingerprints = set()
    for seed in SEEDS:
        inst = template.generate(seed)
        fingerprints.add(inst.fingerprint)
        assert template.check(inst, correct_response(inst)), (template.id, seed)
        assert not template.check(inst, _wrong_response(inst)), (template.id, seed)
        public = inst.public.to_dict()
        assert "key" not in public
        assert re.search("[а-яА-Я]", public["prompt"]), "формулировка по-русски"
    assert len(fingerprints) >= 50, f"{template.id}: {len(fingerprints)} вариантов"
    assert template.generate(123).fingerprint == template.generate(123).fingerprint


@pytest.mark.parametrize(
    "template",
    [t for t in BANK_TEMPLATES if t.format not in (ItemFormat.NUMERIC, ItemFormat.SHORT_TEXT)],
    ids=lambda t: t.id,
)
def test_answer_position_does_not_repeat(template):
    keys = Counter(repr(template.generate(seed).key) for seed in range(200))
    assert keys.most_common(1)[0][1] / 200 <= 0.5, keys.most_common(3)
