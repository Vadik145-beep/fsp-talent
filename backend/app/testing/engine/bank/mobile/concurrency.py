"""Mobile / многопоточность: корутины в runBlocking, отмена, GCD (порядок и дедлоки).

Модели:
- runBlocking — однопоточный цикл событий: launch/async ставят корутину в очередь (FIFO),
  она стартует, когда текущая корутина приостановится; delay — таймер виртуального времени;
  возобновление после join/await тоже идёт через очередь.
- главная очередь GCD — последовательная FIFO: main.async выполняется после текущего кода,
  sync на другой очереди выполняется сразу, asyncAfter — по таймеру.
Независимая сверка — tests/engine/test_bank_mobile_concurrency.py (трансляция в asyncio
с виртуальными часами).
"""

from __future__ import annotations

import heapq
import itertools
import random
from collections import deque
from typing import Any

from ...templates import ItemFormat, ItemTemplate, Variant, make_multi_choice

Ins = tuple[Any, ...]  # инструкция модели (вид, аргументы…)

# --------------------------------------------------------------------------- корутины: порядок

# Инструкции: ("print", s) ("delay", ms) ("launch", j) ("async", j) ("join", j)
# ("await_print", j, k) ("value", v) — последняя строка async-блока


def simulate_coroutines(
    main: list[Ins], children: dict[str, list[Ins]]
) -> tuple[list[str], list[int]]:
    """Возвращает (вывод, моменты пробуждения по таймерам)."""
    out: list[str] = []
    wakes: list[int] = []
    progs = {"main": main, **children}
    pc = dict.fromkeys(progs, 0)
    done: set[str] = set()
    values: dict[str, int] = {}
    waiters: dict[str, list[str]] = {j: [] for j in progs}
    ready: deque[str] = deque(["main"])
    timers: list[tuple[int, int, str]] = []
    now = 0
    seq = 0

    def finish(task: str) -> None:
        done.add(task)
        for w in waiters[task]:
            ready.append(w)
        waiters[task] = []

    while ready or timers:
        if not ready:
            now, _, task = heapq.heappop(timers)
            wakes.append(now)
            ready.append(task)
            continue
        task = ready.popleft()
        prog = progs[task]
        while True:
            if pc[task] >= len(prog):
                finish(task)
                break
            ins = prog[pc[task]]
            op = ins[0]
            if op == "print":
                out.append(ins[1])
            elif op == "value":
                values[task] = ins[1]
            elif op in ("launch", "async"):
                ready.append(ins[1])
            elif op == "delay":
                pc[task] += 1
                seq += 1
                heapq.heappush(timers, (now + ins[1], seq, task))
                break
            elif op in ("join", "await_print"):
                j = ins[1]
                if j not in done:
                    waiters[j].append(task)
                    # инструкция выполнится повторно после пробуждения — тогда j уже done
                    break
                if op == "await_print":
                    out.append(str(values[j] + ins[2]))
            pc[task] += 1
    return out, wakes


def _render_coroutines(main: list[Ins], children: dict[str, list[Ins]]) -> str:
    lines = ["import kotlinx.coroutines.*", "", "fun main() = runBlocking {"]

    def stmt(ins: Ins, pad: str) -> list[str]:
        op = ins[0]
        if op == "print":
            return [f'{pad}println("{ins[1]}")']
        if op == "delay":
            return [f"{pad}delay({ins[1]})"]
        if op == "value":
            return [f"{pad}{ins[1]}"]
        if op in ("launch", "async"):
            res = [f"{pad}val {ins[1]} = {op} {{"]
            for sub in children[ins[1]]:
                res += stmt(sub, pad + "    ")
            return [*res, pad + "}"]
        if op == "join":
            return [f"{pad}{ins[1]}.join()"]
        return [f"{pad}println({ins[1]}.await() + {ins[2]})"]

    for ins in main:
        lines += stmt(ins, "    ")
    lines.append("}")
    return "\n".join(lines)


def _gen_coroutines(rng: random.Random) -> Variant:
    while True:
        letters = list("ABCDEFGHKMNPRSTUVWXYZ")
        rng.shuffle(letters)
        children: dict[str, list[Ins]] = {}
        main: list[Ins] = []
        launched: list[str] = []
        n_children = rng.randint(2, 3)
        has_async = rng.random() < 0.35
        for c in range(n_children):
            is_async = has_async and c == n_children - 1
            name = f"d{c + 1}" if is_async else f"job{c + 1}"
            steps: list[Ins] = []
            if rng.random() < 0.5:
                steps.append(("print", letters.pop()))
            steps.append(("delay", rng.choice(range(100, 501, 50))))
            steps.append(("print", letters.pop()))
            if rng.random() < 0.3:
                steps.append(("delay", rng.choice(range(100, 301, 50))))
                steps.append(("print", letters.pop()))
            if is_async:
                steps.append(("value", rng.randint(1, 9) * 10))
            children[name] = steps
            main.append(("async" if is_async else "launch", name))
            launched.append(name)
            if rng.random() < 0.3:
                main.append(("print", letters.pop()))
        main.append(("print", letters.pop()))
        if rng.random() < 0.6:
            main.append(("delay", rng.choice(range(150, 451, 50))))
            main.append(("print", letters.pop()))
        if has_async:
            main.append(("await_print", launched[-1], rng.randint(1, 9)))
        elif rng.random() < 0.5:
            main.append(("join", rng.choice(launched)))
            main.append(("print", letters.pop()))
        out, wakes = simulate_coroutines(main, children)
        wakes_sorted = sorted(wakes)
        gaps_ok = all(b - a >= 50 for a, b in itertools.pairwise(wakes_sorted))
        textual = [ins[1] for ins in main if ins[0] == "print"]
        if gaps_ok and len(out) >= 5 and out[: len(textual)] != textual:
            break
    return Variant(
        prompt=(
            "Что выведет программа (Kotlin 1.9, kotlinx.coroutines 1.7)? "
            "Перечислите напечатанное через пробел в порядке вывода."
        ),
        key=" ".join(out),
        code=_render_coroutines(main, children),
        extra={"language": "kotlin"},
        explanation="runBlocking однопоточный: launch стартует, когда main приостановится "
        "(delay/join/await или конец блока); после delay корутины просыпаются по времени.",
    )


COROUTINES_ORDER = ItemTemplate(
    id="mobile.coroutines_launch_order",
    specialization="mobile",
    topic="concurrency",
    target_grade="middle",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_coroutines,
    a=1.5,
    b=0.7,
    title="Порядок вывода корутин в runBlocking",
    time_limit_s=240,
)

# --------------------------------------------------------------------------- корутины: отмена


def simulate_cancellation(p: dict[str, Any]) -> list[str]:
    """Модель одного из трёх сценариев отмены (см. _gen_cancellation)."""
    d, t, n = p["d"], p["t"], p["n"]
    ticks = [f"{p['tick']}{i}" for i in range(n) if i * d < t]
    if p["mode"] in ("timeout_null", "timeout_catch"):
        finished = n * d < t
        if finished:
            return [*ticks, p["value"]]
        return [*ticks, "timeout" if p["mode"] == "timeout_null" else p["caught"]]
    out = [*ticks, p["stop"]]
    fin = p["finally"]  # None | "plain" | "suspend" | "noncancellable"
    cleanup = [p["cleanup"]] if fin in ("plain", "noncancellable") else []
    if p["mode"] == "cancel_join":
        return [*out, *cleanup, p["done"]]
    return [*out, p["done"], *cleanup]


def _render_cancellation(p: dict[str, Any]) -> str:
    d, t, n = p["d"], p["t"], p["n"]
    loop = [
        f"repeat({n}) {{ i ->",
        f'    println("{p["tick"]}$i")',
        f"    delay({d})",
        "}",
    ]
    lines = ["import kotlinx.coroutines.*", "", "fun main() = runBlocking {"]
    if p["mode"] == "timeout_null":
        lines += [f"    val result = withTimeoutOrNull({t}) {{"]
        lines += ["        " + s for s in loop]
        lines += [f'        "{p["value"]}"', "    }", '    println(result ?: "timeout")', "}"]
        return "\n".join(lines)
    if p["mode"] == "timeout_catch":
        lines += ["    try {", f"        val result = withTimeout({t}) {{"]
        lines += ["            " + s for s in loop]
        lines += [
            f'            "{p["value"]}"',
            "        }",
            "        println(result)",
            "    } catch (e: TimeoutCancellationException) {",
            f'        println("{p["caught"]}")',
            "    }",
            "}",
        ]
        return "\n".join(lines)
    fin = p["finally"]
    lines.append("    val job = launch {")
    if fin is None:
        lines += ["        " + s for s in loop]
    else:
        lines.append("        try {")
        lines += ["            " + s for s in loop]
        lines.append("        } finally {")
        if fin == "plain":
            lines.append(f'            println("{p["cleanup"]}")')
        elif fin == "suspend":
            lines += [f"            delay({p['fd']})", f'            println("{p["cleanup"]}")']
        else:
            lines += [
                "            withContext(NonCancellable) {",
                f"                delay({p['fd']})",
                f'                println("{p["cleanup"]}")',
                "            }",
            ]
        lines.append("        }")
    lines += ["    }", f"    delay({t})", f'    println("{p["stop"]}")']
    if p["mode"] == "cancel_join":
        lines.append(_join_text(p))
    else:
        lines.append("    job.cancel()")
    lines += [f'    println("{p["done"]}")', "}"]
    return "\n".join(lines)


def _join_text(p: dict[str, Any]) -> str:
    return "    job.cancelAndJoin()" if p["join_style"] == 0 else "    job.cancel(); job.join()"


def _gen_cancellation(rng: random.Random) -> Variant:
    while True:
        d = rng.choice(range(100, 401, 50))
        t = rng.choice(range(250, 1301, 50))
        if t % d == 0 or min(t % d, d - t % d) < 40:
            continue
        mode = rng.choice(
            ("cancel_join", "cancel_join", "cancel_only", "timeout_null", "timeout_catch")
        )
        if mode.startswith("timeout"):
            n = rng.randint(2, 6)
            if abs(n * d - t) < 40:
                continue
        else:
            n = rng.randint(t // d + 2, t // d + 6)  # задача отменяется посреди цикла
        p = {
            "d": d,
            "t": t,
            "n": n,
            "mode": mode,
            "tick": rng.choice(("tick", "step", "ping", "job")),
            "stop": rng.choice(("stop", "halt", "tired")),
            "done": rng.choice(("done", "quit", "exit")),
            "cleanup": rng.choice(("cleanup", "release", "closed")),
            "caught": rng.choice(("caught", "expired", "late")),
            "value": rng.choice(("ok", "ready", "finished")),
            "finally": rng.choice((None, "plain", "plain", "suspend", "noncancellable")),
            "fd": rng.choice((50, 100, 200)),
            "join_style": rng.randrange(2),
        }
        out = simulate_cancellation(p)
        if len(out) >= 3:
            break
    return Variant(
        prompt=(
            "Что выведет программа (Kotlin 1.9, kotlinx.coroutines 1.7)? "
            "Перечислите напечатанное через пробел в порядке вывода."
        ),
        key=" ".join(out),
        code=_render_cancellation(p),
        extra={"language": "kotlin"},
        explanation="Отмена кооперативная: delay бросает CancellationException; cancel() не ждёт "
        "завершения, cancelAndJoin() ждёт; suspend-вызов в finally отменённой корутины "
        "сразу бросает исключение, если не обёрнут в NonCancellable.",
    )


CANCELLATION = ItemTemplate(
    id="mobile.coroutines_cancellation",
    specialization="mobile",
    topic="concurrency",
    target_grade="senior",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_cancellation,
    a=1.6,
    b=1.8,
    title="Отмена корутин и таймауты",
    time_limit_s=270,
)

# --------------------------------------------------------------------------- GCD: порядок вывода


def simulate_gcd(items: list[Ins]) -> list[str]:
    """items: ("print", s) | ("sync", s) | ("async", [items]) | ("after", sec10, [items])."""
    out: list[str] = []
    queue: deque[list[Ins]] = deque()
    timers: list[tuple[int, int, list[Ins]]] = []
    seq = 0

    def run(block: list[Ins]) -> None:
        nonlocal seq
        for it in block:
            if it[0] in ("print", "sync"):
                out.append(it[1])
            elif it[0] == "async":
                queue.append(it[1])
            else:
                seq += 1
                heapq.heappush(timers, (it[1], seq, it[2]))

    run(items)
    while queue or timers:
        if queue:
            run(queue.popleft())
        else:
            _, _, block = heapq.heappop(timers)
            run(block)
    return out


def _collect_prints(block: list[Ins], acc: list[str]) -> None:
    """Метки в порядке появления в тексте кода."""
    for it in block:
        if it[0] in ("print", "sync"):
            acc.append(it[1])
        else:
            _collect_prints(it[1] if it[0] == "async" else it[2], acc)


def _render_gcd(items: list[Ins], pad: str, sync_queue: str) -> list[str]:
    lines: list[str] = []
    for it in items:
        if it[0] == "print":
            lines.append(f'{pad}print("{it[1]}")')
        elif it[0] == "sync":
            q = "DispatchQueue.global()" if it[2] else "queue"
            lines.append(f'{pad}{q}.sync {{ print("{it[1]}") }}')
        else:
            head = (
                "DispatchQueue.main.async {"
                if it[0] == "async"
                else f"DispatchQueue.main.asyncAfter(deadline: .now() + 0.{it[1]}) {{"
            )
            body = it[1] if it[0] == "async" else it[2]
            if len(body) == 1 and body[0][0] == "print":
                lines.append(f'{pad}{head} print("{body[0][1]}") }}')
            else:
                lines.append(pad + head)
                lines += _render_gcd(body, pad + "    ", sync_queue)
                lines.append(pad + "}")
    return lines


def _gen_gcd_order(rng: random.Random) -> Variant:
    while True:
        letters = list("ABCDEFGHKMNPRSTUVWXYZ")
        rng.shuffle(letters)
        delays = rng.sample(range(1, 6), 2)
        items: list[Ins] = []
        n = rng.randint(5, 7)
        n_after = 0
        for _ in range(n):
            r = rng.random()
            if r < 0.3:
                items.append(("print", letters.pop()))
            elif r < 0.5:
                items.append(("sync", letters.pop(), rng.random() < 0.5))
            elif r < 0.8:
                body: list[Ins] = [("print", letters.pop())]
                if rng.random() < 0.35:
                    body.append(("async", [("print", letters.pop())]))
                    if rng.random() < 0.5:
                        body.reverse()
                items.append(("async", body))
            elif n_after < 2:
                body = [("print", letters.pop())]
                if rng.random() < 0.4:
                    body.append(("async", [("print", letters.pop())]))
                items.append(("after", delays[n_after], body))
                n_after += 1
        out = simulate_gcd(items)
        kinds = {it[0] for it in items}
        textual: list[str] = []
        _collect_prints(items, textual)
        if len(out) >= 5 and out != textual and "async" in kinds and len(kinds) >= 3:
            break
    label = rng.choice(("com.example.worker", "com.app.db", "io.sync.queue", "com.shop.cache"))
    body_lines = _render_gcd(items, "        ", "queue")
    code = "\n".join(
        [
            "override func viewDidLoad() {",
            "    super.viewDidLoad()",
            f'    let queue = DispatchQueue(label: "{label}")',
            *[ln[4:] for ln in body_lines],
            "}",
        ]
    )
    return Variant(
        prompt=(
            "Метод viewDidLoad вызывается в главном потоке iOS-приложения (Swift 5.9). "
            "Считайте, что сам код выполняется мгновенно. Что будет напечатано? "
            "Перечислите строки через пробел в порядке вывода."
        ),
        key=" ".join(out),
        code=code,
        extra={"language": "swift"},
        explanation="sync на другой очереди выполняется сразу; main.async ставит блок в конец "
        "главной очереди (после текущего кода); asyncAfter — после задержки.",
    )


GCD_ORDER = ItemTemplate(
    id="mobile.gcd_main_queue_order",
    specialization="mobile",
    topic="concurrency",
    target_grade="middle",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_gcd_order,
    a=1.4,
    b=0.5,
    title="GCD: порядок выполнения на главной очереди",
    time_limit_s=210,
)

# --------------------------------------------------------------------------- GCD: дедлоки

_FUNCS = ("updateUI()", "save()", "reload()", "render()", "persist()")


def _deadlock_pool(q: str, f: str, g: str) -> tuple[list[str], list[str]]:
    deadlock = [
        f"DispatchQueue.main.sync {{ {f} }}",
        f'let {q} = DispatchQueue(label: "{q}")\n{q}.sync {{ {q}.sync {{ {f} }} }}',
        f'let {q} = DispatchQueue(label: "{q}")\n{q}.async {{ {q}.sync {{ {f} }} }}',
        "let sem = DispatchSemaphore(value: 0)\n"
        f"DispatchQueue.main.async {{ {f}; sem.signal() }}\nsem.wait()",
        f"DispatchQueue.main.async {{ DispatchQueue.main.sync {{ {f} }} }}",
    ]
    safe = [
        f"DispatchQueue.main.async {{ {f} }}",
        f"DispatchQueue.global().sync {{ {f} }}",
        f'let {q} = DispatchQueue(label: "{q}", attributes: .concurrent)\n'
        f"{q}.sync {{ {q}.sync {{ {f} }} }}",
        f'let {q} = DispatchQueue(label: "{q}")\n{q}.sync {{ DispatchQueue.main.async {{ {f} }} }}',
        f'let {q} = DispatchQueue(label: "{q}")\n{q}.async {{ DispatchQueue.main.sync {{ {f} }} }}',
        "let sem = DispatchSemaphore(value: 0)\n"
        f"DispatchQueue.global().async {{ {g}; sem.signal() }}\nsem.wait()",
        f'let {q} = DispatchQueue(label: "{q}")\n{q}.async {{ {q}.async {{ {f} }} }}',
    ]
    return deadlock, safe


def _gen_gcd_deadlock(rng: random.Random) -> Variant:
    q = rng.choice(("worker", "dbQueue", "cacheQueue", "syncQueue", "imageQueue"))
    f, g = rng.sample(_FUNCS, 2)
    deadlock, safe = _deadlock_pool(q, f, g)
    n_bad = rng.randint(1, 3)
    n_ok = 5 - n_bad
    correct = rng.sample(deadlock, n_bad)
    wrong = rng.sample(safe, n_ok)
    return make_multi_choice(
        rng,
        "Каждый фрагмент целиком выполняется в главном потоке iOS-приложения (Swift 5.9). "
        "Какие фрагменты приводят к взаимной блокировке — приложение зависает или падает "
        "из-за sync на очереди, которую ждёт сам вызывающий? Отметьте все такие.",
        correct,
        wrong,
        extra={"language": "swift"},
        explanation="sync на последовательную очередь, которую уже занимает текущий код "
        "(main из main, q из блока q), — дедлок; ожидание семафора, который сигналит блок "
        "в той же занятой очереди, — тоже.",
    )


GCD_DEADLOCK = ItemTemplate(
    id="mobile.gcd_deadlock",
    specialization="mobile",
    topic="concurrency",
    target_grade="senior",
    format=ItemFormat.MULTI_CHOICE,
    generator=_gen_gcd_deadlock,
    a=1.3,
    b=1.6,
    title="GCD: какие вызовы дают дедлок",
    time_limit_s=210,
)

TEMPLATES = (COROUTINES_ORDER, CANCELLATION, GCD_ORDER, GCD_DEADLOCK)
