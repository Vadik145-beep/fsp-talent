"""QA — SQL для тестировщика: NULL в условиях, поиск аномалий в данных, GROUP BY / HAVING."""

from __future__ import annotations

import random
from collections import Counter

from ...templates import ItemFormat, ItemTemplate, NumericKey, Variant, make_single_choice
from ._common import table

_NAMES = ("anna", "boris", "vera", "gleb", "dina", "egor", "zoya", "ilya", "kira", "lev", "mila")
_CITIES = ("Kazan", "Omsk", "Perm")

Cell = str | int | None


def render(name: str, header: list[str], rows: list[list[Cell]]) -> str:
    body = [["NULL" if v is None else str(v) for v in r] for r in rows]
    return f"-- {name}\n" + table(header, body)


# --------------------------------------------------------------------------- NULL в условиях


def _gen_where_null(rng: random.Random) -> Variant:
    kind = rng.randrange(7)
    while True:
        n = rng.randint(7, 10)
        names = rng.sample(_NAMES, n)
        rows: list[list[Cell]] = []
        for i, nm in enumerate(names):
            city = rng.choice((*_CITIES, None))
            disc = rng.choice((0, 5, 10, 15, None))
            rows.append([i + 1, nm, city, disc])
        cities = [r[2] for r in rows]
        discs = [r[3] for r in rows]
        if cities.count(None) and discs.count(None) and len(set(cities)) >= 3:
            break
    c1, c2 = rng.sample(_CITIES, 2)
    if kind == 0:
        sql = "SELECT COUNT(*) FROM users WHERE discount <> 0;"
        ans = sum(1 for d in discs if d is not None and d != 0)
    elif kind == 1:
        sql = f"SELECT COUNT(*) FROM users WHERE city <> '{c1}';"
        ans = sum(1 for c in cities if c is not None and c != c1)
    elif kind == 2:
        sql = "SELECT COUNT(discount) FROM users;"
        ans = sum(1 for d in discs if d is not None)
    elif kind == 3:
        sql = "SELECT COUNT(*) FROM users WHERE discount IS NULL OR discount = 0;"
        ans = sum(1 for d in discs if d is None or d == 0)
    elif kind == 4:
        sql = f"SELECT COUNT(*) FROM users WHERE city NOT IN ('{c1}', '{c2}');"
        ans = sum(1 for c in cities if c is not None and c not in (c1, c2))
    elif kind == 5:
        sql = "SELECT COUNT(DISTINCT city) FROM users;"
        ans = len({c for c in cities if c is not None})
    else:
        sql = f"SELECT COUNT(*) FROM users WHERE discount > 5 OR city = '{c1}';"
        ans = sum(
            1
            for c, d in zip(cities, discs, strict=True)
            if (isinstance(d, int) and d > 5) or c == c1
        )
    code = render("users", ["id", "name", "city", "discount"], rows) + f"\n\n{sql}"
    return Variant(
        prompt="Какое число вернёт запрос? (PostgreSQL)",
        key=NumericKey(ans, 0),
        code=code,
        extra={"language": "sql", "answer_type": "integer"},
        explanation=f"Сравнения с NULL дают UNKNOWN; ответ {ans}.",
    )


WHERE_NULL = ItemTemplate(
    id="qa.sql_where_null",
    specialization="qa",
    topic="sql",
    target_grade="junior",
    format=ItemFormat.NUMERIC,
    generator=_gen_where_null,
    a=1.4,
    b=-0.3,
    title="SQL: NULL в условиях и агрегатах",
    time_limit_s=180,
)

# --------------------------------------------------------------------------- какой запрос верный


def _dup_task(rng: random.Random) -> tuple[str, str, str, list[str]]:
    n = rng.randint(6, 8)
    pool = rng.sample(_NAMES, n - rng.randint(1, 2))
    emails = [f"{nm}@mail.ru" for nm in pool]
    while len(emails) < n:
        emails.append(rng.choice(emails[: len(pool)]))
    rng.shuffle(emails)
    if all(c == 1 for c in Counter(emails).values()):
        emails[-1] = emails[0]
    data = render("users", ["id", "email"], [[i + 1, e] for i, e in enumerate(emails)])
    return (
        "Найти email, которые встречаются в таблице users больше одного раза.",
        data,
        "SELECT email FROM users GROUP BY email HAVING COUNT(*) > 1;",
        [
            "SELECT email FROM users WHERE COUNT(*) > 1 GROUP BY email;",
            "SELECT DISTINCT email FROM users;",
            "SELECT email FROM users GROUP BY email HAVING COUNT(*) = 1;",
            "SELECT email, COUNT(*) FROM users GROUP BY email;",
        ],
    )


def _orphan_task(rng: random.Random) -> tuple[str, str, str, list[str]]:
    n = rng.randint(4, 6)
    names = rng.sample(_NAMES, n)
    lonely = rng.sample(range(1, n + 1), rng.randint(1, 2))
    with_orders = [i for i in range(1, n + 1) if i not in lonely]
    orders: list[list[Cell]] = [
        [100 + k, rng.choice(with_orders)] for k in range(rng.randint(3, 5))
    ]
    orders.insert(rng.randrange(len(orders) + 1), [199, None])
    for k, o in enumerate(orders):
        o[0] = 101 + k
    data = (
        render("customers", ["id", "name"], [[i + 1, nm] for i, nm in enumerate(names)])
        + "\n\n"
        + render("orders", ["id", "customer_id"], orders)
    )
    correct = rng.choice(
        (
            "SELECT c.name FROM customers c LEFT JOIN orders o ON o.customer_id = c.id "
            "WHERE o.id IS NULL;",
            "SELECT c.name FROM customers c WHERE NOT EXISTS "
            "(SELECT 1 FROM orders o WHERE o.customer_id = c.id);",
        )
    )
    return (
        "Найти имена клиентов, у которых нет ни одного заказа.",
        data,
        correct,
        [
            "SELECT name FROM customers WHERE id NOT IN (SELECT customer_id FROM orders);",
            "SELECT c.name FROM customers c JOIN orders o ON o.customer_id = c.id "
            "WHERE o.id IS NULL;",
            "SELECT c.name FROM customers c LEFT JOIN orders o ON o.customer_id = c.id "
            "WHERE o.customer_id IS NOT NULL;",
        ],
    )


def _second_salary_task(rng: random.Random) -> tuple[str, str, str, list[str]]:
    while True:
        n = rng.randint(5, 7)
        top = rng.choice(range(150, 301, 10)) * 1000
        sal = [top, top] + [rng.choice(range(60, 150, 5)) * 1000 for _ in range(n - 2)]
        rng.shuffle(sal)
        distinct = sorted(set(sal))
        # «вторая снизу» не должна случайно совпасть с правильным ответом
        if len(distinct) >= 3 and sorted(sal)[1] != distinct[-2]:
            break
    data = render(
        "employees",
        ["id", "name", "salary"],
        [[i + 1, nm, s] for i, (nm, s) in enumerate(zip(rng.sample(_NAMES, n), sal, strict=True))],
    )
    return (
        "Найти вторую по величине зарплату среди различных значений salary.",
        data,
        "SELECT MAX(salary) FROM employees WHERE salary < (SELECT MAX(salary) FROM employees);",
        [
            "SELECT salary FROM employees ORDER BY salary DESC LIMIT 1 OFFSET 1;",
            "SELECT salary FROM employees ORDER BY salary LIMIT 1 OFFSET 1;",
            "SELECT MAX(salary) FROM employees "
            "WHERE salary <= (SELECT MAX(salary) FROM employees);",
        ],
    )


def _gen_sql_choice(rng: random.Random) -> Variant:
    task, data, correct, wrong = rng.choice((_dup_task, _orphan_task, _second_salary_task))(rng)
    return make_single_choice(
        rng,
        f"Задача: {task} Какой запрос решает её правильно на любых данных? "
        "Пример данных — ниже (PostgreSQL).",
        correct,
        wrong,
        code=data,
        extra={"language": "sql"},
        explanation=f"Верно: {correct}",
    )


SQL_CHOICE = ItemTemplate(
    id="qa.sql_query_choice",
    specialization="qa",
    topic="sql",
    target_grade="middle",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_sql_choice,
    a=1.4,
    b=0.5,
    title="SQL: какой запрос находит аномалии",
    time_limit_s=210,
)

# --------------------------------------------------------------------------- GROUP BY / HAVING


def _gen_group_having(rng: random.Random) -> Variant:
    kind = rng.randrange(3)
    while True:
        custs = rng.sample(_NAMES, rng.randint(3, 4))
        n = rng.randint(7, 10)
        rows: list[list[Cell]] = []
        for i in range(n):
            rows.append(
                [
                    i + 1,
                    rng.choice(custs),
                    rng.choice(range(100, 2001, 50)),
                    rng.choice(("paid", "paid", "new", "cancelled")),
                ]
            )
        x = rng.choice(range(500, 3001, 250))
        out: list[str]
        if kind == 0:
            sql = (
                "SELECT customer\nFROM orders\nWHERE status = 'paid'\nGROUP BY customer\n"
                f"HAVING SUM(amount) > {x}\nORDER BY customer;"
            )
            sums: Counter[str] = Counter()
            for _, c, a, s in rows:
                if s == "paid":
                    sums[str(c)] += int(str(a))
            out = sorted(c for c, v in sums.items() if v > x)
        elif kind == 1:
            sql = (
                "SELECT customer\nFROM orders\nGROUP BY customer\nHAVING COUNT(*) >= 2\n"
                "ORDER BY SUM(amount) DESC;"
            )
            cnt = Counter(str(r[1]) for r in rows)
            tot: Counter[str] = Counter()
            for r in rows:
                tot[str(r[1])] += int(str(r[2]))
            chosen = [c for c in cnt if cnt[c] >= 2]
            if len({tot[c] for c in chosen}) < len(chosen):
                continue
            out = sorted(chosen, key=lambda c: -tot[c])
        else:
            sql = (
                f"SELECT customer, COUNT(*)\nFROM orders\nWHERE amount > {x // 2}\n"
                "GROUP BY customer\nORDER BY customer;"
            )
            cnt2 = Counter(str(r[1]) for r in rows if int(str(r[2])) > x // 2)
            out = [tok for c in sorted(cnt2) for tok in (c, str(cnt2[c]))]
        n_rows = len(out) if kind != 2 else len(out) // 2
        if 1 <= n_rows < len(custs):
            break
    code = render("orders", ["id", "customer", "amount", "status"], rows) + f"\n\n{sql}"
    return Variant(
        prompt=(
            "Что вернёт запрос? Перечислите значения через пробел: строка за строкой, "
            "в каждой строке столбцы слева направо (PostgreSQL)."
        ),
        key=" ".join(out),
        code=code,
        extra={"language": "sql"},
        explanation=f"Результат: {' '.join(out)}",
    )


GROUP_HAVING = ItemTemplate(
    id="qa.sql_group_having",
    specialization="qa",
    topic="sql",
    target_grade="middle",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_group_having,
    a=1.3,
    b=0.2,
    title="SQL: результат GROUP BY и HAVING",
    time_limit_s=210,
)

TEMPLATES = [WHERE_NULL, SQL_CHOICE, GROUP_HAVING]
