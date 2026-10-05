"""Mobile / многопоточность: независимая сверка.

Kotlin-корутины в runBlocking и главная очередь GCD — однопоточные циклы событий.
Код задачи транслируется в Python asyncio, который выполняется на цикле событий
с виртуальными часами (время прыгает к ближайшему таймеру): launch/async → задача
(старт через очередь FIFO), delay → asyncio.sleep, join/await → await задачи,
withTimeout(OrNull) → asyncio.wait_for, main.async → call_soon, asyncAfter → call_later.
Отличие asyncio от Kotlin — отмена: в Kotlin любой suspend-вызов в отменённой корутине
сразу бросает CancellationException, поэтому delay транслируется в обёртку kdelay,
которая это проверяет; withContext(NonCancellable) — обычный asyncio.sleep.
"""

import asyncio
import re

import pytest

from app.testing.engine.bank.mobile import concurrency
from app.testing.engine.templates import check

SEEDS = range(120)


class VirtualLoop(asyncio.SelectorEventLoop):
    """Цикл событий с виртуальным временем: никаких реальных ожиданий."""

    def __init__(self):
        super().__init__()
        self._vt = 0.0

    def time(self):
        return self._vt

    def _run_once(self):
        if not self._ready and self._scheduled:
            self._vt = max(self._vt, self._scheduled[0]._when)
        super()._run_once()


def _run(coro_factory):
    loop = VirtualLoop()
    try:
        return loop.run_until_complete(coro_factory())
    finally:
        loop.close()


# --------------------------------------------------------------------------- Kotlin → Python


def _parse(lines: list[str], i: int) -> tuple[list, int]:
    """Дерево блоков по фигурным скобкам. «} finally {» закрывает блок и открывает соседний."""
    nodes, i, _ = _parse_inner(lines, i)
    return nodes, i


def _parse_inner(lines: list[str], i: int) -> tuple[list, int, bool]:
    nodes: list = []
    while i < len(lines):
        ln = lines[i].strip()
        if not ln or ln.startswith("import "):
            i += 1
            continue
        if ln == "}":
            return nodes, i + 1, False
        if ln.startswith("}") and ln.endswith("{"):
            return nodes, i, True  # строка-продолжение не съедена
        if ln.endswith("{") or ln.endswith("->"):
            head = ln if ln.endswith("->") else ln.rstrip("{").strip()
            sub, i, cont = _parse_inner(lines, i + 1)
            nodes.append(("block", head, sub))
            while cont:
                head2 = lines[i].strip()[1:-1].strip()
                sub2, i, cont = _parse_inner(lines, i + 1)
                nodes.append(("block", head2, sub2))
            continue
        nodes.append(("stmt", ln))
        i += 1
    return nodes, i, False


_COUNTER = [0]


def _kt_emit(nodes: list, pad: str, nc: bool = False) -> list[str]:
    out: list[str] = []
    for node in nodes:
        if node[0] == "block":
            head, sub = node[1], node[2]
            if m := re.fullmatch(r"val (\w+) = (launch|async)", head):
                out.append(f"{pad}async def _{m[1]}():")
                out += _kt_emit(sub, pad + "    ", nc) or [f"{pad}    pass"]
                out.append(f"{pad}{m[1]} = asyncio.ensure_future(_{m[1]}())")
                out.append(f"{pad}tasks.append({m[1]})")
            elif m := re.fullmatch(r"val (\w+) = withTimeout(OrNull)?\((\d+)\)", head):
                _COUNTER[0] += 1
                fn = f"_blk{_COUNTER[0]}"
                out.append(f"{pad}async def {fn}():")
                out += _kt_emit(sub, pad + "    ", nc)
                call = f"await asyncio.wait_for({fn}(), {int(m[3]) / 1000})"
                if m[2]:
                    out += [
                        f"{pad}try:",
                        f"{pad}    {m[1]} = {call}",
                        f"{pad}except TimeoutError:",
                        f"{pad}    {m[1]} = None",
                    ]
                else:
                    out.append(f"{pad}{m[1]} = {call}")
            elif m := re.fullmatch(r"repeat\((\d+)\) \{ i ->", head):
                out.append(f"{pad}for i in range({m[1]}):")
                out += _kt_emit(sub, pad + "    ", nc)
            elif head == "try":
                out.append(f"{pad}try:")
                out += _kt_emit(sub, pad + "    ", nc)
            elif head == "finally":
                out.append(f"{pad}finally:")
                out += _kt_emit(sub, pad + "    ", nc) or [f"{pad}    pass"]
            elif head == "catch (e: TimeoutCancellationException)":
                out.append(f"{pad}except TimeoutError:")
                out += _kt_emit(sub, pad + "    ", nc)
            elif head == "withContext(NonCancellable)":
                out.append(f"{pad}if True:")
                out += _kt_emit(sub, pad + "    ", nc=True)
            else:
                raise AssertionError(head)
            continue
        st = node[1]
        if m := re.fullmatch(r'println\("(.*)"\)', st):
            out.append(f'{pad}out.append(f"{m[1].replace("$i", "{i}")}")')
        elif m := re.fullmatch(r"delay\((\d+)\)", st):
            sleep = "asyncio.sleep" if nc else "kdelay"
            out.append(f"{pad}await {sleep}({int(m[1]) / 1000})")
        elif m := re.fullmatch(r"(\w+)\.join\(\)", st):
            out.append(f"{pad}await join({m[1]})")
        elif m := re.fullmatch(r"println\((\w+)\.await\(\) \+ (\d+)\)", st):
            out.append(f"{pad}out.append(str((await {m[1]}) + {m[2]}))")
        elif re.fullmatch(r"\d+", st):
            out.append(f"{pad}return {st}")
        elif m := re.fullmatch(r'"(\w+)"', st):
            out.append(f'{pad}return "{m[1]}"')
        elif m := re.fullmatch(r'println\((\w+) \?: "(\w+)"\)', st):
            out.append(f'{pad}out.append({m[1]} if {m[1]} is not None else "{m[2]}")')
        elif m := re.fullmatch(r"println\((\w+)\)", st):
            out.append(f"{pad}out.append({m[1]})")
        elif st == "job.cancel()":
            out.append(f"{pad}kcancel(job)")
        elif st in ("job.cancelAndJoin()", "job.cancel(); job.join()"):
            out += [f"{pad}kcancel(job)", f"{pad}await join(job)"]
        else:
            raise AssertionError(st)
    return out


def run_kotlin(code: str) -> str:
    lines = code.split("\n")
    nodes, _ = _parse(lines, 0)
    (head, body) = nodes[0][1], nodes[0][2]
    assert head == "fun main() = runBlocking"
    src = [
        "async def main():",
        "    tasks = []",
        *_kt_emit(body, "    "),
        "    await asyncio.gather(*tasks, return_exceptions=True)",
    ]
    out: list[str] = []
    cancelled: set = set()

    async def kdelay(sec):
        if asyncio.current_task() in cancelled:
            raise asyncio.CancelledError  # suspend в отменённой корутине Kotlin
        await asyncio.sleep(sec)

    def kcancel(task):
        cancelled.add(task)
        task.cancel()

    async def join(task):
        # await завершённой задачи не приостанавливает, как join() в Kotlin
        try:
            await task
        except asyncio.CancelledError:
            if asyncio.current_task().cancelling():
                raise

    scope = {"asyncio": asyncio, "out": out, "kdelay": kdelay, "kcancel": kcancel, "join": join}
    exec("\n".join(src), scope)
    _run(scope["main"])
    return " ".join(out)


def test_coroutines_order_independent():
    t = concurrency.COROUTINES_ORDER
    for seed in SEEDS:
        inst = t.generate(seed)
        got = run_kotlin(inst.public.code)
        assert check(inst, got), (seed, inst.public.code, got, inst.key)


def test_coroutines_order_manual_example():
    # Пример из документации kotlinx.coroutines («Your first coroutine»): World! после Hello
    code = "\n".join(
        [
            "fun main() = runBlocking {",
            "    val job1 = launch {",
            "        delay(1000)",
            '        println("World")',
            "    }",
            '    println("Hello")',
            "}",
        ]
    )
    assert run_kotlin(code) == "Hello World"
    main = [("launch", "job1"), ("print", "Hello")]
    assert concurrency.simulate_coroutines(main, {"job1": [("delay", 1000), ("print", "World")]})[
        0
    ] == ["Hello", "World"]


def test_cancellation_independent():
    t = concurrency.CANCELLATION
    for seed in SEEDS:
        inst = t.generate(seed)
        got = run_kotlin(inst.public.code)
        assert check(inst, got), (seed, inst.public.code, got, inst.key)


def test_cancellation_docs_examples():
    # «Cancellation and timeouts», kotlinx.coroutines: пример с finally и cancelAndJoin
    base = {
        "d": 500,
        "t": 1300,
        "n": 1000,
        "tick": "tick",
        "stop": "tired",
        "done": "quit",
        "cleanup": "finally",
        "caught": "x",
        "value": "Done",
        "fd": 100,
        "join_style": 0,
    }
    p = {**base, "mode": "cancel_join", "finally": "plain"}
    assert concurrency.simulate_cancellation(p) == [
        "tick0",
        "tick1",
        "tick2",
        "tired",
        "finally",
        "quit",
    ]
    # «Timeout»: withTimeoutOrNull(1300) с шагом 500 → три строки и null
    p = {**base, "mode": "timeout_null", "finally": None}
    assert concurrency.simulate_cancellation(p) == ["tick0", "tick1", "tick2", "timeout"]
    # suspend в finally отменённой корутины сразу бросает исключение; NonCancellable — нет
    p = {**base, "mode": "cancel_join", "finally": "suspend"}
    assert concurrency.simulate_cancellation(p)[-2:] == ["tired", "quit"]
    p = {**base, "mode": "cancel_only", "finally": "noncancellable"}
    assert concurrency.simulate_cancellation(p)[-3:] == ["tired", "quit", "finally"]


# --------------------------------------------------------------------------- GCD: порядок


def _sw_emit(nodes: list, pad: str) -> list[str]:
    out: list[str] = []
    for node in nodes:
        if node[0] == "block":
            head, sub = node[1], node[2]
            _COUNTER[0] += 1
            fn = f"_b{_COUNTER[0]}"
            out.append(f"{pad}def {fn}():")
            out += _sw_emit(sub, pad + "    ") or [f"{pad}    pass"]
            if head == "DispatchQueue.main.async":
                out.append(f"{pad}loop.call_soon({fn})")
            elif m := re.fullmatch(
                r"DispatchQueue\.main\.asyncAfter\(deadline: \.now\(\) \+ ([\d.]+)\)", head
            ):
                out.append(f"{pad}loop.call_later({m[1]}, {fn})")
            else:
                raise AssertionError(head)
            continue
        st = node[1]
        if m := re.fullmatch(r'print\("(\w+)"\)', st):
            out.append(f'{pad}out.append("{m[1]}")')
        elif m := re.fullmatch(
            r'(?:queue|DispatchQueue\.global\(\))\.sync \{ print\("(\w+)"\) \}', st
        ):
            out.append(f'{pad}out.append("{m[1]}")')  # sync выполняется сразу
        elif m := re.fullmatch(r'DispatchQueue\.main\.async \{ print\("(\w+)"\) \}', st):
            out.append(f'{pad}loop.call_soon(out.append, "{m[1]}")')
        elif m := re.fullmatch(
            r"DispatchQueue\.main\.asyncAfter\(deadline: \.now\(\) \+ ([\d.]+)\) "
            r'\{ print\("(\w+)"\) \}',
            st,
        ):
            out.append(f'{pad}loop.call_later({m[1]}, out.append, "{m[2]}")')
        elif st in ("super.viewDidLoad()",) or st.startswith("let queue = DispatchQueue"):
            continue
        else:
            raise AssertionError(st)
    return out


def run_gcd(code: str) -> str:
    nodes, _ = _parse(code.split("\n"), 0)
    assert nodes[0][1] == "override func viewDidLoad()"
    src = ["def view_did_load():", *_sw_emit(nodes[0][2], "    ")]
    loop = VirtualLoop()
    out: list[str] = []
    scope = {"loop": loop, "out": out}
    exec("\n".join(src), scope)
    try:
        loop.call_soon(scope["view_did_load"])
        loop.run_until_complete(asyncio.sleep(100))
    finally:
        loop.close()
    return " ".join(out)


def test_gcd_order_independent():
    t = concurrency.GCD_ORDER
    for seed in SEEDS:
        inst = t.generate(seed)
        got = run_gcd(inst.public.code)
        assert check(inst, got), (seed, inst.public.code, got, inst.key)


def test_gcd_order_manual_example():
    code = "\n".join(
        [
            "override func viewDidLoad() {",
            "    super.viewDidLoad()",
            '    let queue = DispatchQueue(label: "q")',
            '    print("A")',
            "    DispatchQueue.main.async {",
            '        print("B")',
            '        DispatchQueue.main.async { print("C") }',
            "    }",
            '    DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) { print("D") }',
            '    queue.sync { print("E") }',
            '    DispatchQueue.main.async { print("F") }',
            "}",
        ]
    )
    # главная очередь последовательная FIFO; sync на другой очереди — сразу
    assert run_gcd(code) == "A E B F C D"


# --------------------------------------------------------------------------- GCD: дедлоки


def _split_call(s: str):
    m = re.fullmatch(
        r"(DispatchQueue\.main|DispatchQueue\.global\(\)|\w+)\.(sync|async) \{ (.*) \}", s
    )
    return (m[1], m[2], m[3]) if m else None


def deadlocks(snippet: str) -> bool:
    """Модель очередей: держим множество последовательных очередей, занятых текущим кодом."""
    lines = snippet.split("\n")
    serial = {"DispatchQueue.main": True, "DispatchQueue.global()": False}
    stmts: list[str] = []
    for ln in lines:
        if m := re.fullmatch(
            r'let (\w+) = DispatchQueue\(label: "\w+"(, attributes: \.concurrent)?\)', ln
        ):
            serial[m[1]] = m[2] is None
        elif ln != "let sem = DispatchSemaphore(value: 0)":
            stmts.append(ln)
    pending: list[tuple[str, frozenset]] = []
    state = {"signaled": False, "dead": False}

    def run(code: str, held: frozenset) -> None:
        for part in [p.strip() for p in code.split(";")] if not _split_call(code) else [code]:
            call = _split_call(part)
            if call is None:
                if part == "sem.signal()":
                    state["signaled"] = True
                continue
            q, kind, inner = call
            q_held = frozenset({q}) if serial[q] else frozenset()
            if kind == "sync":
                if serial[q] and q in held:
                    state["dead"] = True
                    return
                run(inner, held | q_held)
            else:
                pending.append((inner, q_held))

    waits = False
    for st in stmts:
        if st == "sem.wait()":
            waits = True
            continue
        run(st, frozenset({"DispatchQueue.main"}))
    if state["dead"]:
        return True
    if waits:
        # главный поток заблокирован: блоки главной очереди выполниться не могут
        for inner, held in list(pending):
            if "DispatchQueue.main" not in held:
                run(inner, held)
        return not state["signaled"]
    while pending:
        inner, held = pending.pop(0)
        run(inner, held)
    return state["dead"]


def test_gcd_deadlock_independent():
    t = concurrency.GCD_DEADLOCK
    for seed in SEEDS:
        inst = t.generate(seed)
        expected = {i for i, o in enumerate(inst.public.options) if deadlocks(o)}
        assert expected == set(inst.key), (seed, inst.public.options)


def test_gcd_deadlock_manual_examples():
    assert deadlocks("DispatchQueue.main.sync { f() }")
    assert not deadlocks("DispatchQueue.main.async { f() }")
    assert deadlocks('let q = DispatchQueue(label: "q")\nq.async { q.sync { f() } }')
    assert not deadlocks(
        'let q = DispatchQueue(label: "q", attributes: .concurrent)\nq.sync { q.sync { f() } }'
    )


@pytest.mark.parametrize("template", concurrency.TEMPLATES, ids=lambda t: t.id)
def test_concurrency_answers_vary(template):
    keys = {repr(template.generate(s).key) for s in range(100)}
    assert len(keys) >= 20
