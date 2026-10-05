"""Backend-банк: ключи, которые нельзя получить запуском кода, сверяются второй,
независимой реализацией (другой алгоритм, разбор текста варианта) и ручными эталонами.
"""

import random
import re
import sqlite3
from email.utils import parsedate_to_datetime

from app.testing.engine.bank.backend import TEMPLATES as BACKEND
from app.testing.engine.bank.backend import caching_queues, concurrency, distributed, http_api

BY_ID = {t.id: t for t in BACKEND}


def _rng(tid: str, seed: int) -> random.Random:
    return random.Random(f"{tid}#{seed}")


# ------------------------------------------------------------ deadlock: перебор состояний


def _thread_programs(code: str) -> dict[str, list[tuple[str, str]]]:
    """Код функций → последовательность операций acquire/release (по отступам with)."""
    progs: dict[str, list[tuple[str, str]]] = {}
    name = None
    stack: list[tuple[int, str]] = []
    for line in [*code.split("\n"), "def __end__():"]:
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        while stack and indent <= stack[-1][0]:
            progs[name].append(("rel", stack.pop()[1]))
        if line.startswith("def "):
            name = line[4:].split("(")[0]
            progs[name] = []
            continue
        m = re.match(r"\s*with (\w+):", line)
        if m and name:
            progs[name].append(("acq", m.group(1)))
            stack.append((indent, m.group(1)))
    progs.pop("__end__")
    return progs


def _deadlock_reachable(p1, p2) -> bool:
    """Полный перебор чередований двух потоков: есть ли состояние, где оба ждут."""
    start = (0, 0, frozenset(), frozenset())
    seen, todo = {start}, [start]
    while todo:
        i, j, h1, h2 = todo.pop()
        moves = []
        for who, pc, prog, mine, other in ((0, i, p1, h1, h2), (1, j, p2, h2, h1)):
            if pc == len(prog):
                continue
            op, lock = prog[pc]
            if op == "rel":
                moves.append((who, mine - {lock}))
            elif lock not in mine and lock not in other:
                moves.append((who, mine | {lock}))
        if not moves:
            if i < len(p1) or j < len(p2):
                return True
            continue
        for who, held in moves:
            nxt = (i + 1, j, held, h2) if who == 0 else (i, j + 1, h1, held)
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    return False


def test_deadlock_pairs_match_state_space_search():
    t = BY_ID["backend.lock_order_deadlock"]
    for seed in range(150):
        inst = t.generate(seed)
        progs = _thread_programs(inst.public.code)
        assert len(progs) == 4
        expected = set()
        for idx, label in enumerate(inst.public.options):
            f, g = label.split(" и ")
            if _deadlock_reachable(progs[f], progs[g]):
                expected.add(idx)
        assert frozenset(expected) == inst.key, inst.public.code


def test_deadlock_model_examples():
    f = concurrency.can_deadlock
    assert f([["a", "b"]], [["b", "a"]])
    assert not f([["a", "b"]], [["a", "b"]])
    assert not f([["g", "a", "b"]], [["g", "b", "a"]])  # общая внешняя блокировка
    assert f([["g", "a", "b"]], [["b", "a"]])
    assert not f([["a"], ["b"]], [["b", "a"]])  # with подряд, а не вложенно
    assert f([["a", "b", "c"]], [["c", "a"]])


# ------------------------------------------------------------ идемпотентность: эмуляция серверов


class _Servers:
    """Три реализации обработчика из условия, по шагам, с часами и хранилищами."""

    def __init__(self, kind: str):
        self.kind = kind
        self.charges = 0
        self.now = 0.0
        self.redis: dict[str, tuple[str, float]] = {}
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE keys (k TEXT PRIMARY KEY, created REAL, response TEXT)")

    def steps(self, key: str):
        """Генератор шагов обработки одного запроса (yield — точка переключения)."""
        if self.kind == "none":
            yield
            self.charges += 1
            return
        if self.kind == "check_then_set":
            saved = self.redis.get(key)
            if saved and saved[1] > self.now:
                return
            yield  # между проверкой и записью может вклиниться второй запрос
            self.charges += 1
            self.redis[key] = ("ok", self.now + 86400)
            return
        self.db.execute("DELETE FROM keys WHERE created < ?", (self.now - 86400,))
        try:
            self.db.execute("INSERT INTO keys VALUES (?, ?, NULL)", (key, self.now))
        except sqlite3.IntegrityError:
            return  # ответ возьмут из сохранённого
        yield
        self.charges += 1

    def run(self, key: str):
        for _ in self.steps(key):
            pass

    def run_concurrently(self, key: str):
        a, b = self.steps(key), self.steps(key)
        alive = [g for g in (a, b) if next(g, "done") != "done"]
        for g in alive:
            for _ in g:
                pass


def test_idempotency_charges_match_emulation():
    tid = "backend.idempotency_charges"
    for seed in range(200):
        inst = BY_ID[tid].generate(seed)
        _, d = distributed._make_idempotency(_rng(tid, seed))
        s = _Servers(d["server"])
        s.run("K1")  # выполнен, ответ потерян
        for e in d["events"]:
            s.now += 5
            if e == "retry_same":
                s.run("K1")
            elif e == "new_key":
                s.run("K2")
            elif e == "double_click":
                s.run_concurrently("K3")
            elif e == "lost_retry":
                s.run("K4")  # первая попытка до сервера не дошла
            elif e == "late_retry":
                s.now += 3 * 86400
                s.run("K1")
        assert s.charges == inst.key.value, d


# ------------------------------------------------------------ повторная доставка: эмуляция брокера


def _emulate_consumer(code: str, crash_after: str) -> int:
    """Выполнить тело цикла по строкам кода с падением, затем повторную доставку."""
    body = [ln.strip() for ln in code.split("\n")[1:]]
    steps = []
    for ln in body:
        if ln.startswith(("payments.charge", "consumer.commit", "channel.basic_ack")):
            steps.append(ln)
        elif ln.startswith("with db.transaction"):
            steps.append("txn")
    charges, processed, acked = 0, set(), False

    def do(step):
        nonlocal charges, acked
        if step.startswith("payments.charge"):
            charges += 1
        elif step == "txn":
            if "m1" not in processed:
                charges += 1
                processed.add("m1")
        else:
            acked = True

    limit = 1 if crash_after == "first" else len(steps)
    for step in steps[:limit]:
        do(step)
    if not acked:  # брокер доставляет сообщение повторно, обработка проходит до конца
        for step in steps:
            do(step)
    return charges


def test_queue_redelivery_matches_emulation():
    tid = "backend.queue_redelivery"
    texts = {0: caching_queues._ZERO, 1: caching_queues._ONE, 2: caching_queues._TWO}
    for seed in range(200):
        inst = BY_ID[tid].generate(seed)
        _, d = caching_queues._make_redelivery(_rng(tid, seed))
        n = _emulate_consumer(inst.public.code, d["crash_after"])
        assert inst.public.options[inst.key] == texts[n], inst.public.code


# ------------------------------------------------------------ условные запросы: алгоритм RFC 9110


def _etags(value: str) -> list[tuple[bool, str]]:
    return [(w == "W/", tag) for w, tag in re.findall(r'(W/)?"([^"]*)"', value)]


def _rfc9110_status(method, headers, etag, last_modified, exists):
    """Порядок проверки предусловий по RFC 9110, раздел 13.2.2."""
    ok = 201 if method == "PUT" and not exists else 200
    if "If-Match" in headers:
        v = headers["If-Match"]
        strong_match = exists and any(not weak and tag == etag for weak, tag in _etags(v))
        if not (v == "*" and exists) and not strong_match:
            return 412
    elif "If-Unmodified-Since" in headers and exists:
        if last_modified > parsedate_to_datetime(headers["If-Unmodified-Since"]):
            return 412
    if "If-None-Match" in headers:
        v = headers["If-None-Match"]
        weak_match = exists and (v == "*" or any(tag == etag for _, tag in _etags(v)))
        if weak_match:
            return 304 if method in ("GET", "HEAD") else 412
    elif "If-Modified-Since" in headers and method in ("GET", "HEAD") and exists:
        if last_modified <= parsedate_to_datetime(headers["If-Modified-Since"]):
            return 304
    return ok


def test_conditional_requests_match_rfc_algorithm():
    t = BY_ID["backend.http_conditional"]
    cases = set()
    for seed in range(300):
        inst = t.generate(seed)
        req = inst.public.code.split("\n")
        method = req[0].split()[0]
        headers = dict(ln.split(": ", 1) for ln in req[1:] if ": " in ln and ln[0] != "{")
        exists = "пока нет" not in inst.public.prompt
        etag = lm = None
        if exists:
            etag = re.search(r'ETag: "([^"]+)"', inst.public.prompt).group(1)
            lm = parsedate_to_datetime(
                re.search(r"Last-Modified: (.+? GMT)", inst.public.prompt).group(1)
            )
        status = _rfc9110_status(method, headers, etag, lm, exists)
        assert inst.key[0] == str(status), (inst.public.prompt, inst.public.code)
        _, d = http_api._make_conditional(_rng(t.id, seed))
        cases.add(d["case"])
    assert len(cases) == 14


# ------------------------------------------------------------ Cache-Control: разбор заголовков


def _cache_expected(prompt: str, code: str) -> str:
    shared = prompt.startswith("CDN")
    t = int(re.search(r"Через (\d+) с", prompt).group(1))
    cc = re.search(r"Cache-Control: (.+)", code).group(1)
    d = {}
    for part in cc.split(", "):
        k, _, v = part.partition("=")
        d[k] = int(v) if v else True
    validator = "ETag:" in code
    revalidate = "conditional" if validator else "full"
    if "no-store" in d or (shared and "private" in d):
        return "full"
    if "no-cache" in d:
        return revalidate
    fresh_for = d.get("s-maxage", d.get("max-age", 0)) if shared else d.get("max-age", 0)
    if t < fresh_for:
        return "fresh"
    if t < fresh_for + d.get("stale-while-revalidate", 0):
        return "swr"
    return revalidate


def test_cache_control_matches_header_parsing():
    t = BY_ID["backend.http_cache_control"]
    marks = {
        "fresh": "не обращаясь к серверу",
        "conditional": "условный запрос",
        "full": "обычный запрос",
        "swr": "в фоне обновит",
    }
    outcomes = set()
    for seed in range(300):
        inst = t.generate(seed)
        exp = _cache_expected(inst.public.prompt, inst.public.code)
        assert marks[exp] in inst.public.options[inst.key], (inst.public.prompt, inst.public.code)
        outcomes.add(exp)
    assert outcomes == set(marks)


def test_cache_outcome_examples():
    f = http_api.cache_outcome
    assert f("browser", {"max-age": 60}, True, 30) == "fresh"
    assert f("browser", {"max-age": 60}, True, 90) == "conditional"
    assert f("browser", {"max-age": 60}, False, 90) == "full"
    assert f("browser", {"no-cache": True}, True, 1) == "conditional"
    assert f("cdn", {"private": True, "max-age": 600}, True, 1) == "full"
    assert f("cdn", {"max-age": 60, "s-maxage": 600}, True, 90) == "fresh"
    assert f("browser", {"max-age": 60, "s-maxage": 600}, True, 90) == "conditional"
    assert f("cdn", {"max-age": 60, "stale-while-revalidate": 30}, True, 75) == "swr"


# ------------------------------------------------------------ распределённые системы: эталоны


def test_raft_answers_follow_majority_rule():
    t = BY_ID["backend.raft_partition"]
    for seed in range(200):
        inst = t.generate(seed)
        p = inst.public.prompt
        n = int(re.search(r"из (\d+) узлов", p).group(1))
        a = int(re.search(r"в первой (\d+)", p).group(1))
        b = int(re.search(r"во второй (\d+)", p).group(1))
        assert a + b == n
        side = a if "из первой части" in p else b
        answer = inst.public.options[inst.key]
        if "serializable" in p:
            assert answer == distributed.R_STALE
        elif side * 2 > n:
            assert answer in (distributed.W_OK, distributed.R_OK)
        else:
            assert answer in (distributed.W_FAIL, distributed.R_FAIL)


def test_outbox_outcomes_hand_table():
    """Исход по стилю кода и месту падения — таблица, составленная вручную."""
    table = {
        ("outbox", "db.insert_outbox"): distributed.O_NONE,
        ("outbox", "db.commit() в create_"): distributed.O_EVENTUAL,
        ("outbox", "broker.publish(...) в relay"): distributed.O_DUP,
        ("outbox", "db.mark_sent"): distributed.O_DUP,
        ("outbox", "db.commit() в relay"): distributed.O_OK,
    }
    t = BY_ID["backend.outbox_crash"]
    for seed in range(200):
        inst = t.generate(seed)
        code, prompt = inst.public.code, inst.public.prompt
        label = re.search(r"вызов (.+?); следующая", prompt).group(1)
        answer = inst.public.options[inst.key]
        if "relay" in code:
            exp = next(v for (s, k), v in table.items() if s == "outbox" and label.startswith(k))
        else:
            lines = [ln.strip() for ln in code.split("\n")]
            commit_first = lines.index("db.commit()") < next(
                i for i, ln in enumerate(lines) if ln.startswith("broker.publish")
            )
            if label.startswith("db.insert_"):
                exp = distributed.O_NONE
            elif label == "db.commit()":
                exp = distributed.O_LOST if commit_first else distributed.O_OK
            else:
                exp = distributed.O_OK if commit_first else distributed.O_GHOST
        assert answer == exp, (prompt, code)


def test_saga_compensations_in_reverse_order():
    t = BY_ID["backend.saga_compensation"]
    comp = {step: c for _, steps in distributed._SAGAS for step, c in steps}
    for seed in range(200):
        inst = t.generate(seed)
        ordered = [inst.public.options[i] for i in inst.key]
        fail = next(i for i, s in enumerate(ordered) if s.endswith(": ошибка"))
        listing = re.findall(r"\d\) ([^;]+?)(?:;|\. Шаг)", inst.public.prompt)
        k = int(re.search(r"Шаг (\d+) завершился", inst.public.prompt).group(1))
        assert ordered[:fail] == listing[: k - 1]
        assert ordered[fail] == f"{listing[k - 1]}: ошибка"
        # компенсируются только завершённые шаги, в обратном порядке
        assert ordered[fail + 1 :] == [comp[s] for s in reversed(listing[: k - 1])]


def test_retry_timeline_examples():
    f = distributed.retry_timeline
    p = {"attempts": 4, "base": 0.5, "cap": 1.0, "timeout": 2.0}
    assert f("for", p) == (4 * 2.0 + 0.5 + 1.0 + 1.0, 4)
    q = {"retries": 2, "delay": 1.0, "cap": 4.0, "timeout": 2.0}
    assert f("while", q) == (3 * 2.0 + 1.0 + 2.0, 3)
