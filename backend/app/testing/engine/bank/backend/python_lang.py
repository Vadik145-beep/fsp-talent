"""Backend · семантика Python: срезы, изменяемые аргументы по умолчанию, позднее связывание."""

from __future__ import annotations

import random
from typing import Any

from ...templates import ItemFormat, ItemTemplate, Variant

_OUTPUT_PROMPT = (
    "Что выведет код (Python 3.12)? Запишите все выведенные значения по порядку через пробел."
)

# ------------------------------------------------------------ срезы и индексы


def _gen_slicing(rng: random.Random) -> Variant:
    name = rng.choice(("a", "nums", "items", "data", "xs", "scores"))
    n = rng.randint(6, 9)
    if rng.random() < 0.5:
        values: list[Any] = rng.sample(range(10, 99), n)
        literal = "[" + ", ".join(map(str, values)) + "]"
    else:
        values = rng.sample(list("bcdfghkmnpqrstvwxz"), n)
        literal = "[" + ", ".join(f'"{v}"' for v in values) + "]"

    def stmt(kind: str) -> tuple[str, list[Any]]:
        if kind == "index":
            i = rng.randrange(1, n)
            return f"print({name}[{i}])", [values[i]]
        if kind == "neg_index":
            k = rng.randint(1, n - 1)
            return f"print({name}[-{k}])", [values[-k]]
        if kind == "slice":
            i = rng.randint(1, n - 3)
            j = rng.randint(i + 1, n - 1)
            return f"print(*{name}[{i}:{j}])", values[i:j]
        if kind == "head":
            k = rng.randint(2, n - 2)
            return f"print(*{name}[:{k}])", values[:k]
        if kind == "tail":
            k = rng.randint(2, n - 2)
            return f"print(*{name}[-{k}:])", values[-k:]
        if kind == "step":
            s = rng.choice((2, 3))
            st = rng.choice((0, 1))
            head = f"{st}::{s}" if st else f"::{s}"
            return f"print(*{name}[{head}])", values[st::s]
        if kind == "reverse":
            j = rng.randint(3, n - 1)
            i = rng.randint(0, j - 2)
            return f"print(*{name}[{j}:{i}:-1])", values[j:i:-1]
        # len_clamp: срез за границей списка не падает, а обрезается
        i = rng.randint(1, n - 2)
        j = rng.choice((n + 3, 50, 100))
        return f"print(len({name}[{i}:{j}]))", [len(values[i:j])]

    kinds = rng.sample(
        ["index", "neg_index", "slice", "head", "tail", "step", "reverse", "len_clamp"], 3
    )
    lines = [f"{name} = {literal}"]
    out: list[Any] = []
    for k in kinds:
        line, vals = stmt(k)
        lines.append(line)
        out += vals
    return Variant(
        prompt=_OUTPUT_PROMPT,
        key=" ".join(map(str, out)),
        code="\n".join(lines),
        extra={"language": "python"},
        explanation="Срез [i:j] не включает j; отрицательный индекс считается с конца.",
    )


PY_SLICING = ItemTemplate(
    id="backend.py_slicing",
    specialization="backend",
    topic="python",
    target_grade="intern",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_slicing,
    a=1.0,
    b=-1.5,
    title="Индексы и срезы списка",
    time_limit_s=150,
)

# ------------------------------------------------------------ изменяемый аргумент по умолчанию


def _gen_mutable_default(rng: random.Random) -> Variant:
    kind = rng.choice(("list", "list", "dict", "fixed"))
    fn = rng.choice(("add_tag", "collect", "remember", "register", "push"))
    acc = rng.choice(("acc", "bucket", "seen", "store", "items"))
    if kind == "list":
        head = [f"def {fn}(x, {acc}=[]):", f"    {acc}.append(x)", f"    return {acc}"]
    elif kind == "fixed":
        head = [
            f"def {fn}(x, {acc}=None):",
            f"    if {acc} is None:",
            f"        {acc} = []",
            f"    {acc}.append(x)",
            f"    return {acc}",
        ]
    else:
        head = [f"def {fn}(x, {acc}={{}}):", f"    {acc}[x] = True", f"    return {acc}"]
    empty = "{}" if kind == "dict" else "[]"

    # модель: объекты-контейнеры и их содержимое
    objects: list[set[str] | list[str]] = []
    default_obj: int | None = None
    results: list[int] = []
    call_lines: list[str] = []
    n_calls = rng.randint(3, 4)
    pool = rng.sample(list("abcdefgh"), 4)
    for c in range(n_calls):
        x = rng.choice(pool) if kind == "dict" else pool[c % len(pool)]
        mode = rng.choice(("default", "default", "default", "fresh", "reuse"))
        if mode == "reuse" and not results:
            mode = "default"
        if mode == "default":
            if kind == "fixed" or default_obj is None:
                objects.append(set() if kind == "dict" else [])
                obj = len(objects) - 1
                if kind != "fixed":
                    default_obj = obj
            else:
                obj = default_obj
            call = f'r{c + 1} = {fn}("{x}")'
        elif mode == "fresh":
            objects.append(set() if kind == "dict" else [])
            obj = len(objects) - 1
            call = f'r{c + 1} = {fn}("{x}", {empty})'
        else:
            src = rng.randrange(len(results))
            obj = results[src]
            call = f'r{c + 1} = {fn}("{x}", r{src + 1})'
        container = objects[obj]
        if isinstance(container, set):
            container.add(x)
        else:
            container.append(x)
        results.append(obj)
        call_lines.append(call)
    names = [f"r{i + 1}" for i in range(n_calls)]
    out = [str(len(objects[o])) for o in results]
    lines = [*head, "", "", *call_lines, f"print({', '.join(f'len({r})' for r in names)})"]
    i, j = rng.sample(range(n_calls), 2)
    i, j = min(i, j), max(i, j)
    lines.append(f"print({names[i]} is {names[j]})")
    out.append(str(results[i] == results[j]))
    return Variant(
        prompt=_OUTPUT_PROMPT,
        key=" ".join(out),
        code="\n".join(lines),
        extra={"language": "python"},
        explanation=(
            "Значение по умолчанию вычисляется один раз при определении функции "
            "и разделяется между вызовами."
        ),
    )


PY_MUTABLE_DEFAULT = ItemTemplate(
    id="backend.py_mutable_default",
    specialization="backend",
    topic="python",
    target_grade="junior",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_mutable_default,
    a=1.3,
    b=-0.5,
    title="Изменяемый аргумент по умолчанию",
    time_limit_s=180,
)

# ------------------------------------------------------------ позднее связывание в замыканиях


def _op_add(x: int, v: int) -> int:
    return x + v


def _op_mul(x: int, v: int) -> int:
    return x * v


def _op_sub(x: int, v: int) -> int:
    return x - v


def _op_sq(x: int, v: int) -> int:
    return v * v + x


_OPS = (
    ("x + {v}", _op_add),
    ("x * {v}", _op_mul),
    ("x - {v}", _op_sub),
    ("{v} * {v} + x", _op_sq),
)


def _gen_late_binding(rng: random.Random) -> Variant:
    kind = rng.choice(
        ("loop", "comp", "default", "factory", "loop_reassign", "comp_reassign", "loop")
    )
    v = rng.choice(("i", "k", "n", "step"))
    fs = rng.choice(("funcs", "handlers", "callbacks", "ops"))
    start = rng.randint(0, 3)
    count = rng.randint(3, 4)
    stop = start + count
    op_tpl, op = rng.choice(_OPS)
    body = op_tpl.format(v=v)
    arg = rng.randint(1, 10)
    loop_values = list(range(start, stop))
    reassigned = rng.choice((10, 20, 100))
    if kind in ("loop", "loop_reassign", "default"):
        lam = f"lambda x, {v}={v}: {body}" if kind == "default" else f"lambda x: {body}"
        lines = [f"{fs} = []", f"for {v} in range({start}, {stop}):", f"    {fs}.append({lam})"]
    elif kind in ("comp", "comp_reassign"):
        lines = [f"{fs} = [lambda x: {body} for {v} in range({start}, {stop})]"]
    else:
        lines = [
            f"def make({v}):",
            f"    return lambda x: {body}",
            "",
            "",
            f"{fs} = [make({v}) for {v} in range({start}, {stop})]",
        ]
    if kind in ("loop_reassign", "comp_reassign"):
        lines.append(f"{v} = {reassigned}")
    lines.append(f"print(*[f({arg}) for f in {fs}])")

    if kind in ("default", "factory"):
        bound = loop_values
    elif kind == "loop_reassign":
        bound = [reassigned] * count  # переменная цикла — глобальная, лямбды видят новое значение
    else:
        bound = [loop_values[-1]] * count  # у генератора списка своя область видимости
    out = [str(op(arg, b)) for b in bound]
    return Variant(
        prompt=_OUTPUT_PROMPT,
        key=" ".join(out),
        code="\n".join(lines),
        extra={"language": "python"},
        explanation=(
            "Замыкание хранит ссылку на переменную, а не её значение; значение берётся "
            "в момент вызова."
        ),
    )


PY_LATE_BINDING = ItemTemplate(
    id="backend.py_late_binding",
    specialization="backend",
    topic="python",
    target_grade="middle",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_late_binding,
    a=1.4,
    b=0.4,
    title="Замыкания и позднее связывание",
    time_limit_s=180,
)

TEMPLATES = [PY_SLICING, PY_MUTABLE_DEFAULT, PY_LATE_BINDING]
