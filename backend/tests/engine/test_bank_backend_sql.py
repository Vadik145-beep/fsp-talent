"""Backend-банк: SQL-ключи сверяются с настоящей СУБД (SQLite).

Таблицы из условия загружаются в SQLite, запрос из условия выполняется как есть.
Использованные конструкции (WHERE с NULL, GROUP BY/HAVING, RANK/DENSE_RANK/ROW_NUMBER,
SUM() OVER с фреймом по умолчанию RANGE, LIMIT/OFFSET) в SQLite и PostgreSQL ведут себя
одинаково.
"""

import random
import sqlite3

import pytest

from app.testing.engine.bank.backend import TEMPLATES as BACKEND
from app.testing.engine.bank.backend import http_api
from app.testing.engine.templates import check

BY_ID = {t.id: t for t in BACKEND}
pytestmark = pytest.mark.skipif(
    sqlite3.sqlite_version_info < (3, 28), reason="нужны оконные функции SQLite"
)


def _load(code: str):
    """Разобрать таблицы из условия в SQLite; вернуть (соединение, SQL-запрос)."""
    blocks = code.split("\n\n")
    db = sqlite3.connect(":memory:")
    for block in blocks[:-1]:
        lines = block.split("\n")
        name = lines[0].removeprefix("-- ").strip()
        header = [h.strip() for h in lines[1].split("|")]
        db.execute(f"CREATE TABLE {name} ({', '.join(header)})")
        for line in lines[3:]:
            cells = [c.strip() for c in line.split("|")]
            vals = [None if v == "NULL" else (int(v) if v.isdigit() else v) for v in cells]
            db.execute(f"INSERT INTO {name} VALUES ({', '.join('?' * len(vals))})", vals)
    return db, blocks[-1]


def test_where_count_matches_sqlite():
    t = BY_ID["backend.sql_where_filter"]
    for seed in range(200):
        inst = t.generate(seed)
        db, sql = _load(inst.public.code)
        assert len(db.execute(sql).fetchall()) == inst.key.value, (seed, sql)


def test_group_having_matches_sqlite():
    t = BY_ID["backend.sql_group_having"]
    for seed in range(200):
        inst = t.generate(seed)
        db, sql = _load(inst.public.code)
        out = " ".join(str(v) for row in db.execute(sql).fetchall() for v in row)
        assert check(inst, out), (seed, sql, out, inst.key)


def test_window_functions_match_sqlite():
    t = BY_ID["backend.sql_window_rank"]
    for seed in range(200):
        inst = t.generate(seed)
        db, sql = _load(inst.public.code)
        cur = db.execute(sql)
        idx = [c[0] for c in cur.description].index("r")
        out = " ".join(str(row[idx]) for row in cur.fetchall())
        assert check(inst, out), (seed, sql, out, inst.key)


def test_index_usage_matches_explain_query_plan():
    t = BY_ID["backend.sql_index_usage"]
    for seed in range(200):
        inst = t.generate(seed)
        ddl = inst.public.code.split("\n\n")[0]
        db = sqlite3.connect(":memory:")
        db.executescript(ddl)
        idx = ddl.split("CREATE INDEX ")[1].split()[0]
        uses = set()
        for i, cond in enumerate(inst.public.options):
            plan = db.execute(f"EXPLAIN QUERY PLAN SELECT * FROM orders {cond}").fetchall()
            details = " ".join(row[-1] for row in plan)
            if "SEARCH" in details and f"USING INDEX {idx}" in details:
                uses.add(i)
        assert frozenset(uses) == inst.key, (seed, ddl, inst.public.options)


def test_pagination_matches_sqlite():
    tid = "backend.pagination_offset"
    for seed in range(150):
        inst = BY_ID[tid].generate(seed)
        _, d = http_api._make_pagination(random.Random(f"{tid}#{seed}"))
        k = d["k"]
        n = 3 * k + 7
        db = sqlite3.connect(":memory:")
        db.execute("CREATE TABLE feed (id INTEGER PRIMARY KEY, created_at INTEGER)")
        db.executemany("INSERT INTO feed VALUES (?, ?)", [(i, i * 10) for i in range(1, n + 1)])
        q = "SELECT id, created_at FROM feed ORDER BY created_at DESC LIMIT ? OFFSET ?"
        page1 = db.execute(q, (k, 0)).fetchall()
        new_ids = range(n + 1, n + 1 + d["inserted"])
        db.executemany("INSERT INTO feed VALUES (?, ?)", [(i, i * 10) for i in new_ids])
        rnd = random.Random(seed)
        gone = rnd.sample([r[0] for r in page1], d["deleted"])
        db.executemany("DELETE FROM feed WHERE id = ?", [(i,) for i in gone])
        if d["method"] == "offset":
            page2 = db.execute(q, (k, k)).fetchall()
        else:
            page2 = db.execute(
                "SELECT id, created_at FROM feed WHERE created_at < ? "
                "ORDER BY created_at DESC LIMIT ?",
                (page1[-1][1], k),
            ).fetchall()
        seen = {r[0] for r in page1} | {r[0] for r in page2}
        dup = len({r[0] for r in page1} & {r[0] for r in page2})
        border = min(r[1] for r in page2)
        skipped = db.execute(
            "SELECT count(*) FROM feed WHERE id <= ? AND created_at > ?", (n, border)
        ).fetchone()[0] - len([i for i in seen if i <= n and i not in gone and i * 10 > border])
        expected = dup if d["ask"] == "dup" else skipped
        assert expected == inst.key.value, (d, dup, skipped)
