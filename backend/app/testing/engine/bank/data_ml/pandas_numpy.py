"""Data Science / ML — семантика numpy и pandas: «что выведет код».

Ответы вычисляются на чистом Python, без numpy/pandas; тесты сверяют их с выполнением кода.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable

from ...templates import ItemFormat, ItemTemplate, Variant

_PROMPT_NUMS = "Что выведет код? Запишите значения через пробел в порядке вывода."

# --------------------------------------------------------------------------- numpy: axis


def _gen_axis(rng: random.Random) -> Variant:
    name = rng.choice(("m", "a", "data", "scores", "grid"))
    rows, cols = rng.choice(((2, 3), (3, 2), (2, 4), (3, 3), (4, 2), (3, 4)))
    op = rng.choice(("sum", "sum", "max", "min", "argmax"))
    axis = rng.choice((0, 1))
    while True:
        m = [[rng.randint(-3, 9) for _ in range(cols)] for _ in range(rows)]
        lines_ = m if axis == 1 else [list(c) for c in zip(*m, strict=True)]
        if op == "argmax" and any(row.count(max(row)) > 1 for row in lines_):
            continue
        break
    funcs: dict[str, Callable[[list[int]], int]] = {
        "sum": sum,
        "max": max,
        "min": min,
        "argmax": lambda r: r.index(max(r)),
    }
    out = [funcs[op](r) for r in lines_]
    body = ",\n".join("    [" + ", ".join(str(v) for v in row) + "]" for row in m)
    code = (
        f"import numpy as np\n\n{name} = np.array([\n{body},\n])\nprint(*{name}.{op}(axis={axis}))"
    )
    return Variant(
        prompt=_PROMPT_NUMS,
        key=" ".join(map(str, out)),
        code=code,
        extra={"language": "python"},
        explanation=f"axis={axis}: {'по столбцам' if axis == 0 else 'по строкам'}.",
    )


NUMPY_AXIS = ItemTemplate(
    id="data_ml.numpy_axis",
    specialization="data_ml",
    topic="pandas_numpy",
    target_grade="intern",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_axis,
    a=1.2,
    b=-1.4,
    title="numpy: агрегаты по осям",
    time_limit_s=120,
)

# --------------------------------------------------------------------------- pandas: NaN

_NAN_EXPRS = ("len", "count", "isna", "sum", "mean", "fill_mean", "gt", "nunique", "dropna")


def _gen_pandas_nan(rng: random.Random) -> Variant:
    name = rng.choice(("s", "price", "age", "score", "qty"))
    while True:
        n = rng.randint(5, 7)
        k_nan = rng.randint(1, 3)
        vals: list[int | None] = [rng.randint(1, 12) for _ in range(n - k_nan)]
        if rng.random() < 0.6:
            vals[-1] = vals[0]  # повтор значения — для nunique
        for _ in range(k_nan):
            vals.insert(rng.randrange(len(vals) + 1), None)
        exprs = rng.sample(_NAN_EXPRS, 3)
        if not set(exprs) & {"count", "mean", "gt", "nunique", "fill_mean", "dropna", "isna"}:
            continue
        present = [v for v in vals if v is not None]
        total = sum(present)
        if "mean" in exprs and total % len(present):
            continue
        if "fill_mean" in exprs and total % n:
            continue
        break
    t = rng.choice(sorted(set(present)))
    results = {
        "len": (f"len({name})", n),
        "count": (f"{name}.count()", len(present)),
        "isna": (f"{name}.isna().sum()", n - len(present)),
        "sum": (f"int({name}.sum())", total),
        "mean": (f"int({name}.mean())", total // len(present)),
        "fill_mean": (f"int({name}.fillna(0).mean())", total // n),
        "gt": (f"({name} > {t}).sum()", sum(1 for v in present if v > t)),
        "nunique": (f"{name}.nunique()", len(set(present))),
        "dropna": (f"len({name}.dropna())", len(present)),
    }
    nan_word = rng.choice(("np.nan", "None"))
    lit = ", ".join(nan_word if v is None else str(v) for v in vals)
    code = (
        "import numpy as np\nimport pandas as pd\n\n"
        f"{name} = pd.Series([{lit}])\n"
        f"print({', '.join(results[e][0] for e in exprs)})"
    )
    return Variant(
        prompt=_PROMPT_NUMS,
        key=" ".join(str(results[e][1]) for e in exprs),
        code=code,
        extra={"language": "python"},
        explanation="Агрегаты pandas пропускают NaN; сравнение с NaN даёт False.",
    )


PANDAS_NAN = ItemTemplate(
    id="data_ml.pandas_nan",
    specialization="data_ml",
    topic="pandas_numpy",
    target_grade="junior",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_pandas_nan,
    a=1.4,
    b=-0.5,
    title="pandas: пропуски в агрегатах",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- numpy: broadcasting


def broadcast(a: tuple[int, ...], b: tuple[int, ...]) -> tuple[int, ...] | None:
    out: list[int] = []
    for i in range(1, max(len(a), len(b)) + 1):
        x = a[-i] if i <= len(a) else 1
        y = b[-i] if i <= len(b) else 1
        if x != y and 1 not in (x, y):
            return None
        out.append(max(x, y))
    return tuple(reversed(out))


def _shape_expr(fn: str, shape: tuple[int, ...]) -> str:
    if len(shape) == 1:
        return f"np.arange({shape[0]})" if fn == "arange" else f"np.{fn}({shape[0]})"
    inner = ", ".join(map(str, shape))
    if fn == "arange":
        size = 1
        for d in shape:
            size *= d
        return f"np.arange({size}).reshape({inner})"
    return f"np.{fn}(({inner}))"


def _shape_str(shape: tuple[int, ...]) -> str:
    return "(" + ", ".join(map(str, shape)) + ("," if len(shape) == 1 else "") + ")"


def _gen_broadcast(rng: random.Random) -> Variant:
    while True:
        res = tuple(rng.randint(2, 5) for _ in range(rng.choice((2, 2, 3))))

        def derive(full: tuple[int, ...]) -> tuple[int, ...]:
            start = rng.randrange(len(full))
            part = list(full[start:])
            for i in range(len(part)):
                if rng.random() < 0.45:
                    part[i] = 1
            return tuple(part)

        a, b = derive(res), derive(res)
        if rng.random() < 0.3:  # попытка сделать размерности несовместимыми
            bl = list(b)
            i = rng.randrange(len(bl))
            pos = len(bl) - i  # позиция оси справа, с 1
            other = a[-pos] if pos <= len(a) else 1
            bl[i] = rng.choice([v for v in range(2, 7) if v != other])
            b = tuple(bl)
        out = broadcast(a, b)
        if out is not None and len(out) < 2:
            continue
        if a == b or 1 in (math.prod(a), math.prod(b)):
            continue
        break
    va, vb = rng.choice((("a", "b"), ("x", "w"), ("left", "right"), ("u", "v")))
    op = rng.choice(("+", "*", "-"))
    code = (
        "import numpy as np\n\n"
        f"{va} = {_shape_expr(rng.choice(('zeros', 'ones', 'arange')), a)}\n"
        f"{vb} = {_shape_expr(rng.choice(('zeros', 'ones', 'arange')), b)}\n"
        f"c = {va} {op} {vb}\n"
        "print(c.shape)"
    )
    key = "error" if out is None else _shape_str(out)
    return Variant(
        prompt=(
            "Что выведет код? Запишите ответ так, как его напечатает Python, например (2, 5). "
            "Если строка с операцией упадёт с ошибкой — напишите error."
        ),
        key=key,
        code=code,
        extra={"language": "python"},
        explanation=f"Формы {a} и {b}: {key}.",
    )


NUMPY_BROADCAST = ItemTemplate(
    id="data_ml.numpy_broadcasting",
    specialization="data_ml",
    topic="pandas_numpy",
    target_grade="junior",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_broadcast,
    a=1.4,
    b=-0.2,
    title="numpy: broadcasting форм",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- pandas: groupby

_CITIES = ("Kazan", "Omsk", "Perm", "Sochi", "Tula", "Ufa", "Samara", "Tomsk")
_PRODUCTS = ("tea", "milk", "bread", "cheese", "juice")


def _gen_groupby(rng: random.Random) -> Variant:
    kind = rng.choice(("idxmax", "sorted_max", "size_count", "nunique", "share", "top2"))
    while True:
        cities = rng.sample(_CITIES, 3)
        n = rng.randint(6, 9)
        city_col = [rng.choice(cities) for _ in range(n)]
        if len(set(city_col)) < 3 or city_col == sorted(city_col):
            continue
        prod_col = [rng.choice(_PRODUCTS) for _ in range(n)]
        sales: list[int | None] = [rng.randint(1, 40) for _ in range(n)]
        groups = sorted(set(city_col))
        if kind == "size_count":
            for i in rng.sample(range(n), rng.randint(1, 2)):
                sales[i] = None
        present = {g: [s for c, s in zip(city_col, sales, strict=True) if c == g] for g in groups}
        sums = {g: sum(v for v in present[g] if v is not None) for g in groups}
        if kind in ("idxmax", "top2") and len(set(sums.values())) < len(groups):
            continue
        if kind == "nunique":
            nun = {
                g: len({p for c, p in zip(city_col, prod_col, strict=True) if c == g})
                for g in groups
            }
            multi = [g for g in groups if nun[g] > 1]
            if not multi or len(multi) == len(groups):
                continue
        if kind == "share":
            shares = [s / sums[c] for c, s in zip(city_col, sales, strict=True) if s is not None]
            if any(abs(x - 0.5) < 1e-9 for x in shares):
                continue
        break
    head = ["import numpy as np", "import pandas as pd", ""]

    def col(vals: list[str] | list[int | None]) -> str:
        return ", ".join(
            "np.nan" if v is None else (f'"{v}"' if isinstance(v, str) else str(v)) for v in vals
        )

    df = [
        "df = pd.DataFrame({",
        f'    "city": [{col(city_col)}],',
        f'    "product": [{col(prod_col)}],',
        f'    "sales": [{col(sales)}],',
        "})",
    ]
    if kind == "idxmax":
        body = ['res = df.groupby("city")["sales"].sum()', "print(res.idxmax(), res.max())"]
        best = max(groups, key=lambda g: sums[g])
        out = [best, str(sums[best])]
    elif kind == "sorted_max":
        body = ['print(*df.groupby("city")["sales"].max().tolist())']
        out = [str(max(v for v in present[g] if v is not None)) for g in groups]
    elif kind == "size_count":
        g = rng.choice([g for g in groups if None in present[g]] or groups)
        body = ['g = df.groupby("city")["sales"]', f'print(g.size()["{g}"], g.count()["{g}"])']
        out = [str(len(present[g])), str(sum(1 for v in present[g] if v is not None))]
    elif kind == "nunique":
        body = ['res = df.groupby("city")["product"].nunique()', "print(*res[res > 1].index)"]
        out = multi
    elif kind == "share":
        body = [
            'df["share"] = df["sales"] / df.groupby("city")["sales"].transform("sum")',
            'print((df["share"] > 0.5).sum())',
        ]
        out = [str(sum(1 for x in shares if x > 0.5))]
    else:
        body = [
            'res = df.groupby("city").agg(total=("sales", "sum"), n=("sales", "size"))',
            'print(*res.sort_values("total", ascending=False).index[:2])',
        ]
        out = sorted(groups, key=lambda g: -sums[g])[:2]
    return Variant(
        prompt=_PROMPT_NUMS,
        key=" ".join(out),
        code="\n".join(head + df + body),
        extra={"language": "python"},
        explanation=f"Вид: {kind}. groupby сортирует ключи групп по умолчанию.",
    )


PANDAS_GROUPBY = ItemTemplate(
    id="data_ml.pandas_groupby",
    specialization="data_ml",
    topic="pandas_numpy",
    target_grade="middle",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_groupby,
    a=1.5,
    b=0.4,
    title="pandas: groupby и агрегаты",
    time_limit_s=210,
)

# --------------------------------------------------------------------------- numpy: view или copy

_Op = tuple[list[str], Callable[[list[int]], None], bool]


def _view_ops(rng: random.Random, n: int) -> list[_Op]:
    v1, v2, v3 = rng.sample((0, -1, 99, 100, 7, 42, 500), 3)
    i = rng.randrange(0, n - 2)
    j = rng.randrange(i + 2, n + 1)
    k = rng.randrange(n)
    ops: list[_Op] = []

    def set_at(idx: int, val: int) -> Callable[[list[int]], None]:
        def f(a: list[int]) -> None:
            a[idx] = val

        return f

    def noop(a: list[int]) -> None:
        return None

    ops.append(([f"b = a[{i}:{j}]", f"b[0] = {v1}"], set_at(i, v1), True))
    ops.append(([f"c = a[[{i}, {k}]]", f"c[0] = {v2}"], noop, False))
    ops.append(([f"d = a[{i}:{j}].copy()", f"d[0] = {v3}"], noop, False))
    ops.append((["e = a[::2]", f"e[1] = {v2}"], set_at(2, v2), True))
    t = rng.randint(3, 8)

    def mask_assign(a: list[int]) -> None:
        for idx, x in enumerate(a):
            if x > t:
                a[idx] = 0

    ops.append(([f"f = a[a > {t}]", "f[:] = 0"], noop, False))
    ops.append(([f"a[a > {t}] = 0"], mask_assign, True))
    ops.append(([f"g = a[{i}:{j}]", "g = g * 10"], noop, False))

    def inplace(a: list[int]) -> None:
        for idx in range(i, j):
            a[idx] *= 10

    ops.append(([f"h = a[{i}:{j}]", "h *= 10"], inplace, True))
    if n == 6:
        ops.append(
            (["r = a.reshape(2, 3)", f"r[1, 0] = {v3}"], set_at(3, v3), True),
        )
    ops.append((["z = a", f"z[{k}] = {v1}"], set_at(k, v1), True))
    return ops


def _gen_view_copy(rng: random.Random) -> Variant:
    n = rng.choice((5, 6, 6, 7))
    base = rng.sample(range(1, 10), n)
    while True:
        chosen = rng.sample(_view_ops(rng, n), 3)
        if any(c[2] for c in chosen) and not all(c[2] for c in chosen):
            break
    a = list(base)
    lines = ["import numpy as np", "", f"a = np.array([{', '.join(map(str, base))}])"]
    for code_lines, apply, _ in chosen:
        lines += code_lines
        apply(a)
    lines.append("print(*a)")
    return Variant(
        prompt=_PROMPT_NUMS,
        key=" ".join(map(str, a)),
        code="\n".join(lines),
        extra={"language": "python"},
        explanation="Срезы — представления (view); индексация списком и маской — копии.",
    )


NUMPY_VIEW_COPY = ItemTemplate(
    id="data_ml.numpy_view_copy",
    specialization="data_ml",
    topic="pandas_numpy",
    target_grade="middle",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_view_copy,
    a=1.6,
    b=0.8,
    title="numpy: представление или копия",
    time_limit_s=210,
)

TEMPLATES = [NUMPY_AXIS, PANDAS_NAN, NUMPY_BROADCAST, PANDAS_GROUPBY, NUMPY_VIEW_COPY]
