"""Backend: сложность алгоритма (single_choice), SQL JOIN (numeric)."""

from __future__ import annotations

import random

from ..templates import ItemFormat, ItemTemplate, NumericKey, Variant, make_single_choice

# --------------------------------------------------------------------------- сложность алгоритма

# Стоимость цикла: (степень n, степень log n)
_LoopSpec = tuple[str, int, str]  # (вид, параметр, имя переменной)

_FUNC_NAMES = ("process", "calc", "aggregate", "score", "scan", "build_index", "count_pairs")
_VAR_SETS = (("i", "j", "k"), ("a", "b", "c"), ("x", "y", "z"), ("row", "col", "step"))


_SUP = {2: "²", 3: "³", 4: "⁴"}


def _complexity_label(p: int, lg: int) -> str:
    if p == 0 and lg == 0:
        return "O(1)"
    parts = []
    if p == 1:
        parts.append("n")
    elif p > 1:
        parts.append(f"n{_SUP[p]}")
    if lg == 1:
        parts.append("log n")
    elif lg > 1:
        parts.append(f"log{_SUP[lg]} n")
    return "O(" + " ".join(parts) + ")"


def _render_loops(loops: list[_LoopSpec], body: str, indent: int) -> list[str]:
    lines: list[str] = []

    def rec(idx: int, ind: int, outer_var: str | None) -> None:
        sp = "    " * ind
        if idx == len(loops):
            lines.append(sp + body)
            return
        kind, param, var = loops[idx]
        if kind == "const":
            lines.append(f"{sp}for {var} in range({param}):")
            rec(idx + 1, ind + 1, var)
        elif kind == "linear":
            head = "range(n)" if param == 1 else f"range(0, n, {param})"
            lines.append(f"{sp}for {var} in {head}:")
            rec(idx + 1, ind + 1, var)
        elif kind == "dep":
            lines.append(f"{sp}for {var} in range({outer_var}):")
            rec(idx + 1, ind + 1, var)
        elif kind == "log":
            lines.append(f"{sp}{var} = 1")
            lines.append(f"{sp}while {var} < n:")
            rec(idx + 1, ind + 1, var)
            lines.append(f"{sp}    {var} *= {param}")
        elif kind == "half":
            lines.append(f"{sp}{var} = n")
            lines.append(f"{sp}while {var} > 0:")
            rec(idx + 1, ind + 1, var)
            lines.append(f"{sp}    {var} //= {param}")
        else:  # pragma: no cover - защитная ветка
            raise ValueError(kind)

    rec(0, indent, None)
    return lines


_COST = {"const": (0, 0), "linear": (1, 0), "dep": (1, 0), "log": (0, 1), "half": (0, 1)}


def _gen_complexity(rng: random.Random) -> Variant:
    names = rng.choice(_VAR_SETS)
    depth = rng.choice((1, 2, 2, 3))
    loops: list[_LoopSpec] = []
    for level in range(depth):
        kinds = ["const", "linear", "linear", "log", "half"]
        if level > 0 and loops[-1][0] == "linear":
            kinds.append("dep")
        kind = rng.choice(kinds)
        if kind == "const":
            param = rng.choice((3, 10, 26, 100, 1000))
        elif kind == "linear":
            param = rng.choice((1, 1, 2, 3))
        elif kind in ("log", "half"):
            param = rng.choice((2, 2, 3))
        else:
            param = 0
        loops.append((kind, param, names[level]))
    # хотя бы один цикл зависит от n — иначе вопрос тривиален
    if all(k == "const" for k, _, _ in loops):
        loops[0] = ("linear", 1, names[0])
    p = sum(_COST[k][0] for k, _, _ in loops)
    lg = sum(_COST[k][1] for k, _, _ in loops)
    used = ", ".join(v for _, _, v in loops)
    body = f"total += items[{loops[-1][2]} % n]" if rng.random() < 0.5 else f"total += 1  # {used}"

    lines = [f"def {rng.choice(_FUNC_NAMES)}(items):", "    n = len(items)", "    total = 0"]
    # иногда перед основной частью есть сортировка: O(n log n)
    if rng.random() < 0.35:
        lines.append("    items = sorted(items)")
        if (p, lg) < (1, 1):
            p, lg = 1, 1
    lines += _render_loops(loops, body, indent=1)
    lines.append("    return total")
    code = "\n".join(lines)

    correct = _complexity_label(p, lg)
    neighbours = set()
    for dp, dl in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1), (1, 1), (2, 0)):
        q, m = p + dp, lg + dl
        if 0 <= q <= 4 and 0 <= m <= 3 and (q, m) != (p, lg):
            neighbours.add(_complexity_label(q, m))
    distractors = sorted(neighbours)
    return make_single_choice(
        rng,
        "Какова временная сложность функции по n = len(items)? "
        "Считайте, что арифметика и обращение к элементу списка — O(1).",
        correct,
        distractors,
        code=code,
        extra={"language": "python"},
        explanation=f"Перемножаем стоимость вложенных циклов: {correct}.",
    )


ALGO_COMPLEXITY = ItemTemplate(
    id="backend.algo_complexity",
    specialization="backend",
    topic="algorithms",
    target_grade="junior",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_complexity,
    a=1.3,
    b=-0.5,
    title="Временная сложность фрагмента кода",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- SQL JOIN

_SCHEMAS = (
    # (родитель, псевдоним, имя-колонка, ребёнок, псевдоним, внешний ключ, числовая колонка)
    ("customers", "c", "name", "orders", "o", "customer_id", "amount"),
    ("authors", "a", "name", "books", "b", "author_id", "pages"),
    ("departments", "d", "title", "employees", "e", "department_id", "salary"),
    ("users", "u", "login", "sessions", "s", "user_id", "duration"),
    ("projects", "p", "code", "tasks", "t", "project_id", "points"),
)
_NAMES = ("anna", "boris", "vera", "gleb", "dina", "egor", "zoya", "ilya", "kira", "lev")


def _table(header: list[str], rows: list[list[str]]) -> str:
    widths = [
        max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(header)
    ]
    out = [" | ".join(h.ljust(w) for h, w in zip(header, widths, strict=True))]
    out.append("-+-".join("-" * w for w in widths))
    out += [" | ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)) for r in rows]
    return "\n".join(out)


def _gen_sql_join(rng: random.Random) -> Variant:
    parent, pa, pcol, child, ca, fk, num = rng.choice(_SCHEMAS)
    n_parent = rng.randint(3, 6)
    parent_ids = sorted(rng.sample(range(1, 20), n_parent))
    parent_rows = [(pid, rng.choice(_NAMES)) for pid in parent_ids]
    n_child = rng.randint(4, 8)
    orphan_id = max(parent_ids) + rng.randint(1, 9)
    child_rows: list[tuple[int, int | None, int]] = []
    for cid in range(1, n_child + 1):
        r = rng.random()
        ref: int | None
        if r < 0.12:
            ref = None
        elif r < 0.22:
            ref = orphan_id
        else:
            ref = rng.choice(parent_ids[: max(2, n_parent - rng.randint(0, 2))])
        child_rows.append((100 + cid, ref, rng.choice((50, 80, 120, 150, 200, 300))))
    limit = rng.choice((100, 120, 150))

    def matches(pid: int, cond: bool = False) -> int:
        return sum(1 for _, ref, v in child_rows if ref == pid and (not cond or v > limit))

    unmatched_children = sum(1 for _, ref, _ in child_rows if ref not in parent_ids)
    kinds = ("inner", "left", "full", "anti", "left_on_filter", "left_where_filter", "distinct")
    kind = rng.choice(kinds)
    on = f"{ca}.{fk} = {pa}.id"
    sel = f"SELECT {pa}.{pcol}, {ca}.id"
    if kind == "inner":
        sql = f"{sel}\nFROM {parent} {pa}\nJOIN {child} {ca} ON {on};"
        answer = sum(matches(pid) for pid in parent_ids)
    elif kind == "left":
        sql = f"{sel}\nFROM {parent} {pa}\nLEFT JOIN {child} {ca} ON {on};"
        answer = sum(max(1, matches(pid)) for pid in parent_ids)
    elif kind == "full":
        sql = f"{sel}\nFROM {parent} {pa}\nFULL OUTER JOIN {child} {ca} ON {on};"
        answer = sum(max(1, matches(pid)) for pid in parent_ids) + unmatched_children
    elif kind == "anti":
        sql = (
            f"SELECT {pa}.{pcol}\nFROM {parent} {pa}\n"
            f"LEFT JOIN {child} {ca} ON {on}\nWHERE {ca}.id IS NULL;"
        )
        answer = sum(1 for pid in parent_ids if matches(pid) == 0)
    elif kind == "left_on_filter":
        sql = (
            f"{sel}\nFROM {parent} {pa}\nLEFT JOIN {child} {ca}\n"
            f"  ON {on} AND {ca}.{num} > {limit};"
        )
        answer = sum(max(1, matches(pid, True)) for pid in parent_ids)
    elif kind == "left_where_filter":
        sql = (
            f"{sel}\nFROM {parent} {pa}\nLEFT JOIN {child} {ca} ON {on}\n"
            f"WHERE {ca}.{num} > {limit};"
        )
        answer = sum(matches(pid, True) for pid in parent_ids)
    else:
        sql = f"SELECT COUNT(DISTINCT {pa}.id)\nFROM {parent} {pa}\nJOIN {child} {ca} ON {on};"
        answer = sum(1 for pid in parent_ids if matches(pid) > 0)

    t1 = _table(["id", pcol], [[str(i), nm] for i, nm in parent_rows])
    t2 = _table(
        ["id", fk, num],
        [[str(i), "NULL" if ref is None else str(ref), str(v)] for i, ref, v in child_rows],
    )
    code = f"-- {parent}\n{t1}\n\n-- {child}\n{t2}\n\n{sql}"
    if kind == "distinct":
        prompt = "Какое число вернёт запрос? (PostgreSQL)"
    else:
        prompt = "Сколько строк вернёт запрос? (PostgreSQL)"
    return Variant(
        prompt=prompt,
        key=NumericKey(answer, 0),
        code=code,
        extra={"language": "sql", "answer_type": "integer"},
        explanation=f"Тип запроса: {kind}; ответ {answer}.",
    )


SQL_JOIN = ItemTemplate(
    id="backend.sql_join_rows",
    specialization="backend",
    topic="sql",
    target_grade="middle",
    format=ItemFormat.NUMERIC,
    generator=_gen_sql_join,
    a=1.5,
    b=0.3,
    title="Сколько строк вернёт JOIN",
    time_limit_s=240,
)

TEMPLATES = [ALGO_COMPLEXITY, SQL_JOIN]
