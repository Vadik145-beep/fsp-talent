"""Backend · SQL: WHERE и NULL, GROUP BY/HAVING, оконные функции, индексы, изоляция транзакций."""

from __future__ import annotations

import random
from typing import Any

from ...templates import (
    ItemFormat,
    ItemTemplate,
    NumericKey,
    Variant,
    make_multi_choice,
    make_single_choice,
)
from ._common import PERSON_NAMES, sql_value, text_table


def _render_tables(tables: list[tuple[str, list[str], list[list[Any]]]], sql: str) -> str:
    """Таблицы с данными и запрос: «-- имя», таблица, пустая строка, …, SQL последним блоком."""
    blocks = []
    for name, header, rows in tables:
        body = text_table(header, [[sql_value(v) for v in r] for r in rows])
        blocks.append(f"-- {name}\n{body}")
    return "\n\n".join([*blocks, sql])


# ------------------------------------------------------------ WHERE, AND/OR, NULL

_CATALOGS = (
    ("products", ("books", "games", "music", "toys")),
    ("goods", ("food", "drinks", "snacks", "tea")),
    ("items", ("phones", "laptops", "tablets", "watches")),
)
_ITEM_NAMES = ("alpha", "bravo", "delta", "echo", "gamma", "kappa", "lima", "omega", "sigma")


def _gen_where(rng: random.Random) -> Variant:
    table, cats = rng.choice(_CATALOGS)
    n = rng.randint(7, 10)
    names = rng.sample(_ITEM_NAMES, min(n, len(_ITEM_NAMES)))
    while len(names) < n:
        names.append(f"{rng.choice(_ITEM_NAMES)}{len(names)}")
    kind = rng.choice(("or_and", "paren", "between", "ne_null", "eq_null", "not_in", "in_and"))
    with_null_cat = kind == "not_in"
    rows: list[list[Any]] = []
    for i in range(n):
        cat: str | None = rng.choice(cats)
        if with_null_cat and rng.random() < 0.25:
            cat = None
        price = rng.choice((90, 150, 200, 250, 300, 450, 500, 700, 900))
        stock = None if rng.random() < 0.25 else rng.choice((0, 0, 3, 5, 12, 20))
        rows.append([i + 1, names[i], cat, price, stock])
    x, y = rng.sample(cats, 2)
    p = rng.choice((150, 200, 300, 450, 500))
    if kind == "or_and":
        cond = f"category = '{x}' OR category = '{y}' AND price > {p}"

        def pred(r: list[Any]) -> bool:
            return bool(r[2] == x or (r[2] == y and r[3] > p))
    elif kind == "paren":
        cond = f"(category = '{x}' OR category = '{y}') AND price > {p}"

        def pred(r: list[Any]) -> bool:
            return bool(r[2] in (x, y) and r[3] > p)
    elif kind == "between":
        prices = sorted({r[3] for r in rows})
        lo = rng.choice(prices[: max(1, len(prices) // 2)])
        hi = rng.choice([v for v in prices if v > lo] or [lo])
        cond = f"price BETWEEN {lo} AND {hi}"

        def pred(r: list[Any]) -> bool:
            return bool(lo <= r[3] <= hi)
    elif kind == "ne_null":
        cond = "stock <> 0"

        def pred(r: list[Any]) -> bool:
            return bool(r[4] is not None and r[4] != 0)
    elif kind == "eq_null":
        cond = f"category = '{x}' OR stock = NULL"

        def pred(r: list[Any]) -> bool:
            return bool(r[2] == x)
    elif kind == "not_in":
        cond = f"category NOT IN ('{x}', '{y}')"

        def pred(r: list[Any]) -> bool:
            return bool(r[2] is not None and r[2] not in (x, y))
    else:
        cond = f"category IN ('{x}', '{y}') AND stock > 0"

        def pred(r: list[Any]) -> bool:
            return bool(r[2] in (x, y) and r[4] is not None and r[4] > 0)

    answer = sum(1 for r in rows if pred(r))
    sql = f"SELECT id, name\nFROM {table}\nWHERE {cond};"
    code = _render_tables([(table, ["id", "name", "category", "price", "stock"], rows)], sql)
    return Variant(
        prompt="Сколько строк вернёт запрос? (PostgreSQL)",
        key=NumericKey(answer, 0),
        code=code,
        extra={"language": "sql", "answer_type": "integer"},
        explanation=f"Условие {kind}: {answer} строк.",
    )


SQL_WHERE = ItemTemplate(
    id="backend.sql_where_filter",
    specialization="backend",
    topic="sql",
    target_grade="intern",
    format=ItemFormat.NUMERIC,
    generator=_gen_where,
    a=1.1,
    b=-1.2,
    title="Сколько строк отберёт WHERE",
    time_limit_s=180,
)

# ------------------------------------------------------------ GROUP BY / HAVING


def _agg_value(fn: str, amounts: list[int]) -> int:
    if fn == "COUNT(*)":
        return len(amounts)
    if fn == "SUM(amount)":
        return sum(amounts)
    return max(amounts)


def _compare(v: int, op: str, threshold: int) -> bool:
    return v >= threshold if op == ">=" else v > threshold


def _gen_group_having(rng: random.Random) -> Variant:
    table = rng.choice(("orders", "payments", "invoices"))
    customers = rng.sample(PERSON_NAMES, rng.randint(3, 5))
    statuses = ("paid", "new", "cancelled")
    while True:
        n = rng.randint(8, 12)
        rows: list[list[Any]] = [
            [
                i + 1,
                rng.choice(customers),
                rng.choice((*statuses, "paid")),
                rng.choice((100, 200, 250, 300, 400, 500, 800)),
            ]
            for i in range(n)
        ]
        where_kind = rng.choice(("none", "paid", "not_cancelled"))
        agg = rng.choice(("COUNT(*)", "SUM(amount)", "MAX(amount)"))
        having_agg = rng.choice(("COUNT(*)", "SUM(amount)", agg))
        if where_kind == "paid":
            where, kept = "WHERE status = 'paid'\n", [r for r in rows if r[2] == "paid"]
        elif where_kind == "not_cancelled":
            where = "WHERE status <> 'cancelled'\n"
            kept = [r for r in rows if r[2] != "cancelled"]
        else:
            where, kept = "", rows
        groups: dict[str, list[int]] = {}
        for r in kept:
            groups.setdefault(r[1], []).append(r[3])

        if len(groups) < 2:
            continue
        hvals = sorted({_agg_value(having_agg, a) for a in groups.values()})
        if len(hvals) < 2:
            continue
        threshold = rng.choice(hvals[1:])
        op = rng.choice((">=", ">"))
        if op == ">":
            threshold = hvals[hvals.index(threshold) - 1]
        result = [
            (c, _agg_value(agg, a))
            for c, a in sorted(groups.items())
            if _compare(_agg_value(having_agg, a), op, threshold)
        ]
        if result and len(result) < len(groups):
            break
    sql = (
        f"SELECT customer, {agg}\nFROM {table}\n{where}GROUP BY customer\n"
        f"HAVING {having_agg} {op} {threshold}\nORDER BY customer;"
    )
    code = _render_tables([(table, ["id", "customer", "status", "amount"], rows)], sql)
    return Variant(
        prompt=(
            "Что вернёт запрос (PostgreSQL)? Запишите значения всех строк результата по порядку "
            "через пробел: строка за строкой, в каждой — слева направо."
        ),
        key=" ".join(f"{c} {v}" for c, v in result),
        code=code,
        extra={"language": "sql"},
        explanation="WHERE фильтрует строки до группировки, HAVING — группы после неё.",
    )


SQL_GROUP_HAVING = ItemTemplate(
    id="backend.sql_group_having",
    specialization="backend",
    topic="sql",
    target_grade="junior",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_group_having,
    a=1.3,
    b=-0.4,
    title="GROUP BY, WHERE и HAVING",
    time_limit_s=240,
)

# ------------------------------------------------------------ оконные функции


def _ranks(values: list[int], dense: bool) -> list[int]:
    """RANK/DENSE_RANK для значений, уже упорядоченных по убыванию."""
    out: list[int] = []
    for i, v in enumerate(values):
        if i and v == values[i - 1]:
            out.append(out[-1])
        elif dense:
            out.append(out[-1] + 1 if out else 1)
        else:
            out.append(i + 1)
    return out


def _gen_window(rng: random.Random) -> Variant:
    kind = rng.choice(("rank", "dense", "rownum_part", "rank_part", "running", "running_rows"))
    if kind in ("running", "running_rows"):
        n = rng.randint(5, 7)
        while True:
            days = sorted(rng.choice((1, 2, 3, 4, 5)) for _ in range(n))
            if len(set(days)) < n and len(set(days)) >= 3:
                break
        rows: list[list[Any]] = [
            [i + 1, days[i], rng.choice((10, 20, 30, 40, 50, 70))] for i in range(n)
        ]
        table = rng.choice(("sales", "payments", "visits"))
        if kind == "running":
            win = "SUM(amount) OVER (ORDER BY day)"
            out = [sum(r[2] for r in rows if r[1] <= row[1]) for row in rows]
        else:
            win = (
                "SUM(amount) OVER (ORDER BY day, id\n"
                "                         ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)"
            )
            out = [sum(r[2] for r in rows[: i + 1]) for i in range(n)]
        sql = f"SELECT id, day, amount,\n       {win} AS r\nFROM {table}\nORDER BY day, id;"
        code = _render_tables([(table, ["id", "day", "amount"], rows)], sql)
    else:
        n = rng.randint(6, 8)
        players = rng.sample(PERSON_NAMES, n)
        teams = rng.sample(("red", "blue", "green"), 2)
        while True:
            points = [rng.choice((10, 20, 20, 30, 30, 40, 50)) for _ in range(n)]
            team_of = [rng.choice(teams) for _ in range(n)]
            if len(set(points)) < n and len(set(team_of)) == 2:
                break
        rows = [[i + 1, players[i], team_of[i], points[i]] for i in range(n)]
        table = rng.choice(("scores", "results", "ratings"))
        if kind in ("rank", "dense"):
            fn = "RANK()" if kind == "rank" else "DENSE_RANK()"
            win = f"{fn} OVER (ORDER BY points DESC)"
            order = sorted(rows, key=lambda r: (-r[3], r[1]))
            out = _ranks([r[3] for r in order], dense=kind == "dense")
            outer = "ORDER BY points DESC, player"
        else:
            if kind == "rownum_part":
                win = "ROW_NUMBER() OVER (PARTITION BY team ORDER BY points DESC, player)"
            else:
                win = "RANK() OVER (PARTITION BY team ORDER BY points DESC)"
            order = sorted(rows, key=lambda r: (r[2], -r[3], r[1]))
            out = []
            for t in sorted(set(team_of)):
                part = [r[3] for r in order if r[2] == t]
                if kind == "rownum_part":
                    out += list(range(1, len(part) + 1))
                else:
                    out += _ranks(part, dense=False)
            outer = "ORDER BY team, points DESC, player"
        sql = f"SELECT player, team, points,\n       {win} AS r\nFROM {table}\n{outer};"
        code = _render_tables([(table, ["id", "player", "team", "points"], rows)], sql)
    return Variant(
        prompt=(
            "Какие значения будут в столбце r результата (PostgreSQL)? "
            "Запишите их по порядку строк результата через пробел."
        ),
        key=" ".join(map(str, out)),
        code=code,
        extra={"language": "sql"},
        explanation=f"Оконная функция ({kind}).",
    )


SQL_WINDOW = ItemTemplate(
    id="backend.sql_window_rank",
    specialization="backend",
    topic="sql",
    target_grade="middle",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_window,
    a=1.4,
    b=0.6,
    title="Оконные функции: ранги и нарастающий итог",
    time_limit_s=240,
)

# ------------------------------------------------------------ использование индекса

_INDEX_COLS = {
    "customer_id": ("42", "17", "7"),
    "status": ("'paid'", "'new'", "'shipped'"),
    "created_at": ("'2026-03-01'", "'2026-05-15'", "'2026-09-30'"),
}
_FUNC = {
    "customer_id": "abs(customer_id)",
    "status": "lower(status)",
    "created_at": "substr(created_at, 1, 10)",
}


def _gen_index_usage(rng: random.Random) -> Variant:
    cols = rng.sample(list(_INDEX_COLS), rng.choice((2, 2, 3)))
    c1, c2 = cols[0], cols[1]
    c3 = cols[2] if len(cols) == 3 else None
    idx = rng.choice(("idx_orders", "orders_idx", "ix_orders_search"))

    def val(c: str) -> str:
        return rng.choice(_INDEX_COLS[c])

    preds: list[tuple[str, bool]] = [
        (f"{c1} = {val(c1)}", True),
        (f"{c2} = {val(c2)}", False),
        (f"{c1} = {val(c1)} AND {c2} = {val(c2)}", True),
        (f"{c2} = {val(c2)} AND {c1} = {val(c1)}", True),
        (f"{c1} > {val(c1)}", True),
        (f"{_FUNC[c1]} = {val(c1)}", False),
        (f"{c1} = {val(c1)} OR {c2} = {val(c2)}", False),
        (f"{c1} <> {val(c1)}", False),
        (f"{c1} IN ({', '.join(rng.sample(_INDEX_COLS[c1], 2))})", True),
        ("amount > 1000", False),
        (f"{c1} = {val(c1)} AND amount > 1000", True),
    ]
    if c3:
        preds += [
            (f"{c2} = {val(c2)} AND {c3} = {val(c3)}", False),
            (f"{c1} = {val(c1)} AND {c3} = {val(c3)}", True),
        ]
    # одинаковые формулировки (например, два «c1 = …» с одним значением) склеиваем
    seen: dict[str, bool] = {}
    for p, ok in preds:
        seen.setdefault(p, ok)
    items = list(seen.items())
    while True:
        chosen = rng.sample(items, 5)
        if any(ok for _, ok in chosen) and not all(ok for _, ok in chosen):
            break
    correct = [f"WHERE {p}" for p, ok in chosen if ok]
    wrong = [f"WHERE {p}" for p, ok in chosen if not ok]
    code = (
        "CREATE TABLE orders (\n"
        "    id          INTEGER PRIMARY KEY,\n"
        "    customer_id INTEGER,\n"
        "    status      TEXT,\n"
        "    created_at  TEXT,\n"
        "    amount      INTEGER,\n"
        "    comment     TEXT\n"
        ");\n"
        f"CREATE INDEX {idx} ON orders ({', '.join(cols)});\n\n"
        "-- запросы вида: SELECT * FROM orders <условие>;"
    )
    return make_multi_choice(
        rng,
        "База — SQLite, статистика (ANALYZE) не собиралась. Для каких условий SQLite найдёт "
        f"строки поиском по индексу {idx} (в EXPLAIN QUERY PLAN будет SEARCH … USING INDEX), "
        "а не полным перебором таблицы? Отметьте все такие.",
        correct,
        wrong,
        code=code,
        extra={"language": "sql"},
        explanation="Составной индекс работает по левому префиксу; функции над столбцом, "
        "<> и OR с неиндексированной частью мешают поиску.",
    )


SQL_INDEX_USAGE = ItemTemplate(
    id="backend.sql_index_usage",
    specialization="backend",
    topic="sql",
    target_grade="middle",
    format=ItemFormat.MULTI_CHOICE,
    generator=_gen_index_usage,
    a=1.3,
    b=0.7,
    title="Когда сработает составной индекс",
    time_limit_s=240,
)

# ------------------------------------------------------------ уровни изоляции PostgreSQL

_LEVELS = ("READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE")


def isolation_read_value(level: str, first_query: str, t2_end: str, b0: int, d: int) -> int:
    """Что вернёт отмеченный SELECT в T1 (модель MVCC PostgreSQL).

    first_query — когда T1 выполнила первый запрос: before (до UPDATE в T2), between (после
    UPDATE, до завершения T2), after (после завершения T2), none (отмеченный SELECT — первый).
    t2_end — commit / rollback / open (T2 ещё не завершена).
    """
    if t2_end != "commit":
        return b0
    if level == "READ COMMITTED":
        return b0 + d
    # REPEATABLE READ / SERIALIZABLE: снимок берётся при первом запросе транзакции
    return b0 if first_query in ("before", "between") else b0 + d


def _make_isolation(rng: random.Random) -> tuple[Variant, dict[str, Any]]:
    level = rng.choice(_LEVELS)
    first_query = rng.choice(("before", "between", "after", "none"))
    t2_end = rng.choice(("commit", "commit", "rollback", "open"))
    if first_query == "after" and t2_end == "open":
        first_query = "between"
    table, col = rng.choice((("accounts", "balance"), ("wallets", "amount"), ("stock", "qty")))
    row_id = rng.randint(1, 9)
    b0 = rng.choice((100, 200, 500, 1000, 1500))
    d = rng.choice((-50, -30, 20, 40, 70, 150))
    first_sql = rng.choice(
        (f"SELECT {col} FROM {table} WHERE id = {row_id};", "SELECT count(*) FROM orders;")
    )
    sign = "+" if d > 0 else "-"
    steps: list[str] = [f"T1: BEGIN ISOLATION LEVEL {level};"]
    if first_query == "before":
        steps.append(f"T1: {first_sql}")
    steps += [
        "T2: BEGIN;",
        f"T2: UPDATE {table} SET {col} = {col} {sign} {abs(d)} WHERE id = {row_id};",
    ]
    if first_query == "between":
        steps.append(f"T1: {first_sql}")
    if t2_end == "commit":
        steps.append("T2: COMMIT;")
    elif t2_end == "rollback":
        steps.append("T2: ROLLBACK;")
    if first_query == "after":
        steps.append(f"T1: {first_sql}")
    steps.append(f"T1: SELECT {col} FROM {table} WHERE id = {row_id};   -- (?)")
    code = "\n".join(f"{i + 1:>2}. {s}" for i, s in enumerate(steps))
    answer = isolation_read_value(level, first_query, t2_end, b0, d)
    other = b0 + d if answer == b0 else b0
    opts = {
        str(answer),
        str(other),
        "Ошибка: could not serialize access due to concurrent update",
        "Запрос будет ждать завершения T2 (строка заблокирована)",
    }
    correct = str(answer)
    variant = make_single_choice(
        rng,
        f"PostgreSQL 16. В таблице {table} у строки id = {row_id} значение {col} = {b0}. "
        "Две сессии выполняют команды строго в указанном порядке. Что вернёт отмеченный "
        "SELECT в T1?",
        correct,
        sorted(opts - {correct}),
        code=code,
        extra={"language": "sql"},
        explanation=(
            "В PostgreSQL нет грязного чтения; READ COMMITTED видит коммиты на начало каждого "
            "запроса, REPEATABLE READ и SERIALIZABLE — снимок на момент первого запроса "
            "транзакции (не BEGIN). Чтение не блокируется записью."
        ),
    )
    data = {
        "level": level,
        "steps": steps,
        "table": table,
        "col": col,
        "row_id": row_id,
        "b0": b0,
        "answer": answer,
    }
    return variant, data


SQL_ISOLATION = ItemTemplate(
    id="backend.sql_isolation_read",
    specialization="backend",
    topic="sql",
    target_grade="senior",
    format=ItemFormat.SINGLE_CHOICE,
    generator=lambda rng: _make_isolation(rng)[0],
    a=1.5,
    b=1.4,
    title="Что увидит транзакция при разных уровнях изоляции",
    time_limit_s=240,
)

TEMPLATES = [SQL_WHERE, SQL_GROUP_HAVING, SQL_WINDOW, SQL_INDEX_USAGE, SQL_ISOLATION]
