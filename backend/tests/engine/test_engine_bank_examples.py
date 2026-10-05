import ipaddress
import re
import shutil
import sqlite3
import subprocess
from collections import Counter

import pytest

from app.testing.engine.bank_examples import EXAMPLE_TEMPLATES, example_registry
from app.testing.engine.bank_examples.frontend import _simulate
from app.testing.engine.constants import SPECIALIZATIONS
from app.testing.engine.templates import ItemFormat, ItemInstance, check, correct_response

SEEDS = range(400)


def _wrong_response(inst: ItemInstance):
    """Заведомо неверный ответ того же вида."""
    key = inst.key
    fmt = inst.format
    if fmt is ItemFormat.SINGLE_CHOICE:
        return (key + 1) % len(inst.public.options)
    if fmt is ItemFormat.MULTI_CHOICE:
        return sorted(set(key) ^ {0})  # добавить или убрать один вариант
    if fmt is ItemFormat.NUMERIC:
        return key.value + 1
    if fmt is ItemFormat.SHORT_TEXT:
        return "неверный ответ"
    if fmt is ItemFormat.CODE_OUTPUT:
        return " ".join(reversed(key.split()))
    if fmt is ItemFormat.FIND_BUG_LINE:
        return key % len(inst.public.code.split("\n")) + 1
    if fmt is ItemFormat.ORDERING:
        k = list(key)
        k[0], k[1] = k[1], k[0]
        return k
    raise AssertionError(fmt)


def test_bank_composition():
    assert len(EXAMPLE_TEMPLATES) == 12
    by_spec = Counter(t.specialization for t in EXAMPLE_TEMPLATES)
    assert by_spec == dict.fromkeys(SPECIALIZATIONS, 2)
    assert {t.format for t in EXAMPLE_TEMPLATES} == set(ItemFormat)
    assert len(example_registry()) == 12
    # a, b заданы экспертно и согласованы с целевым грейдом
    order = {"intern": 0, "junior": 1, "middle": 2, "senior": 3}
    for t in EXAMPLE_TEMPLATES:
        assert 0.5 <= t.a <= 2.5
        assert abs(t.b - (order[t.target_grade] - 1.5)) <= 0.8, t.id


@pytest.mark.parametrize("template", EXAMPLE_TEMPLATES, ids=lambda t: t.id)
def test_template_variants_and_checking(template):
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
    # детерминизм
    assert template.generate(123).fingerprint == template.generate(123).fingerprint


@pytest.mark.parametrize(
    "template",
    [t for t in EXAMPLE_TEMPLATES if t.format not in (ItemFormat.NUMERIC, ItemFormat.SHORT_TEXT)],
    ids=lambda t: t.id,
)
def test_answer_position_does_not_repeat(template):
    """Позиция или номер верного ответа не одна и та же: слитое «ответ — второй» не работает."""
    keys = Counter(repr(template.generate(seed).key) for seed in range(300))
    assert keys.most_common(1)[0][1] / 300 <= 0.5, keys.most_common(3)


def test_python_complexity_code_runs():
    t = example_registry().get("backend.algo_complexity")
    for seed in range(60):
        inst = t.generate(seed)
        scope: dict = {}
        exec(inst.public.code, scope)  # код задачи должен быть рабочим Python
        func = next(v for k, v in scope.items() if callable(v) and not k.startswith("__"))
        assert isinstance(func(list(range(1, 33))), int)


def _parse_sql_variant(code: str):
    blocks = code.split("\n\n")
    tables = {}
    for block in blocks[:-1]:
        lines = block.split("\n")
        name = lines[0].removeprefix("-- ").strip()
        header = [h.strip() for h in lines[1].split("|")]
        rows = [[c.strip() for c in line.split("|")] for line in lines[3:]]
        tables[name] = (header, rows)
    return tables, blocks[-1]


@pytest.mark.skipif(sqlite3.sqlite_version_info < (3, 39), reason="нужен FULL JOIN в SQLite")
def test_sql_answers_match_real_database():
    t = example_registry().get("backend.sql_join_rows")
    for seed in range(150):
        inst = t.generate(seed)
        tables, sql = _parse_sql_variant(inst.public.code)
        db = sqlite3.connect(":memory:")
        for name, (header, rows) in tables.items():
            db.execute(f"CREATE TABLE {name} ({', '.join(header)})")
            for r in rows:
                vals = [None if v == "NULL" else (int(v) if v.isdigit() else v) for v in r]
                db.execute(f"INSERT INTO {name} VALUES ({', '.join('?' * len(vals))})", vals)
        result = db.execute(sql).fetchall()
        actual = result[0][0] if sql.startswith("SELECT COUNT") else len(result)
        assert actual == inst.key.value, (seed, sql)


def test_event_loop_model_examples():
    assert _simulate([("sync", "A"), ("timeout", "B", 0), ("promise", "C")]) == ["A", "C", "B"]
    assert _simulate(
        [("chain", "A", "B"), ("micro", "C"), ("await", "D", "E"), ("timeout", "F", 0)]
    ) == ["D", "A", "C", "E", "B", "F"]
    assert _simulate(
        [("timeout_promise", "A", "B", 0), ("timeout", "C", 0), ("timeout", "D", 10)]
    ) == ["A", "B", "C", "D"]
    assert _simulate([("timeout", "A", 100), ("timeout", "B", 0)]) == ["B", "A"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node не установлен")
def test_event_loop_answers_match_node():
    t = example_registry().get("frontend.event_loop_order")
    for seed in range(25):
        inst = t.generate(seed)
        out = subprocess.run(
            ["node", "-e", inst.public.code], capture_output=True, text=True, timeout=30
        )
        assert out.returncode == 0, out.stderr
        assert check(inst, out.stdout), (seed, inst.public.code, out.stdout, inst.key)


def _specificity(selector: str) -> tuple[int, int, int]:
    compounds = [c for c in re.split(r"\s*>\s*|\s+", selector) if c]
    ids = selector.count("#")
    classes = selector.count(".") + selector.count("[")
    types = sum(1 for c in compounds if c[0].isalpha())
    return ids, classes, types


def test_css_specificity_examples():
    t = example_registry().get("frontend.css_specificity")
    for seed in range(150):
        inst = t.generate(seed)
        rules = re.findall(r"^(.+?) \{ color: (\w+)( !important)?; \}$", inst.public.code, re.M)
        assert len(rules) == 4
        ranked = max(range(4), key=lambda i: (bool(rules[i][2]), _specificity(rules[i][0]), i))
        assert inst.public.options[inst.key] == rules[ranked][1], inst.public.code


def test_cidr_answers():
    t = example_registry().get("devops.cidr_subnet")
    for seed in range(100):
        inst = t.generate(seed)
        ip, prefix = re.search(r"(\d+\.\d+\.\d+\.\d+)/(\d+)", inst.public.prompt).groups()
        net = ipaddress.IPv4Network(f"{ip}/{prefix}", strict=False)
        answer = ipaddress.IPv4Address(inst.key[0])
        assert answer in net
        assert answer != ipaddress.IPv4Address(ip)  # ответ не списывается из условия


def test_find_bug_line_points_to_meaningful_line():
    reg = example_registry()
    for tid in ("mobile.kotlin_find_bug", "devops.dockerfile_layers"):
        t = reg.get(tid)
        for seed in range(100):
            inst = t.generate(seed)
            line = inst.public.code.split("\n")[inst.key - 1]
            assert line.strip() and not line.strip().startswith(("//", "#", "}"))
