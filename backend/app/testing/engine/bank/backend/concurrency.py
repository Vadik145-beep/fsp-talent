"""Backend · конкурентность: время asyncio-кода, блокировка event loop, взаимоблокировки,
потерянное обновление в PostgreSQL."""

from __future__ import annotations

import itertools
import random
from typing import Any

from ...templates import (
    ItemFormat,
    ItemTemplate,
    NumericKey,
    Variant,
    make_multi_choice,
)

# ------------------------------------------------------------ сколько идёт asyncio-код

_FETCH_NAMES = (
    "users",
    "orders",
    "items",
    "stats",
    "logs",
    "prices",
    "geo",
    "rates",
    "feed",
    "carts",
    "tags",
    "news",
    "promo",
    "limits",
    "avatars",
    "reviews",
)


def async_total_time(stmts: list[tuple[Any, ...]]) -> int:
    """Модель времени main(): последовательные await, gather, задачи, wait_for."""
    now = 0
    tasks: dict[str, int] = {}
    for st in stmts:
        kind = st[0]
        if kind in ("seq", "await_create"):
            now += st[2]
        elif kind == "gather":
            now += max(s for _, s in st[1])
        elif kind == "task":
            tasks[st[1]] = now + st[3]
        elif kind == "await_task":
            now = max(now, tasks[st[1]])
        elif kind == "wait_for":
            now += min(st[2], st[3])
    return now  # незавершённые задачи asyncio.run отменяет при выходе


def _make_async_time(rng: random.Random) -> tuple[Variant, dict[str, Any]]:
    names = iter(rng.sample(_FETCH_NAMES, len(_FETCH_NAMES)))
    stmts: list[tuple[Any, ...]] = []
    pending: list[str] = []
    task_no = 0
    n = rng.randint(3, 5)
    for _ in range(n):
        options = ["seq", "gather", "task", "await_create", "wait_for"]
        if pending:
            options += ["await_task", "await_task"]
        kind = rng.choice(options)
        if kind == "gather":
            k = rng.randint(2, 3)
            stmts.append(("gather", [(next(names), rng.randint(1, 5)) for _ in range(k)]))
        elif kind == "task":
            task_no += 1
            var = f"t{task_no}"
            stmts.append(("task", var, next(names), rng.randint(2, 6)))
            pending.append(var)
        elif kind == "await_task":
            var = pending.pop(0)
            stmts.append(("await_task", var))
        elif kind == "wait_for":
            s = rng.randint(2, 6)
            stmts.append(
                ("wait_for", next(names), s, rng.choice([x for x in (1, 2, 3, 4) if x != s]))
            )
        else:
            stmts.append((kind, next(names), rng.randint(1, 4)))
    # ещё одна задача может остаться без await — это часть проверки
    if pending and rng.random() < 0.6:
        stmts.append(("await_task", pending.pop(0)))
    lines = [
        "import asyncio",
        "",
        "",
        "async def fetch(name, seconds):",
        "    await asyncio.sleep(seconds)",
        "    return name",
        "",
        "",
        "async def main():",
    ]
    for st in stmts:
        kind = st[0]
        if kind == "seq":
            lines.append(f'    {st[1]} = await fetch("{st[1]}", {st[2]})')
        elif kind == "await_create":
            lines.append(f'    {st[1]} = await asyncio.create_task(fetch("{st[1]}", {st[2]}))')
        elif kind == "gather":
            args = ", ".join(f'fetch("{nm}", {s})' for nm, s in st[1])
            targets = ", ".join(nm for nm, _ in st[1])
            lines.append(f"    {targets} = await asyncio.gather({args})")
        elif kind == "task":
            lines.append(f'    {st[1]} = asyncio.create_task(fetch("{st[2]}", {st[3]}))')
        elif kind == "await_task":
            lines.append(f"    await {st[1]}")
        else:
            lines += [
                "    try:",
                f'        await asyncio.wait_for(fetch("{st[1]}", {st[2]}), timeout={st[3]})',
                "    except TimeoutError:",
                "        pass",
            ]
    lines += ["", "", "asyncio.run(main())"]
    answer = async_total_time(stmts)
    variant = Variant(
        prompt=(
            "Сколько секунд будет выполняться программа (Python 3.12)? Временем на всё, кроме "
            "asyncio.sleep, пренебречь. Ответ — целое число секунд."
        ),
        key=NumericKey(answer, 0),
        code="\n".join(lines),
        extra={"language": "python", "answer_type": "integer", "unit": "с"},
        explanation=(
            "await ждёт по очереди, gather — параллельно (максимум), create_task запускает "
            "задачу сразу; задачи без await отменяются при выходе из asyncio.run."
        ),
    )
    return variant, {"stmts": stmts}


ASYNC_TIME = ItemTemplate(
    id="backend.async_total_time",
    specialization="backend",
    topic="concurrency",
    target_grade="junior",
    format=ItemFormat.NUMERIC,
    generator=lambda rng: _make_async_time(rng)[0],
    a=1.3,
    b=-0.3,
    title="Сколько идёт asyncio-код: await, gather, задачи",
    time_limit_s=240,
)

# ------------------------------------------------------------ блокировка event loop

# (строка, нужные импорты, переменная или None)
_GOOD_LINES = (
    ("user = await repo.get_user(user_id)", (), "user"),
    ("orders = await repo.list_orders(user_id, limit=20)", (), "orders"),
    ('rates = await http.get_json("/rates")', (), "rates"),
    ("await asyncio.sleep(0.05)", ("asyncio",), None),
    ("thumb = await asyncio.to_thread(resize_image, raw, 128)", ("asyncio",), "thumb"),
    (
        "geo = await asyncio.to_thread(requests.get, GEO_URL, timeout=5)",
        ("asyncio", "requests"),
        "geo",
    ),
    ('await cache.set(f"dash:{user_id}", user_id, ttl=60)', (), None),
    ("limits = await repo.get_limits(user_id)", (), "limits"),
)
BLOCKING_LINES = (
    ("time.sleep(0.5)", ("time",), None),
    ("weather = requests.get(WEATHER_URL, timeout=5).json()", ("requests",), "weather"),
    ('subprocess.run(["convert", src, dst], check=True)', ("subprocess",), None),
    ('digest = hashlib.pbkdf2_hmac("sha256", pwd, salt, 600_000)', ("hashlib",), "digest"),
)


def _gen_blocking_bug(rng: random.Random) -> Variant:
    fn = rng.choice(
        ("get_dashboard", "build_profile", "handle_login", "export_report", "sync_user")
    )
    goods = rng.sample(_GOOD_LINES, rng.randint(3, 5))
    bad = rng.choice(BLOCKING_LINES)
    body = list(goods)
    pos = rng.randint(0, len(body))
    body.insert(pos, bad)
    imports = sorted({m for _, mods, _ in body for m in mods} | {"asyncio"})
    head = [f"import {m}" for m in imports]
    head += ["", "from app.clients import cache, http, repo", "", ""]
    lines = [*head, f"async def {fn}(user_id: int) -> dict:"]
    variables = [v for _, _, v in body if v]
    lines += [f"    {line}" for line, _, _ in body]
    lines.append("    return {" + ", ".join(f'"{v}": {v}' for v in variables) + "}")
    bug_line = len(head) + 1 + pos + 1
    return Variant(
        prompt=(
            f"Сервис на FastAPI (asyncio, один процесс). Под нагрузкой эндпоинт с обработчиком "
            f"{fn} начал тормозить весь сервис: другие запросы ждут, пока он отработает. "
            "В какой строке причина? Остальные имена (repo, http, cache, resize_image, "
            "константы) определены корректно."
        ),
        key=bug_line,
        code="\n".join(lines),
        extra={"language": "python", "line_count": len(lines)},
        explanation=f"Синхронный блокирующий вызов в async-функции: {bad[0]}",
    )


ASYNC_BLOCKING = ItemTemplate(
    id="backend.async_blocking_bug",
    specialization="backend",
    topic="concurrency",
    target_grade="junior",
    format=ItemFormat.FIND_BUG_LINE,
    generator=_gen_blocking_bug,
    a=1.2,
    b=-0.4,
    title="Что блокирует event loop",
    time_limit_s=150,
)

# ------------------------------------------------------------ взаимоблокировки

_LOCK_SETS = (
    ("accounts_lock", "orders_lock", "audit_lock"),
    ("users_lock", "cache_lock", "stats_lock"),
    ("lock_a", "lock_b", "lock_c"),
    ("db_lock", "queue_lock", "file_lock"),
)
_FUNC_NAMES = ("transfer", "refund", "report", "cleanup", "sync", "rebuild", "export", "audit")
_ACTIONS = ("process()", "save()", "flush()", "update_totals()", "write_log()", "notify()")

Func = list[list[str]]  # функция — последовательность блоков, блок — цепочка вложенных with


def can_deadlock(f: Func, g: Func) -> bool:
    """Могут ли f и g в двух потоках заблокировать друг друга навсегда."""
    for cf in f:
        for cg in g:
            for j in range(1, len(cf)):
                held_f = set(cf[:j])
                want_f = cf[j]
                for k in range(1, len(cg)):
                    held_g = set(cg[:k])
                    want_g = cg[k]
                    if want_f in held_g and want_g in held_f and not held_f & held_g:
                        return True
    return False


def _random_func(rng: random.Random, locks: tuple[str, ...], gate: str) -> Func:
    shape = rng.choice(("nested2", "nested2", "nested3", "sequential", "gate", "single"))
    if shape == "nested2":
        return [rng.sample(locks, 2)]
    if shape == "nested3":
        return [rng.sample(locks, 3)]
    if shape == "sequential":
        a, b = rng.sample(locks, 2)
        return [[a], [b]]
    if shape == "gate":
        return [[gate, *rng.sample(locks, 2)]]
    return [[rng.choice(locks)]]


def _render_func(rng: random.Random, name: str, func: Func) -> list[str]:
    lines = [f"def {name}():"]
    for block in func:
        ind = "    "
        for lock in block:
            lines.append(f"{ind}with {lock}:")
            ind += "    "
        lines.append(f"{ind}{rng.choice(_ACTIONS)}")
    return lines


def _make_deadlock(rng: random.Random) -> tuple[Variant, dict[str, Any]]:
    locks = rng.choice(_LOCK_SETS)
    gate = "global_lock"
    names = rng.sample(_FUNC_NAMES, 4)
    while True:
        funcs = [_random_func(rng, locks, gate) for _ in names]
        pairs = list(itertools.combinations(range(4), 2))
        flags = [can_deadlock(funcs[i], funcs[j]) for i, j in pairs]
        if any(flags) and not all(flags):
            break
    used = [lk for lk in (*locks, gate) if any(lk in b for f in funcs for b in f)]
    lines = ["import threading", ""]
    lines += [f"{lk} = threading.Lock()" for lk in used]
    for name, func in zip(names, funcs, strict=True):
        lines += ["", "", *_render_func(rng, name, func)]
    labels = [f"{names[i]} и {names[j]}" for i, j in pairs]
    correct = [lb for lb, fl in zip(labels, flags, strict=True) if fl]
    wrong = [lb for lb, fl in zip(labels, flags, strict=True) if not fl]
    variant = make_multi_choice(
        rng,
        "Функции вызываются из разных потоков; process(), save() и т. п. не берут блокировок "
        "и всегда завершаются. Какие пары функций, запущенные одновременно (каждая в своём "
        "потоке), могут навсегда заблокировать друг друга (deadlock)? Отметьте все такие пары.",
        correct,
        wrong,
        code="\n".join(lines),
        extra={"language": "python"},
        explanation=(
            "Deadlock: один поток держит X и ждёт Y, другой держит Y и ждёт X. Последовательные "
            "with не держат две блокировки сразу, общая внешняя блокировка упорядочивает потоки."
        ),
    )
    return variant, {"funcs": funcs, "names": names}


LOCK_DEADLOCK = ItemTemplate(
    id="backend.lock_order_deadlock",
    specialization="backend",
    topic="concurrency",
    target_grade="senior",
    format=ItemFormat.MULTI_CHOICE,
    generator=lambda rng: _make_deadlock(rng)[0],
    a=1.5,
    b=1.2,
    title="Какие функции могут взаимно заблокироваться",
    time_limit_s=240,
)

# ------------------------------------------------------------ потерянное обновление

LOST_UPDATE_KINDS = ("atomic", "rmw", "for_update", "optimistic", "sequential")


def lost_update_final(kind: str, level: str, b0: int, x1: int, x2: int) -> int:
    """Итоговый баланс после двух списаний (модель PostgreSQL, ошибки не повторяются)."""
    if kind == "sequential":
        return b0 - x1 - x2
    if kind == "optimistic":
        return b0 - x1  # у T2 версия устарела: UPDATE затронет 0 строк (или ошибка в RR)
    if level != "READ COMMITTED":
        return b0 - x1  # T2 получает could not serialize access, транзакция откатывается
    if kind == "rmw":
        return b0 - x2  # T2 перезаписывает значение, посчитанное из старого чтения
    return b0 - x1 - x2  # atomic / FOR UPDATE: T2 работает с уже закоммиченным значением


def lost_update_steps(kind: str, x1: int, x2: int) -> list[tuple[str, str, int]]:
    """Расписание: (сессия, действие, сумма). Действия: begin, read, read_fu, read_ver,
    upd_atomic, upd_set, upd_opt, commit."""
    if kind == "atomic":
        return [
            ("T1", "begin", 0),
            ("T2", "begin", 0),
            ("T1", "upd_atomic", x1),
            ("T2", "upd_atomic", x2),
            ("T1", "commit", 0),
            ("T2", "commit", 0),
        ]
    if kind == "sequential":
        return [
            ("T1", "begin", 0),
            ("T2", "begin", 0),
            ("T1", "read", 0),
            ("T1", "upd_set", x1),
            ("T1", "commit", 0),
            ("T2", "read", 0),
            ("T2", "upd_set", x2),
            ("T2", "commit", 0),
        ]
    read, upd = {"rmw": ("read", "upd_set"), "for_update": ("read_fu", "upd_set")}.get(
        kind, ("read_ver", "upd_opt")
    )
    return [
        ("T1", "begin", 0),
        ("T2", "begin", 0),
        ("T1", read, 0),
        ("T2", read, 0),
        ("T1", upd, x1),
        ("T1", "commit", 0),
        ("T2", upd, x2),
        ("T2", "commit", 0),
    ]


def _make_lost_update(rng: random.Random) -> tuple[Variant, dict[str, Any]]:
    kind = rng.choice((*LOST_UPDATE_KINDS, "rmw", "atomic", "for_update"))
    level = rng.choice(("READ COMMITTED", "READ COMMITTED", "REPEATABLE READ"))
    table, col = rng.choice(
        (("accounts", "balance"), ("wallets", "amount"), ("cards", "limit_left"))
    )
    rid = rng.randint(1, 50)
    b0 = rng.choice((1000, 1500, 2000, 3000, 5000))
    x1, x2 = rng.sample((100, 200, 300, 400, 500, 700), 2)
    steps = lost_update_steps(kind, x1, x2)
    where = f"WHERE id = {rid}"
    lines: list[str] = []
    read_step: dict[str, int] = {}
    for sess, action, amount in steps:
        n = len(lines) + 1
        if action == "begin":
            sql = "BEGIN;" if level == "READ COMMITTED" else f"BEGIN ISOLATION LEVEL {level};"
        elif action == "read":
            sql = f"SELECT {col} FROM {table} {where};"
            read_step[sess] = n
        elif action == "read_fu":
            sql = f"SELECT {col} FROM {table} {where} FOR UPDATE;"
            read_step[sess] = n
        elif action == "read_ver":
            sql = f"SELECT {col}, version FROM {table} {where};"
            read_step[sess] = n
        elif action == "upd_atomic":
            sql = f"UPDATE {table} SET {col} = {col} - {amount} {where};"
        elif action == "upd_set":
            sql = (
                f"UPDATE {table} SET {col} = :new {where};"
                f"  -- :new = значение из шага {read_step[sess]} − {amount}"
            )
        elif action == "upd_opt":
            sql = (
                f"UPDATE {table} SET {col} = :new, version = version + 1 "
                f"{where} AND version = :v;"
                f"  -- :new, :v — из шага {read_step[sess]}; :new = {col} − {amount}"
            )
        else:
            sql = "COMMIT;"
        lines.append(f"{n:>2}. {sess}: {sql}")
    answer = lost_update_final(kind, level, b0, x1, x2)
    blocking = (
        "Если команда ждёт снятия блокировки строки, её сессия ждёт, а следующие шаги другой "
        "сессии выполняются."
    )
    prompt = (
        f"PostgreSQL 16. Изначально у строки id = {rid} в таблице {table} {col} = {b0}. "
        "Две сессии приложения выполняют шаги строго по порядку. "
        f"{blocking} Если команда завершилась ошибкой, приложение откатывает свою транзакцию "
        "и не повторяет её; UPDATE, затронувший 0 строк, тоже не повторяется. "
        f"Каким будет {col} после завершения обеих сессий?"
    )
    variant = Variant(
        prompt=prompt,
        key=NumericKey(answer, 0),
        code="\n".join(lines),
        extra={"language": "sql", "answer_type": "integer"},
        explanation=f"Сценарий {kind} при {level}: {answer}.",
    )
    data = {
        "kind": kind,
        "level": level,
        "table": table,
        "col": col,
        "rid": rid,
        "b0": b0,
        "steps": steps,
        "answer": answer,
    }
    return variant, data


LOST_UPDATE = ItemTemplate(
    id="backend.lost_update",
    specialization="backend",
    topic="concurrency",
    target_grade="senior",
    format=ItemFormat.NUMERIC,
    generator=lambda rng: _make_lost_update(rng)[0],
    a=1.5,
    b=1.6,
    title="Потерянное обновление в PostgreSQL",
    time_limit_s=300,
)

TEMPLATES = [ASYNC_TIME, ASYNC_BLOCKING, LOCK_DEADLOCK, LOST_UPDATE]
