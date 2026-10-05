import random

import pytest

from app.testing.engine.templates import (
    ItemFormat,
    ItemInstance,
    ItemTemplate,
    NumericKey,
    PublicItem,
    TemplateRegistry,
    TemplateStatus,
    Variant,
    check,
    correct_response,
    make_multi_choice,
    make_ordering,
    make_single_choice,
    normalize_text,
    output_tokens,
)


def _inst(fmt: ItemFormat, key, options=(), code=None) -> ItemInstance:
    return ItemInstance("t", 1, PublicItem(fmt, "q", tuple(options), code), key)


def _gen_square(rng: random.Random) -> Variant:
    x = rng.randint(2, 99)
    return Variant(prompt=f"Чему равно {x} в квадрате?", key=NumericKey(x * x, 0))


def _template(**kw) -> ItemTemplate:
    params = dict(
        id="demo.square",
        specialization="backend",
        topic="math",
        target_grade="intern",
        format=ItemFormat.NUMERIC,
        generator=_gen_square,
    )
    params.update(kw)
    return ItemTemplate(**params)


def test_check_single_choice_and_find_line():
    inst = _inst(ItemFormat.SINGLE_CHOICE, 2, ["a", "b", "c"])
    assert check(inst, 2) and check(inst, "2") and check(inst, 2.0)
    assert not check(inst, 1)
    assert not check(inst, True)  # bool не считается числом
    assert not check(inst, None) and not check(inst, "два") and not check(inst, [2])
    line = _inst(ItemFormat.FIND_BUG_LINE, 4, code="a\nb\nc\nd")
    assert check(line, " 4 ") and not check(line, 3)


def test_check_multi_choice():
    inst = _inst(ItemFormat.MULTI_CHOICE, frozenset({0, 2}), ["a", "b", "c"])
    assert check(inst, [2, 0]) and check(inst, ("0", "2"))
    assert not check(inst, [0]) and not check(inst, [0, 1, 2])
    assert not check(inst, [0, 0, 2])  # повторы — мусор
    assert not check(inst, "02") and not check(inst, None)


def test_check_numeric():
    inst = _inst(ItemFormat.NUMERIC, NumericKey(0.25, 0.006))
    for ok in (0.25, "0.25", "0,25", " 0.2549 ", 0.244):
        assert check(inst, ok), ok
    for bad in (0.3, "abc", None, float("nan"), float("inf"), True, "1e999"):
        assert not check(inst, bad), bad
    exact = _inst(ItemFormat.NUMERIC, NumericKey(7, 0))
    assert check(exact, "7") and check(exact, 7.0) and not check(exact, 8)


def test_check_short_text_normalization():
    inst = _inst(ItemFormat.SHORT_TEXT, ("404", "404 not found"))
    assert check(inst, " 404 ") and check(inst, "404 Not  Found.") and check(inst, "«404»")
    assert not check(inst, "405") and not check(inst, "") and not check(inst, 404)
    assert normalize_text("  Ёжик   В тумане! ") == "ежик в тумане"


def test_check_code_output_tokens():
    inst = _inst(ItemFormat.CODE_OUTPUT, "A C B", code="x")
    assert check(inst, "A\nC\nB") and check(inst, "A, C, B") and check(inst, " A C B ")
    assert not check(inst, "A B C") and not check(inst, None)
    assert output_tokens("1\n 2;3 ,4") == ["1", "2", "3", "4"]


def test_check_ordering():
    inst = _inst(ItemFormat.ORDERING, (2, 0, 1), ["b", "c", "a"])
    assert check(inst, [2, 0, 1]) and check(inst, ["2", "0", "1"])
    assert not check(inst, [0, 1, 2]) and not check(inst, "201")


def test_generate_is_deterministic_and_hides_key():
    t = _template()
    a, b = t.generate(42), t.generate(42)
    assert a.fingerprint == b.fingerprint and a.key == b.key
    assert (
        t.generate(43).fingerprint != a.fingerprint or t.generate(44).fingerprint != a.fingerprint
    )
    public = a.public.to_dict()
    assert set(public) == {"format", "prompt", "options", "code", "extra"}
    assert "key" not in public and "template_id" not in public and "seed" not in public
    assert t.check(a, correct_response(a))
    assert not t.check(a, a.key.value + 1)


def test_template_check_rejects_foreign_instance():
    t = _template()
    other = _template(id="demo.other")
    with pytest.raises(ValueError):
        t.check(other.generate(1), 1)


def test_template_validation():
    with pytest.raises(ValueError):
        _template(specialization="gamedev")
    with pytest.raises(ValueError):
        _template(target_grade="lead")
    with pytest.raises(ValueError):
        _template(a=0)
    t = _template(status="pilot", format="numeric")
    assert t.status is TemplateStatus.PILOT and t.format is ItemFormat.NUMERIC


def test_bad_generator_output_is_rejected():
    def bad(rng: random.Random) -> Variant:
        return Variant(prompt="Выберите", key=5, options=("a", "b"))

    t = _template(format=ItemFormat.SINGLE_CHOICE, generator=bad)
    with pytest.raises(ValueError):
        t.generate(1)


def test_helpers_shuffle_and_keys():
    rng = random.Random(3)
    for _ in range(50):
        v = make_single_choice(rng, "q", "right", ["w1", "w2", "w3", "w4", "right"])
        assert v.options[v.key] == "right" and len(v.options) == 4
        m = make_multi_choice(rng, "q", ["r1", "r2"], ["w1", "w2"])
        assert {v_ for i, v_ in enumerate(m.options) if i in m.key} == {"r1", "r2"}
        steps = ["s1", "s2", "s3", "s4"]
        o = make_ordering(rng, "q", steps)
        assert list(o.options) != steps  # перемешано
        assert [o.options[i] for i in o.key] == steps


def test_registry():
    t1 = _template()
    t2 = _template(id="demo.pilot", status=TemplateStatus.PILOT, specialization="qa", topic="x")
    reg = TemplateRegistry([t1, t2])
    assert len(reg) == 2 and "demo.square" in reg
    with pytest.raises(ValueError):
        reg.register(t1)
    with pytest.raises(KeyError):
        reg.get("nope")
    assert reg.filter(specialization="qa") == [t2]
    assert reg.filter(status="active") == [t1]
    assert reg.filter(status=["active", "pilot"]) == [t1, t2]
    assert reg.topics() == ["math", "x"]
    inst = reg.instance("demo.square", 5)
    assert reg.check(inst, correct_response(inst))
