"""Frontend: порядок вывода в event loop JS (code_output), специфичность CSS (single_choice)."""

from __future__ import annotations

import random
from collections import deque
from collections.abc import Callable
from typing import Any

from ..templates import ItemFormat, ItemTemplate, Variant, make_single_choice

# --------------------------------------------------------------------------- event loop

_LABEL_SETS = (
    tuple("ABCDEFGHJK"),
    tuple("123456789"),
    ("red", "green", "blue", "cyan", "lime", "pink", "gray", "teal", "navy", "gold"),
    ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"),
)

_KINDS = ("sync", "timeout", "promise", "micro", "chain", "await", "timeout_promise")


Stmt = tuple[Any, ...]  # (вид, метки…, задержка)


def _simulate(stmts: list[Stmt]) -> list[str]:
    """Модель event loop браузера/Node: синхронный код → микрозадачи → таймеры по задержке."""
    out: list[str] = []
    micro: deque[Callable[[], None]] = deque()
    timers: list[tuple[int, int, Callable[[], None]]] = []

    def log(label: str) -> Callable[[], None]:
        return lambda: out.append(label)

    def chain(l1: str, l2: str) -> Callable[[], None]:
        def run() -> None:
            out.append(l1)
            micro.append(log(l2))

        return run

    for seq, st in enumerate(stmts):
        kind = st[0]
        if kind == "sync":
            out.append(st[1])
        elif kind == "timeout":
            timers.append((st[2], seq, log(st[1])))
        elif kind in ("promise", "micro"):
            micro.append(log(st[1]))
        elif kind == "chain":
            micro.append(chain(st[1], st[2]))
        elif kind == "await":
            out.append(st[1])
            micro.append(log(st[2]))
        elif kind == "timeout_promise":
            timers.append((st[3], seq, chain(st[1], st[2])))

    def drain() -> None:
        while micro:
            micro.popleft()()

    drain()
    for _, _, cb in sorted(timers, key=lambda t: (t[0], t[1])):
        cb()
        drain()
    return out


def _js(st: Stmt) -> list[str]:
    kind = st[0]
    if kind == "sync":
        return [f"console.log('{st[1]}');"]
    if kind == "timeout":
        return [f"setTimeout(() => console.log('{st[1]}'), {st[2]});"]
    if kind == "promise":
        return [f"Promise.resolve().then(() => console.log('{st[1]}'));"]
    if kind == "micro":
        return [f"queueMicrotask(() => console.log('{st[1]}'));"]
    if kind == "chain":
        return [
            "Promise.resolve()",
            f"  .then(() => console.log('{st[1]}'))",
            f"  .then(() => console.log('{st[2]}'));",
        ]
    if kind == "await":
        return [
            "(async () => {",
            f"  console.log('{st[1]}');",
            "  await null;",
            f"  console.log('{st[2]}');",
            "})();",
        ]
    return [
        "setTimeout(() => {",
        f"  console.log('{st[1]}');",
        f"  Promise.resolve().then(() => console.log('{st[2]}'));",
        f"}}, {st[3]});",
    ]


def _gen_event_loop(rng: random.Random) -> Variant:
    while True:
        labels = list(rng.choice(_LABEL_SETS))
        rng.shuffle(labels)
        n = rng.randint(4, 6)
        stmts: list[Stmt] = []
        used: list[str] = []
        for _ in range(n):
            if not labels:
                break
            kind = rng.choice(_KINDS)
            if kind in ("chain", "await", "timeout_promise") and len(labels) < 2:
                kind = "sync"
            if kind in ("sync", "promise", "micro"):
                st: Stmt = (kind, labels.pop())
            elif kind == "timeout":
                st = (kind, labels.pop(), rng.choice((0, 0, 10, 100)))
            elif kind in ("chain", "await"):
                st = (kind, labels.pop(), labels.pop())
            else:
                st = (kind, labels.pop(), labels.pop(), rng.choice((0, 10, 50)))
            stmts.append(st)
            used += [s for s in st[1:] if isinstance(s, str)]
        out = _simulate(stmts)
        kinds = {s[0] for s in stmts}
        # вывод должен отличаться от порядка в коде и содержать асинхронность
        if out != used and kinds & {"timeout", "timeout_promise"} and len(kinds) >= 3:
            break
    lines: list[str] = []
    for st in stmts:
        lines += _js(st)
    return Variant(
        prompt=(
            "Что выведет этот код в консоль (браузер или Node.js)? "
            "Перечислите значения в порядке вывода через пробел."
        ),
        key=" ".join(out),
        code="\n".join(lines),
        extra={"language": "javascript"},
        explanation="Сначала синхронный код, затем все микрозадачи, затем таймеры по задержке.",
    )


EVENT_LOOP = ItemTemplate(
    id="frontend.event_loop_order",
    specialization="frontend",
    topic="javascript_async",
    target_grade="senior",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_event_loop,
    a=1.6,
    b=1.2,
    title="Порядок вывода: микрозадачи и таймеры",
    time_limit_s=240,
)

# --------------------------------------------------------------------------- специфичность CSS

_COLORS = (
    "crimson",
    "royalblue",
    "seagreen",
    "darkorange",
    "purple",
    "teal",
    "goldenrod",
    "slategray",
    "tomato",
    "navy",
    "olive",
    "hotpink",
)
_ELEMENTS = (("p", "div"), ("span", "label"), ("li", "ul"), ("a", "nav"), ("button", "form"))
_CLASSES = ("title", "active", "card", "note", "big", "warn", "muted", "primary", "item", "link")
_IDS = ("main", "hero", "cta", "promo", "header", "total", "login")
_WRAPS = ("wrap", "box", "panel", "menu", "content", "section")


def _gen_css(rng: random.Random) -> Variant:
    tag, parent = rng.choice(_ELEMENTS)
    c1, c2 = rng.sample(_CLASSES, 2)
    pid = rng.choice(_IDS)
    wrap = rng.choice(_WRAPS)
    # (селектор, специфичность (id, class, type))
    pool = [
        (tag, (0, 0, 1)),
        (f".{c1}", (0, 1, 0)),
        (f".{c2}", (0, 1, 0)),
        (f"{tag}.{c1}", (0, 1, 1)),
        (f".{c1}.{c2}", (0, 2, 0)),
        (f"#{pid}", (1, 0, 0)),
        (f"{parent} {tag}", (0, 0, 2)),
        (f".{wrap} {tag}", (0, 1, 1)),
        (f".{wrap} .{c2}", (0, 2, 0)),
        (f"{parent}.{wrap} > {tag}.{c1}", (0, 2, 2)),
        (f"#{pid}.{c1}", (1, 1, 0)),
        (f"{tag}[id]", (0, 1, 1)),
        (f"{parent} > .{c2}", (0, 1, 1)),
    ]
    while True:
        rules = rng.sample(pool, 4)
        colors = rng.sample(_COLORS, 4)
        important = rng.randrange(4) if rng.random() < 0.2 else -1
        ranked = sorted(range(4), key=lambda i: (i == important, rules[i][1], i), reverse=True)
        winner = ranked[0]
        # без !important победитель должен быть «интересным»: не всегда последнее правило
        if important >= 0 or winner != 3 or rng.random() < 0.3:
            break
    css_lines = []
    for i, ((sel, _), color) in enumerate(zip(rules, colors, strict=True)):
        imp = " !important" if i == important else ""
        css_lines.append(f"{sel} {{ color: {color}{imp}; }}")
    html = (
        f'<{parent} class="{wrap}">\n'
        f'  <{tag} id="{pid}" class="{c1} {c2}">Текст</{tag}>\n'
        f"</{parent}>"
    )
    code = f"<!-- HTML -->\n{html}\n\n/* CSS */\n" + "\n".join(css_lines)
    correct = colors[winner]
    distractors = [c for c in colors if c != correct]
    return make_single_choice(
        rng,
        f'Какого цвета будет текст элемента <{tag} id="{pid}">?',
        correct,
        distractors,
        code=code,
        extra={"language": "css"},
        explanation=(
            "Побеждает !important, затем большая специфичность, при равенстве — правило ниже."
        ),
    )


CSS_SPECIFICITY = ItemTemplate(
    id="frontend.css_specificity",
    specialization="frontend",
    topic="css",
    target_grade="junior",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_css,
    a=1.2,
    b=-0.3,
    title="Какое CSS-правило победит",
    time_limit_s=150,
)

TEMPLATES = [EVENT_LOOP, CSS_SPECIFICITY]
