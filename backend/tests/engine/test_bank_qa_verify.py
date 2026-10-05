"""Сверка ключей шаблонов qa с настоящими системами и независимыми пересчётами.

SQL — SQLite, curl — настоящий curl против локального HTTP-сервера, локаторы — lxml,
фикстуры — запуск pytest, контракт — jsonschema, перцентили — numpy. Чего нет в
окружении — тест пропускает.
"""

import ast
import http.server
import itertools
import math
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
import threading
from collections import Counter
from typing import ClassVar

import numpy as np
import pytest

from app.testing.engine.bank.qa import TEMPLATES
from app.testing.engine.templates import ItemFormat, check

REG = {t.id: t for t in TEMPLATES}


def _rows(table: str) -> tuple[list[str], list[list[str]]]:
    lines = [ln for ln in table.split("\n") if ln.strip()]
    header = [c.strip() for c in lines[0].split("|")]
    return header, [[c.strip() for c in ln.split("|")] for ln in lines[2:]]


def _num(text: str, pattern: str) -> float:
    return float(re.search(pattern, text).group(1))


# --------------------------------------------------------------------------- SQL в SQLite


def _load_sql(code: str) -> tuple[sqlite3.Connection, str]:
    blocks = code.split("\n\n")
    db = sqlite3.connect(":memory:")
    for block in blocks[:-1]:
        lines = block.split("\n")
        name = lines[0].removeprefix("-- ").strip()
        header, rows = _rows("\n".join(lines[1:]))
        db.execute(f"CREATE TABLE {name} ({', '.join(header)})")
        for r in rows:
            vals = [None if v == "NULL" else int(v) if re.fullmatch(r"-?\d+", v) else v for v in r]
            db.execute(f"INSERT INTO {name} VALUES ({', '.join('?' * len(vals))})", vals)
    return db, blocks[-1]


def test_where_null_matches_sqlite():
    t = REG["qa.sql_where_null"]
    for seed in range(200):
        inst = t.generate(seed)
        db, sql = _load_sql(inst.public.code)
        assert db.execute(sql).fetchone()[0] == inst.key.value, (seed, sql)


def test_group_having_matches_sqlite():
    t = REG["qa.sql_group_having"]
    for seed in range(200):
        inst = t.generate(seed)
        db, sql = _load_sql(inst.public.code)
        out = " ".join(str(v) for row in db.execute(sql).fetchall() for v in row)
        assert check(inst, out), (seed, sql, out, inst.key)


def test_sql_choice_only_correct_query_works_on_shown_data():
    t = REG["qa.sql_query_choice"]
    for seed in range(200):
        inst = t.generate(seed)
        db, _ = _load_sql(inst.public.code + "\n\n-- нет запроса")
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master")}
        if "employees" in tables:
            sal = sorted({r[0] for r in db.execute("SELECT salary FROM employees")})
            expected = {(sal[-2],)}
        elif "customers" in tables:
            with_orders = {r[0] for r in db.execute("SELECT customer_id FROM orders")}
            expected = {
                (r[1],)
                for r in db.execute("SELECT id, name FROM customers")
                if r[0] not in with_orders
            }
        else:
            emails = Counter(r[0] for r in db.execute("SELECT email FROM users"))
            expected = {(e,) for e, c in emails.items() if c > 1}
        for i, sql in enumerate(inst.public.options):
            try:
                got = set(db.execute(sql).fetchall())
            except sqlite3.Error:
                got = None
            if i == inst.key:
                assert got == expected, (seed, sql, got, expected)
            else:
                assert got != expected, (seed, sql, got)


# --------------------------------------------------------------------------- curl


class _Recorder(http.server.BaseHTTPRequestHandler):
    methods: ClassVar[list[str]] = []

    def _handle(self):
        type(self).methods.append(self.command)
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = _handle  # noqa: N815

    def log_message(self, *args):
        pass


@pytest.mark.skipif(shutil.which("curl") is None, reason="curl не установлен")
def test_curl_method_matches_real_curl(tmp_path):
    for name in ("report.pdf", "photo.png", "data.csv"):
        (tmp_path / name).write_text("x")
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Recorder)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    t = REG["qa.curl_method"]
    seen = set()
    try:
        for seed in range(60):
            inst = t.generate(seed)
            cmd = inst.public.prompt.split("\n")[-1]
            cmd = re.sub(r"https://[^/\s]+", base, cmd).replace("/dev/null", os.devnull)
            _Recorder.methods.clear()
            args = shlex.split(cmd)
            args.insert(1, "--noproxy")
            args.insert(2, "*")
            subprocess.run(args, cwd=tmp_path, capture_output=True, timeout=20, check=True)
            assert _Recorder.methods, cmd
            assert check(inst, _Recorder.methods[-1]), (cmd, _Recorder.methods)
            seen.add(_Recorder.methods[-1])
    finally:
        server.shutdown()
    assert len(seen) >= 5


# --------------------------------------------------------------------------- локаторы в lxml


def test_locators_with_lxml():
    html = pytest.importorskip("lxml.html")
    pytest.importorskip("cssselect")
    t = REG["qa.locator_choice"]
    for seed in range(150):
        inst = t.generate(seed)
        doc = html.fromstring(f"<html><body>{inst.public.code}</body></html>")
        target = re.search(r"кнопку «(.+?)»", inst.public.prompt).group(1)
        for i, sel in enumerate(inst.public.options):
            found = doc.xpath(sel) if sel.startswith("//") else doc.cssselect(sel)
            ok = len(found) == 1 and found[0].text == target
            assert ok == (i == inst.key), (seed, sel, [e.text for e in found])


# --------------------------------------------------------------------------- pytest


def test_pytest_fixture_order_matches_real_pytest(tmp_path):
    t = REG["qa.pytest_fixture_order"]
    for seed in range(25):
        inst = t.generate(seed)
        path = tmp_path / f"test_gen_{seed}.py"
        path.write_text(inst.public.code, encoding="utf-8")
        res = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-s",
                "-q",
                "-p",
                "no:cacheprovider",
                "--rootdir",
                str(tmp_path),
                str(path),
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert res.returncode == 0, res.stdout + res.stderr
        printed = re.findall(r"(?:^|\s|\.)((?:\w+)[+-]|run_\w+)", res.stdout)
        assert check(inst, " ".join(printed)), (seed, inst.public.code, res.stdout, inst.key)


# --------------------------------------------------------------------------- контракт и jsonschema


def _schema_from_contract(table: str) -> dict:
    _, rows = _rows(table)
    props, required = {}, []
    for name, typ, req, cons in rows:
        s: dict = {}
        if typ == "integer":
            s["type"] = "integer"
        elif typ == "boolean":
            s["type"] = "boolean"
        elif typ == "array of string":
            s = {"type": "array", "items": {"type": "string"}}
        elif typ == "string или null":
            s["type"] = ["string", "null"]
        else:
            s["type"] = "string"
        if cons.startswith("одно из:"):
            s["enum"] = [v.strip() for v in cons.removeprefix("одно из:").split(",")]
        elif cons == "≥ 0":
            s["minimum"] = 0
        elif cons == "непустая строка":
            s["minLength"] = 1
        elif cons.startswith("ISO 8601"):
            s["pattern"] = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
        props[name] = s
        if req == "да":
            required.append(name)
    return {"type": "object", "properties": props, "required": required}


def test_json_contract_with_jsonschema():
    jsonschema = pytest.importorskip("jsonschema")
    import json

    t = REG["qa.json_contract"]
    for seed in range(200):
        inst = t.generate(seed)
        contract, resp = inst.public.code.split("\n\nОтвет:\n")
        schema = _schema_from_contract(contract)
        bad = set()
        for err in jsonschema.Draft202012Validator(schema).iter_errors(json.loads(resp)):
            if err.validator == "required":
                bad.add(re.search(r"'(\w+)'", err.message).group(1))
            else:
                bad.add(err.path[0])
        expected = {i for i, o in enumerate(inst.public.options) if o.strip("«»") in bad}
        assert expected == inst.key, (seed, bad, inst.public.options)


# --------------------------------------------------------------------------- пересчёты


def test_pairwise_counts_by_construction():
    t = REG["qa.pairwise_count"]
    for seed in range(100):
        inst = t.generate(seed)
        sizes = [len(line.split(":")[1].split(",")) for line in inst.public.code.split("\n")]
        a, b, c = sorted(sizes, reverse=True)
        if "минимальное" in inst.public.prompt:
            rows = [(x, y, (x + y) % c) for x in range(a) for y in range(b)]
            for (i, si), (j, sj) in itertools.combinations(enumerate((a, b, c)), 2):
                covered = {(r[i], r[j]) for r in rows}
                assert len(covered) == si * sj  # все пары покрыты
            assert inst.key.value == len(rows)  # меньше нельзя: пар у двух крупных a·b
        else:
            pairs = sum(x * y for x, y in itertools.combinations(sizes, 2))
            assert inst.key.value == pairs


def test_state_transitions_resimulated():
    t = REG["qa.state_transitions"]
    for seed in range(150):
        inst = t.generate(seed)
        _, rows = _rows(inst.public.code)
        start = re.search(r"в состоянии «(.+?)»", inst.public.prompt).group(1)
        graph = {(e, s): to for e, s, to in rows}
        good = set()
        for i, opt in enumerate(inst.public.options):
            state = start
            for ev in opt.split(" → "):
                state = graph.get((ev, state))
                if state is None:
                    break
            if state is not None:
                good.add(i)
        assert good == inst.key, seed


def test_percentile_matches_numpy():
    t = REG["qa.response_percentile"]
    for seed in range(200):
        inst = t.generate(seed)
        vals = [int(v) for v in inst.public.code.split(", ")]
        m = re.search(r"p(\d+) времени", inst.public.prompt)
        if m:
            value = np.percentile(vals, int(m.group(1)), method="inverted_cdf")
        else:
            sla = _num(inst.public.prompt, r"SLA (\d+)")
            value = int((np.array(vals) > sla).sum())
        assert inst.key.value == value, seed


def test_littles_law_by_simulation():
    t = REG["qa.littles_law"]
    for seed in range(60):
        inst = t.generate(seed)
        p = inst.public.prompt
        z = _num(p, r"пауза (\d+) с")
        if "Сколько виртуальных" in p:
            r, x = _num(p, r"ответа (\d+(?:\.\d+)?) с"), _num(p, r"получить (\d+) запросов")
            n = int(inst.key.value)
        elif "пропускную" in p:
            r, n = _num(p, r"ответа (\d+(?:\.\d+)?) с"), int(_num(p, r"Пользователей (\d+)"))
            x = inst.key.value
        else:
            n, x = int(_num(p, r"Пользователей (\d+)")), _num(p, r"показал (\d+) запросов")
            r = inst.key.value
        # дискретная симуляция закрытой модели: пользователи стартуют равномерно
        horizon = 2000.0
        cycle = r + z
        done = sum(math.floor((horizon - k * cycle / n) / cycle) for k in range(n))
        assert abs(done / horizon - x) / x < 0.01, (seed, p, done / horizon, x)


def _bucket(times, cap, refill):
    tokens, sec, rej = float(cap), 0, 0
    for t in times:
        while sec < math.floor(t + 1e-9):
            sec += 1
            tokens = min(cap, tokens + refill)
        if tokens >= 1:
            tokens -= 1
        else:
            rej += 1
    return rej


def _window(times, limit, window):
    log, rej = [], 0
    for t in times:
        log = [a for a in log if a > t - window + 1e-9]
        if len(log) < limit:
            log.append(t)
        else:
            rej += 1
    return rej


def test_rate_limit_resimulated():
    t = REG["qa.rate_limit"]
    for seed in range(200):
        inst = t.generate(seed)
        p = inst.public.prompt
        times = [float(v) for v in re.search(r"\(секунды\): ([\d., ]+)\.", p).group(1).split(", ")]
        if "Token bucket" in p:
            cap = int(_num(p, r"ёмкость (\d+)"))
            refill = int(_num(p, r"добавляется (\d+)"))
            value = _bucket(times, cap, refill)
        else:
            window = int(_num(p, r"последние (\d+) с"))
            limit = int(_num(p, r"меньше (\d+) запросов"))
            value = _window(times, limit, window)
        assert inst.key.value == value, (seed, p)


def test_regression_scope_resimulated():
    t = REG["qa.regression_scope"]
    for seed in range(150):
        inst = t.generate(seed)
        changed = re.search(r"только модуль «(.+?)»", inst.public.prompt).group(1)
        users: dict[str, set[str]] = {}
        for line in inst.public.code.split("\n"):
            mod, rest = line.split(" использует: ")
            for dep in re.findall(r"«(.+?)»", rest):
                users.setdefault(dep, set()).add(mod.strip("«»"))
        hit, stack = {changed}, [changed]
        while stack:
            for u in users.get(stack.pop(), ()):
                if u not in hit:
                    hit.add(u)
                    stack.append(u)
        expected = {i for i, o in enumerate(inst.public.options) if o.split("«")[1][:-1] in hit}
        assert expected == inst.key, seed


def test_pagination_by_slicing():
    t = REG["qa.pagination_check"]
    for seed in range(200):
        inst = t.generate(seed)
        p = inst.public.prompt
        limit, total = int(_num(p, r"limit=(\d+)")), int(_num(p, r"Всего в базе (\d+)"))
        data = list(range(total))
        pages = [data[i : i + limit] for i in range(0, total, limit)]
        if "Сколько страниц" in p:
            value = len(pages)
        elif "последней" in p:
            value = len(pages[-1])
        elif "offset" in p:
            page = int(_num(p, r"на странице (\d+)"))
            value = data.index(pages[page - 1][0])
        else:
            page = int(_num(p, r"запрос страницы (\d+)"))
            value = len(data[(page - 1) * limit : page * limit])
        assert inst.key.value == value, (seed, p)


def test_decision_table_reevaluated():
    t = REG["qa.decision_table"]
    for seed in range(150):
        inst = t.generate(seed)
        _, rows = _rows(inst.public.code.split("\n«—»")[0])
        case = inst.public.prompt.split("Входные данные: ")[1]
        facts = []
        for cond in (rows[0][0], rows[1][0], rows[2][0]):
            if "≥" in cond:
                limit = int(re.search(r"≥ (\d+)", cond).group(1))
                value = int(re.search(r"[Сс]умма(?: заказа)? (\d+)", case).group(1))
                facts.append(value >= limit)
            elif "Вес >" in cond:
                limit = int(re.search(r"> (\d+)", cond).group(1))
                facts.append(int(re.search(r"вес (\d+)", case).group(1)) > limit)
            elif "за город" in cond:
                facts.append("пригороде" in case)
            elif "сотрудник" in cond:
                facts.append(case.startswith("Сотрудник"))
            elif "карта" in cond:
                facts.append("карта лояльности есть" in case)
            elif "администратор" in cond:
                facts.append("Роль — администратор" in case)
            elif "Pro" in cond:
                facts.append("тариф Pro" in case)
            else:
                facts.append("email подтверждён" in case)
        for col in range(1, 5):
            if all(rows[r][col] in ("—", "да" if facts[r] else "нет") for r in range(3)):
                expected = rows[3][col]
                break
        assert inst.public.options[inst.key] == expected, (seed, case)


def test_equivalence_reevaluated():
    t = REG["qa.equivalence_classes"]
    pattern = r"От (-?\d+) до (-?\d+).*?от (-?\d+) до (-?\d+).*?от (-?\d+) и больше"
    for seed in range(200):
        inst = t.generate(seed)
        b0, e1, b1, e2, b2 = (int(v) for v in re.search(pattern, inst.public.prompt).groups())
        assert e1 == b1 - 1 and e2 == b2 - 1

        def cls(v, bounds=(b0, b1, b2)):
            return sum(v >= b for b in bounds)

        for i, opt in enumerate(inst.public.options):
            x, y = (int(v) for v in opt.split(" и "))
            assert (cls(x) == cls(y)) == (i == inst.key), (seed, opt)


def test_release_readiness_reevaluated():
    t = REG["qa.release_readiness"]
    for seed in range(200):
        inst = t.generate(seed)
        c = inst.public.code
        need_pass, max_crit, need_cov = (
            _num(c, r"не меньше (\d+)% выполненных"),
            _num(c, r"не больше (\d+)\."),
            _num(c, r"не меньше (\d+)% требований"),
        )
        ex, pa = _num(c, r"выполнено (\d+)"), _num(c, r"пройдено (\d+)")
        bl, cr = _num(c, r"blocker — (\d+)"), _num(c, r"critical — (\d+)")
        cov, req = (float(v) for v in re.search(r"покрыто требований (\d+) из (\d+)", c).groups())
        failing = [
            name
            for name, ok in (
                ("доля пройденных", pa / ex * 100 >= need_pass),
                ("блокирующих", bl == 0),
                ("критических", cr <= max_crit),
                ("покрытие", cov / req * 100 >= need_cov),
            )
            if not ok
        ]
        answer = inst.public.options[inst.key]
        if failing:
            assert len(failing) == 1 and failing[0] in answer, (seed, failing, answer)
        else:
            assert answer.startswith("Все критерии"), (seed, answer)


def test_counting_metrics_recomputed():
    for seed in range(200):
        inst = REG["qa.test_run_stats"].generate(seed)
        p = inst.public.prompt
        nums = [int(v) for v in re.findall(r"(\d+)", p.split("Выполненными")[0])]
        total, passed, failed, blocked, skipped, not_run = nums
        assert total == passed + failed + blocked + skipped + not_run
        if "процент выполненных" in p:
            value = passed / (passed + failed) * 100
        elif "запланированных тестов выполнен" in p:
            value = (passed + failed) / total * 100
        else:
            value = blocked + skipped + not_run
        assert abs(inst.key.value - value) < 1e-9
        inst = REG["qa.defect_metrics"].generate(seed)
        p = inst.public.prompt
        if "DRE" in p or "leakage" in p:
            before, after = (int(v) for v in re.findall(r"(\d+)", p)[:2])
            value = (before if "DRE" in p else after) / (before + after) * 100
        elif "KLOC" in p:
            kloc, found = (int(v) for v in re.findall(r"(\d+)", p)[:2])
            value = found / kloc
        else:
            fixed, reopened = (int(v) for v in re.findall(r"(\d+)", p)[:2])
            value = reopened / fixed * 100
        assert abs(inst.key.value - value) < 1e-9, p


@pytest.mark.parametrize("tid", ["qa.flaky_test_line", "qa.vulnerable_line"])
def test_find_bug_code_is_valid_python(tid):
    lines_seen = set()
    for seed in range(150):
        inst = REG[tid].generate(seed)
        ast.parse(inst.public.code)
        line = inst.public.code.split("\n")[inst.key - 1].strip()
        assert line and not line.startswith(("#", "@", "import", "from")), (seed, line)
        lines_seen.add(inst.key)
    assert len(lines_seen) >= 5


def test_bank_composition():
    assert len(TEMPLATES) == 30
    grades = Counter(t.target_grade for t in TEMPLATES)
    assert grades == {"intern": 6, "junior": 8, "middle": 9, "senior": 7}
    topics = Counter(t.topic for t in TEMPLATES)
    assert len(topics) >= 6 and max(topics.values()) <= 7
    assert {t.format for t in TEMPLATES} == set(ItemFormat)
