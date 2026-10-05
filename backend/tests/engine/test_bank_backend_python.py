"""Backend-банк: ключи сверяются выполнением кода задачи настоящим Python.

Код варианта (как его видит кандидат) запускается через exec; ответ генератора должен
совпасть с тем, что реально выведет или вернёт программа.
"""

import asyncio
import contextlib
import functools
import io
import math
import posixpath
import random
import re
import sqlite3
import types
from collections import deque

import pytest

from app.testing.engine.bank.backend import TEMPLATES as BACKEND
from app.testing.engine.bank.backend import (
    algorithms,
    caching_queues,
    concurrency,
    distributed,
    http_api,
    security,
)
from app.testing.engine.templates import check

BY_ID = {t.id: t for t in BACKEND}
SEEDS = range(60)


def _rng(tid: str, seed: int) -> random.Random:
    """Тот же генератор случайных чисел, что использует ItemTemplate.generate."""
    return random.Random(f"{tid}#{seed}")


def _run(code: str, namespace: dict | None = None) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(code, namespace if namespace is not None else {})
    return buf.getvalue()


@pytest.mark.parametrize(
    "tid", ["backend.py_slicing", "backend.py_mutable_default", "backend.py_late_binding"]
)
def test_code_output_matches_python(tid):
    t = BY_ID[tid]
    keys = set()
    for seed in range(150):
        inst = t.generate(seed)
        out = _run(inst.public.code)
        assert check(inst, out), (seed, inst.public.code, out, inst.key)
        keys.add(inst.key)
    assert len(keys) > 20


def test_binary_search_output_matches_python():
    t = BY_ID["backend.binary_search_steps"]
    for seed in range(150):
        inst = t.generate(seed)
        assert int(_run(inst.public.code)) == inst.key.value, inst.public.code


def test_handler_status_matches_execution():
    tid = "backend.handler_status"
    for seed in range(150):
        inst = BY_ID[tid].generate(seed)
        _, d = http_api._make_handler_status(_rng(tid, seed))
        users = {"good": types.SimpleNamespace(id=d["uid"], is_admin=d["is_admin"])}
        records = {}
        if d["exists"]:
            records[d["rid"]] = types.SimpleNamespace(author_id=d["author"])
        ns = {
            "find_user": lambda token, users=users: users.get(token),
            d["coll"]: records,
        }
        exec(inst.public.code, ns)
        handler = ns[f"update_{d['res']}"]
        request = types.SimpleNamespace(
            token="good" if d["token_ok"] else "expired",
            body={d["field"]: "новое значение"} if d["has_field"] else {},
        )
        status = handler(request, d["rid"])
        assert status == d["answer"]
        assert inst.public.options[inst.key] == str(status)


def test_path_traversal_matches_execution():
    t = BY_ID["backend.path_traversal"]
    base = security.BASE_DIR
    answers = set()
    for seed in range(200):
        inst = t.generate(seed)
        ns: dict = {}
        exec(inst.public.code, ns)
        resolve = ns["resolve"]
        escaping = []
        for opt in inst.public.options:
            m = re.fullmatch(r'name = "(.*)"', opt)
            if not m:
                continue
            try:
                path = resolve(m.group(1))
            except PermissionError:
                continue
            real = posixpath.normpath(path)  # ОС разрешает «..» при открытии файла
            if not (real == base or real.startswith(base + "/")):
                escaping.append(opt)
        assert len(escaping) <= 1, (inst.public.code, escaping)
        expected = escaping[0] if escaping else security.NONE_OPTION
        assert inst.public.options[inst.key] == expected, inst.public.code
        answers.add(expected == security.NONE_OPTION)
    assert answers == {True, False}


def test_retry_backoff_matches_execution():
    tid = "backend.retry_backoff_time"
    for seed in range(150):
        inst = BY_ID[tid].generate(seed)
        _, d = distributed._make_retry(_rng(tid, seed))
        clock = {"t": 0.0, "calls": 0}

        def request(timeout, clock=clock):
            clock["calls"] += 1
            clock["t"] += timeout
            raise TimeoutError

        fake_time = types.SimpleNamespace(
            sleep=lambda s, clock=clock: clock.update(t=clock["t"] + s)
        )
        code = inst.public.code.replace("import time\n", "")
        fn = re.search(r"call_with_retry\((\w+)", code.splitlines()[-1]).group(1)
        with pytest.raises(TimeoutError):
            exec(code, {"time": fake_time, fn: request})
        expected = clock["t"] if d["ask"] == "time" else clock["calls"]
        assert abs(expected - inst.key.value) < 1e-9, (code, clock)


class _VirtualTimeLoop(asyncio.SelectorEventLoop):
    """Event loop с виртуальными часами: таймеры срабатывают сразу, время копится."""

    last: "_VirtualTimeLoop | None" = None

    def __init__(self):
        super().__init__()
        self._vt = 0.0
        _VirtualTimeLoop.last = self

    def time(self):
        return self._vt

    def _run_once(self):
        if not self._ready and self._scheduled:
            when = self._scheduled[0]._when
            self._vt = max(self._vt, when)
        super()._run_once()


def test_async_total_time_matches_real_asyncio():
    t = BY_ID["backend.async_total_time"]
    for seed in range(120):
        inst = t.generate(seed)
        code = inst.public.code.replace(
            "asyncio.run(main())", "asyncio.run(main(), loop_factory=_VirtualTimeLoop)"
        )
        exec(code, {"_VirtualTimeLoop": _VirtualTimeLoop})
        elapsed = _VirtualTimeLoop.last._vt
        assert abs(elapsed - inst.key.value) < 1e-6, (inst.public.code, elapsed)


def test_async_time_model_examples():
    f = concurrency.async_total_time
    assert f([("seq", "a", 2), ("gather", [("b", 3), ("c", 1)])]) == 5
    assert f([("task", "t1", "a", 4), ("seq", "b", 1), ("await_task", "t1")]) == 4
    assert f([("task", "t1", "a", 6), ("seq", "b", 1)]) == 1  # задачу без await отменят
    assert f([("wait_for", "a", 5, 2), ("await_create", "b", 3)]) == 5


def _fake_db():
    db = sqlite3.connect(":memory:")
    db.executescript(
        """
        CREATE TABLE users (id INTEGER, email TEXT, login TEXT);
        INSERT INTO users VALUES (1, 'a@x.ru', 'anna'), (2, 'b@x.ru', 'boris');
        CREATE TABLE orders (id INTEGER, total INTEGER, status TEXT);
        INSERT INTO orders VALUES (1, 100, 'paid'), (2, 200, 'new'), (3, 300, 'paid');
        CREATE TABLE products (id INTEGER, title TEXT);
        INSERT INTO products VALUES (1, 'lamp'), (2, 'desk');
        CREATE TABLE reviews (id INTEGER, author TEXT);
        INSERT INTO reviews VALUES (1, 'anna'), (2, 'boris'), (3, 'anna');
        """
    )

    class Cursor:
        def __init__(self):
            self.cur = db.cursor()

        def execute(self, sql, params=None):
            if params is None:
                return self.cur.execute(sql)
            return self.cur.execute(sql.replace("%s", "?"), params)  # стиль psycopg

        def fetchone(self):
            return self.cur.fetchone()

        def fetchall(self):
            return self.cur.fetchall()

    return types.SimpleNamespace(cursor=Cursor)


def test_sql_injection_line_is_really_injectable():
    t = BY_ID["backend.sql_injection_line"]
    payload = "' OR '1'='1"
    for seed in range(150):
        inst = t.generate(seed)
        lines = inst.public.code.split("\n")
        code = "\n".join(lines[1:])  # без импорта app.db
        conn = _fake_db()
        ns = {"get_connection": lambda conn=conn: conn}
        exec(code, ns)
        vulnerable = []
        for name in ("find_user", "list_orders", "search_products", "count_reviews"):
            if name in ns and ns[name](payload) != ns[name]("zzz-nobody"):
                vulnerable.append(name)
        assert len(vulnerable) == 1, (inst.public.code, vulnerable)
        # строка-ключ находится внутри уязвимой функции
        owner = next(ln for ln in reversed(lines[: inst.key]) if ln.startswith("def ")).split("(")[
            0
        ][4:]
        assert owner == vulnerable[0]
        assert lines[inst.key - 1].strip().startswith("query =")


def test_blocking_line_is_the_only_blocking_call():
    t = BY_ID["backend.async_blocking_bug"]
    patterns = [line for line, _, _ in concurrency.BLOCKING_LINES]
    positions = set()
    for seed in range(150):
        inst = t.generate(seed)
        lines = inst.public.code.split("\n")
        hits = [i + 1 for i, ln in enumerate(lines) if ln.strip() in patterns]
        assert hits == [inst.key]
        # все остальные вызовы в async-функции — через await
        body = lines[lines.index(next(ln for ln in lines if ln.startswith("async def"))) + 1 :]
        for ln in body:
            s = ln.strip()
            if s in patterns or s.startswith("return"):
                continue
            assert "await " in s, s
        positions.add(inst.key)
    assert len(positions) >= 5
    # код модуля синтаксически корректен
    compile(t.generate(1).public.code, "<variant>", "exec")


def _fifo_misses(capacity, requests):
    cache, order, misses = set(), deque(), 0
    for k in requests:
        if k in cache:
            continue
        misses += 1
        if len(cache) == capacity:
            cache.discard(order.popleft())
        cache.add(k)
        order.append(k)
    return misses


def test_cache_misses_match_functools_lru_cache():
    tid = "backend.lru_misses"
    for seed in range(200):
        inst = BY_ID[tid].generate(seed)
        _, d = caching_queues._make_lru(_rng(tid, seed))
        if d["policy"] == "LRU":
            cached = functools.lru_cache(maxsize=d["capacity"])(lambda k: k)
            for k in d["requests"]:
                cached(k)
            misses = cached.cache_info().misses
        else:
            misses = _fifo_misses(d["capacity"], d["requests"])
        expected = misses if d["ask"] == "misses" else len(d["requests"]) - misses
        assert expected == inst.key.value


def test_complexity_scaling_independent_formula():
    tid = "backend.complexity_scaling"
    funcs = {
        "n": lambda n: n,
        "n2": lambda n: n**2,
        "n3": lambda n: n**3,
        "nlogn": lambda n: n * math.log2(n),
        "logn": math.log2,
        "2n": lambda n: 2.0**n,
    }
    for seed in range(200):
        inst = BY_ID[tid].generate(seed)
        _, d = algorithms._make_scaling(_rng(tid, seed))
        f = funcs[d["kind"]]
        expected = d["t"] * f(d["n2"]) / f(d["n1"])
        assert abs(expected - inst.key.value) < 1e-6
        assert str(d["t"]) in inst.public.prompt


def test_data_structure_answers():
    """Ключ — структура с O(1)/O(log n) на нужных операциях (сверено вручную по докам Python)."""
    expected = {
        "обрабатывался ли": "set:",
        "строго в порядке": "collections.deque: append() и popleft()",
        "самым ранним дедлайном": "heapq:",
        "по логину": "dict:",
        "undo": "list: append() и pop()",
        "сколько раз встретился": "collections.Counter",
    }
    t = BY_ID["backend.ds_choice"]
    seen = set()
    for seed in range(200):
        inst = t.generate(seed)
        marker = next(m for m in expected if m in inst.public.prompt)
        assert inst.public.options[inst.key].startswith(expected[marker])
        seen.add(marker)
    assert seen == set(expected)
