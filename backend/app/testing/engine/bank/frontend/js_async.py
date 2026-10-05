"""Frontend / асинхронный JavaScript: цепочка промисов с ошибками, Promise.all/race/allSettled/any.

Порядок микрозадач и таймеров (тема примера frontend.event_loop_order) здесь не проверяется:
в задачах одна цепочка или комбинаторы, выполняемые последовательно через await.
"""

from __future__ import annotations

import random

from ...templates import ItemFormat, ItemTemplate, Variant

_NODE_PROMPT = (
    "Что выведет этот код в Node.js? Перечислите выведенные значения в порядке вывода "
    "через пробел (сообщения выводятся как есть, без кавычек)."
)

# --------------------------------------------------------------------------- цепочка промисов


class _NanError(Exception):
    """В цепочке получился NaN — вариант пересобирается (неинтересный ответ)."""


def _num(x: int | None, op: str, k: int) -> int:
    if x is None:
        raise _NanError
    return x + k if op == "+" else x * k


def _js_str(v: object) -> str:
    return "undefined" if v is None else str(v)


def _chain_variant(rng: random.Random) -> tuple[list[str], list[str], bool]:
    """Одна попытка: (строки кода, вывод, была ли ошибка в цепочке)."""
    start_ok = rng.random() < 0.7
    v0 = rng.randint(1, 9)
    lines = [f"Promise.resolve({v0})" if start_ok else f"Promise.reject(new Error('S{v0}'))"]
    # состояние: ok=True — val значение (int или None=undefined); ok=False — val это message
    ok: bool = start_ok
    val: int | str | None = v0 if start_ok else f"S{v0}"
    outs: list[str] = []
    had_error = not start_ok
    for _ in range(rng.randint(4, 6)):
        kind = rng.choice(
            ("add", "add", "throw", "catch", "log", "finally", "then2", "reject", "fin_ret")
        )
        k = rng.randint(2, 9)
        if kind == "add":
            lines.append(f"  .then((x) => x + {k})")
            if ok:
                val = _num(val, "+", k)  # type: ignore[arg-type]
        elif kind == "throw":
            lines += ["  .then((x) => {", "    throw new Error('E' + x);", "  })"]
            if ok:
                ok, val, had_error = False, f"E{_js_str(val)}", True
        elif kind == "reject":
            lines.append("  .then((x) => Promise.reject(new Error('R' + x)))")
            if ok:
                ok, val, had_error = False, f"R{_js_str(val)}", True
        elif kind == "catch":
            lines += [
                "  .catch((e) => {",
                "    console.log('catch', e.message);",
                f"    return {k};",
                "  })",
            ]
            if not ok:
                outs += ["catch", str(val)]
                ok, val = True, k
        elif kind == "log":
            lines.append("  .then((x) => console.log('then', x))")
            if ok:
                outs += ["then", _js_str(val)]
                val = None
        elif kind == "finally":
            lines.append("  .finally(() => console.log('finally'))")
            outs.append("finally")
        elif kind == "fin_ret":
            lines.append(f"  .finally(() => {k * 10})")
        else:  # then с двумя аргументами
            lines.append(f"  .then((x) => x * {k}, (e) => -{k})")
            if ok:
                val = _num(val, "*", k)  # type: ignore[arg-type]
            else:
                ok, val = True, -k
    lines += [
        "  .then(",
        "    (v) => console.log('done', v),",
        "    (e) => console.log('fail', e.message),",
        "  );",
    ]
    outs += ["done", _js_str(val)] if ok else ["fail", str(val)]
    return lines, outs, had_error


def _gen_promise_chain(rng: random.Random) -> Variant:
    while True:
        try:
            lines, outs, had_error = _chain_variant(rng)
        except _NanError:
            continue
        if had_error:
            break
    return Variant(
        prompt=_NODE_PROMPT,
        key=" ".join(outs),
        code="\n".join(lines),
        extra={"language": "javascript"},
        explanation=(
            "Отклонение пропускает then без второго аргумента до ближайшего catch; catch "
            "возвращает обычное значение; finally не меняет результат цепочки."
        ),
    )


JS_PROMISE_CHAIN = ItemTemplate(
    id="frontend.js_promise_chain",
    specialization="frontend",
    topic="javascript_async",
    target_grade="middle",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_promise_chain,
    a=1.5,
    b=0.4,
    title="Цепочка промисов: then, catch, finally и ошибки",
    time_limit_s=210,
)

# --------------------------------------------------------------------------- комбинаторы

_COMBINATORS = ("all", "allSettled", "race", "any")


def _combinator_result(kind: str, items: list[tuple[str, int | None, bool]]) -> list[str]:
    """items: (метка, задержка или None для обычного значения, отклоняется ли)."""

    def t(it: tuple[str, int | None, bool]) -> int:
        return -1 if it[1] is None else it[1]

    by_time = sorted(items, key=t)
    if kind == "all":
        rejected = [it for it in by_time if it[2]]
        if rejected:
            return ["all", "error", rejected[0][0]]
        return ["all", "+".join(it[0] for it in items)]
    if kind == "allSettled":
        parts = [("r:" if it[2] else "f:") + it[0] for it in items]
        return ["allSettled", *parts]
    if kind == "race":
        first = by_time[0]
        return ["race", "error", first[0]] if first[2] else ["race", first[0]]
    fulfilled = [it for it in by_time if not it[2]]
    if fulfilled:
        return ["any", fulfilled[0][0]]
    return ["any", "error", "AggregateError", str(len(items))]


def _item_js(it: tuple[str, int | None, bool]) -> str:
    label, delay, fail = it
    if delay is None:
        return f"'{label}'"
    return f"wait({delay}, '{label}', true)" if fail else f"wait({delay}, '{label}')"


def _block_js(kind: str, items: list[tuple[str, int | None, bool]]) -> list[str]:
    arr = ", ".join(_item_js(it) for it in items)
    if kind == "all":
        ok = "console.log('all', v.join('+'));"
        err = "console.log('all', 'error', e.message);"
    elif kind == "allSettled":
        ok = "console.log('allSettled', ...v.map(show));"
        err = "console.log('allSettled', 'error');"
    elif kind == "race":
        ok = "console.log('race', v);"
        err = "console.log('race', 'error', e.message);"
    else:
        ok = "console.log('any', v);"
        err = "console.log('any', 'error', e.name, e.errors.length);"
    return [
        "  try {",
        f"    const v = await Promise.{kind}([{arr}]);",
        f"    {ok}",
        "  } catch (e) {",
        f"    {err}",
        "  }",
    ]


def _gen_combinators(rng: random.Random) -> Variant:
    kinds = rng.sample(_COMBINATORS, rng.randint(2, 3))
    letters = list("abcdefghkmnpqrstuvwxyz")
    rng.shuffle(letters)
    lines = [
        "const wait = (ms, value, fail) =>",
        "  new Promise((resolve, reject) =>",
        "    setTimeout(() => (fail ? reject(new Error(value)) : resolve(value)), ms),",
        "  );",
    ]
    if "allSettled" in kinds:
        lines += [
            "const show = (r) =>",
            "  r.status === 'fulfilled' ? 'f:' + r.value : 'r:' + r.reason.message;",
        ]
    lines.append("(async () => {")
    outs: list[str] = []
    for kind in kinds:
        n = rng.randint(2, 3)
        delays = rng.sample((20, 40, 60, 80, 100), n)
        items: list[tuple[str, int | None, bool]] = []
        for d in delays:
            items.append((letters.pop(), d, rng.random() < 0.45))
        if kind == "any" and rng.random() < 0.3:
            items = [(lbl, d, True) for lbl, d, _ in items]
        if kind in ("race", "all", "any") and rng.random() < 0.2:
            items.insert(rng.randrange(len(items) + 1), (letters.pop(), None, False))
        lines += _block_js(kind, items)
        outs += _combinator_result(kind, items)
    lines.append("})();")
    return Variant(
        prompt=_NODE_PROMPT,
        key=" ".join(outs),
        code="\n".join(lines),
        extra={"language": "javascript"},
        explanation=(
            "all — значения в порядке массива или первая по времени ошибка; race — первый "
            "завершившийся; any — первый успешный или AggregateError; allSettled — все статусы; "
            "обычное значение в массиве готово раньше любого таймера."
        ),
    )


JS_PROMISE_COMBINATORS = ItemTemplate(
    id="frontend.js_promise_combinators",
    specialization="frontend",
    topic="javascript_async",
    target_grade="senior",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_combinators,
    a=1.6,
    b=1.2,
    title="Promise.all, race, allSettled, any с ошибками",
    time_limit_s=270,
)

TEMPLATES = (JS_PROMISE_CHAIN, JS_PROMISE_COMBINATORS)
