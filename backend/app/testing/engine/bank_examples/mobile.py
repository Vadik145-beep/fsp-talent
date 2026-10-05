"""Mobile: жизненный цикл Android Activity (ordering), ошибка в Kotlin-коде (find_bug_line)."""

from __future__ import annotations

import random

from ..templates import ItemFormat, ItemTemplate, Variant, make_ordering

# --------------------------------------------------------------------------- жизненный цикл

_ACTIVITIES = (
    "MainActivity",
    "LoginActivity",
    "ProfileActivity",
    "CartActivity",
    "SettingsActivity",
    "DetailsActivity",
    "ChatActivity",
    "MapActivity",
)
_FRAGMENTS = ("ProfileFragment", "FeedFragment", "CartFragment", "SearchFragment")


def _scenarios(a: str, b: str, f: str) -> list[tuple[str, list[str]]]:
    return [
        (
            f"Пользователь запускает приложение, открывается {a}, затем он нажимает кнопку Home.",
            ["onCreate()", "onStart()", "onResume()", "onPause()", "onStop()"],
        ),
        (
            f"{a} открыта, пользователь нажимает «Назад» и полностью выходит из неё.",
            ["onPause()", "onStop()", "onDestroy()"],
        ),
        (
            f"{a} свёрнута кнопкой Home, пользователь возвращается в приложение "
            f"и затем снова сворачивает его.",
            ["onRestart()", "onStart()", "onResume()", "onPause()", "onStop()"],
        ),
        (
            f"Пользователь поворачивает экран, пока открыта {a} "
            "(configChanges не заданы, Android 9+).",
            [
                "onPause()",
                "onStop()",
                "onSaveInstanceState()",
                "onDestroy()",
                "onCreate()",
                "onStart()",
                "onRestoreInstanceState()",
                "onResume()",
            ],
        ),
        (
            f"Из {a} запускается полноэкранная {b}.",
            [
                f"{a}.onPause()",
                f"{b}.onCreate()",
                f"{b}.onStart()",
                f"{b}.onResume()",
                f"{a}.onStop()",
            ],
        ),
        (
            f"В открытой {b} (запущена из {a}) пользователь нажимает «Назад».",
            [
                f"{b}.onPause()",
                f"{a}.onRestart()",
                f"{a}.onStart()",
                f"{a}.onResume()",
                f"{b}.onStop()",
                f"{b}.onDestroy()",
            ],
        ),
        (
            f"В {a} транзакцией добавляется {f}; активити уже в состоянии RESUMED.",
            [
                "onAttach()",
                "onCreate()",
                "onCreateView()",
                "onViewCreated()",
                "onStart()",
                "onResume()",
            ],
        ),
        (
            f"{f} показан в {a}; его заменяют другим фрагментом без addToBackStack.",
            ["onPause()", "onStop()", "onDestroyView()", "onDestroy()", "onDetach()"],
        ),
    ]


def _gen_lifecycle(rng: random.Random) -> Variant:
    a, b = rng.sample(_ACTIVITIES, 2)
    f = rng.choice(_FRAGMENTS)
    text, steps = rng.choice(_scenarios(a, b, f))
    is_fragment = "onAttach()" in steps or "onDetach()" in steps
    subject = "фрагмента" if is_fragment else "активити"
    return make_ordering(
        rng,
        f"{text}\nРасставьте колбэки {subject} в порядке их вызова.",
        steps,
        extra={"platform": "android"},
        explanation="Порядок по документации Android: " + " → ".join(steps),
    )


ANDROID_LIFECYCLE = ItemTemplate(
    id="mobile.android_lifecycle",
    specialization="mobile",
    topic="android_lifecycle",
    target_grade="junior",
    format=ItemFormat.ORDERING,
    generator=_gen_lifecycle,
    a=1.3,
    b=-0.1,
    title="Порядок колбэков жизненного цикла",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- Kotlin: найди ошибку

_FILLERS = (
    'println("{f}: start")',
    "val startedAt = System.nanoTime()",
    "// TODO: вынести в репозиторий",
    "// входные данные приходят из API",
)


def _bug_programs(rng: random.Random, f: str) -> tuple[str, list[str], int]:
    """Возвращает (что должна делать функция, строки тела без сигнатуры, индекс строки с багом)."""
    kind = rng.randrange(5)
    xs, acc, i = rng.choice(
        (("items", "sum", "i"), ("values", "total", "idx"), ("nums", "acc", "k"))
    )
    if kind == 0:
        sig = f"fun {f}({xs}: List<Int>): Int {{"
        body = [
            f"    var {acc} = 0",
            f"    for ({i} in 0..{xs}.size) {{",
            f"        {acc} += {xs}[{i}]",
            "    }",
            f"    return {acc}",
        ]
        return f"возвращает сумму элементов списка {xs}", [sig, *body, "}"], 2
    if kind == 1:
        done, total = rng.choice((("done", "total"), ("passed", "all"), ("closed", "count")))
        ratio = rng.choice(("ratio", "share", "part"))
        sig = f"fun {f}({done}: Int, {total}: Int): Double {{"
        body = [
            f"    if ({total} == 0) return 0.0",
            f"    val {ratio} = {done} / {total}",
            f"    return {ratio} * 100.0",
        ]
        return (
            f"возвращает процент {done} от {total} (от 0.0 до 100.0)",
            [sig, *body, "}"],
            2,
        )
    if kind == 2:
        limit = rng.choice((100, 500, 1000, 2500))
        cnt, o = rng.choice((("count", "order"), ("n", "o"), ("result", "item")))
        sig = f"fun {f}(orders: List<Order>): Int {{"
        body = [
            f"    var {cnt} = 0",
            f"    for ({o} in orders) {{",
            f"        if ({o}.amount > {limit}) {{",
            f"            {cnt}++",
            "        }",
            "    }",
            f"    return {cnt}",
        ]
        return (
            f"возвращает число заказов на сумму не меньше {limit}",
            [sig, *body, "}"],
            3,
        )
    if kind == 3:
        prices, name = rng.choice((("prices", "name"), ("catalog", "sku"), ("tariffs", "code")))
        sig = f"fun {f}({prices}: Map<String, Int>, {name}: String): Int {{"
        body = [
            f"    val key = {name}.trim().lowercase()",
            f"    val price = {prices}[key]!!",
            "    return price",
        ]
        return (
            f"возвращает цену по ключу {name} или 0, если такого ключа нет в {prices}",
            [sig, *body, "}"],
            2,
        )
    sig = f"fun {f}({xs}: List<String>): String? {{"
    body = [
        f"    if ({xs}.isEmpty()) return null",
        f"    return {xs}[{xs}.size]",
    ]
    return f"возвращает последний элемент {xs} или null, если список пуст", [sig, *body, "}"], 2


def _gen_kotlin_bug(rng: random.Random) -> Variant:
    f = rng.choice(("calc", "compute", "summarize", "resolve", "evaluate", "report", "pick"))
    desc, lines, bug_idx = _bug_programs(rng, f)
    # 0–2 безобидные строки сразу после сигнатуры сдвигают номер строки с ошибкой
    k = rng.choice((0, 0, 1, 1, 2))
    fillers = ["    " + s.replace("{f}", f) for s in rng.sample(_FILLERS, k)]
    lines = [lines[0], *fillers, *lines[1:]]
    bug_line = bug_idx + k + 1  # 1-based
    return Variant(
        prompt=(
            f"Функция {f} {desc}. В какой строке ошибка, из-за которой она падает "
            "или возвращает неверный результат? Укажите номер строки."
        ),
        key=bug_line,
        code="\n".join(lines),
        extra={"language": "kotlin", "line_count": len(lines)},
        explanation=f"Ошибка в строке {bug_line}: {lines[bug_line - 1].strip()}",
    )


KOTLIN_BUG = ItemTemplate(
    id="mobile.kotlin_find_bug",
    specialization="mobile",
    topic="kotlin",
    target_grade="middle",
    format=ItemFormat.FIND_BUG_LINE,
    generator=_gen_kotlin_bug,
    a=1.4,
    b=0.4,
    title="Найди строку с ошибкой (Kotlin)",
    time_limit_s=180,
)

TEMPLATES = [ANDROID_LIFECYCLE, KOTLIN_BUG]
