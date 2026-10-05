"""Frontend / DOM-события: target и currentTarget при делегировании, порядок фаз
погружения и всплытия, stopPropagation / stopImmediatePropagation / once.

Код задач — HTML + JS, который выполняется как есть; тест прогоняет его в jsdom.
"""

from __future__ import annotations

import random

from ...templates import ItemFormat, ItemTemplate, Variant, make_ordering

_WORDS = (
    "kiwi",
    "plum",
    "lime",
    "pear",
    "fig",
    "date",
    "nut",
    "corn",
    "rice",
    "bean",
    "mint",
    "sage",
)
_ELEMENT_IDS = (
    ("page", "form", "send"),
    ("app", "card", "buy"),
    ("layout", "panel", "save"),
    ("root", "toolbar", "ok"),
    ("shell", "dialog", "close"),
    ("main", "row", "like"),
)


def _code(html: str, js: list[str]) -> str:
    return "<!-- HTML -->\n" + html + "\n\n// JS\n" + "\n".join(js)


# --------------------------------------------------------------------------- target и currentTarget

_MENU_ITEMS = ("Tea", "Coffee", "Juice", "Water", "Cocoa", "Milk", "Soda", "Kvass")


def _gen_delegation(rng: random.Random) -> Variant:
    list_id = rng.choice(("menu", "list", "catalog", "cart", "nav", "options"))
    n = rng.randint(3, 4)
    names = rng.sample(_MENU_ITEMS, n)
    ids = rng.sample(range(2, 99), n)
    prices = [rng.choice(range(50, 400, 10)) for _ in range(n)]
    html_lines = [f'<ul id="{list_id}">']
    for name, i, p in zip(names, ids, prices, strict=True):
        html_lines.append(
            f'  <li class="row" data-id="{i}"><span class="label">{name}</span> '
            f'<b class="price">{p}</b></li>'
        )
    html_lines.append("</ul>")
    k = rng.randrange(n)
    target_kind = rng.choice(("span", "b", "li"))
    sel = {
        "span": f'li[data-id="{ids[k]}"] .label',
        "b": f'li[data-id="{ids[k]}"] .price',
        "li": f'li[data-id="{ids[k]}"]',
    }[target_kind]
    tag = {"span": "SPAN", "b": "B", "li": "LI"}[target_kind]
    cls = {"span": "label", "b": "price", "li": "row"}[target_kind]
    arrow = rng.random() < 0.4
    probes = [
        ("e.target.tagName", tag),
        ("e.currentTarget.id", list_id),
        ("e.currentTarget.tagName", "UL"),
        ("e.target.closest('li').dataset.id", str(ids[k])),
        ("e.target.className", cls),
        ("e.target === e.currentTarget", "false"),
        ("e.target.parentElement.tagName", "UL" if target_kind == "li" else "LI"),
        ("e.target.dataset.id", str(ids[k]) if target_kind == "li" else "undefined"),
    ]
    if not arrow:
        probes.append(("this.id", list_id))
    chosen = rng.sample(probes, 3)
    head = "(e) => {" if arrow else "function (e) {"
    js = [
        f"const list = document.getElementById('{list_id}');",
        f"list.addEventListener('click', {head}",
        *(f"  console.log({expr});" for expr, _ in chosen),
        "});",
        f"document.querySelector('{sel}').click(); // клик пользователя",
    ]
    return Variant(
        prompt=(
            "Что выведет код в консоль браузера после клика в последней строке? "
            "Перечислите значения по порядку через пробел."
        ),
        key=" ".join(out for _, out in chosen),
        code=_code("\n".join(html_lines), js),
        extra={"language": "javascript"},
        explanation=(
            "target — элемент, по которому кликнули; currentTarget (и this в обычной функции) — "
            "элемент, на котором висит обработчик."
        ),
    )


DOM_DELEGATION = ItemTemplate(
    id="frontend.dom_target_delegation",
    specialization="frontend",
    topic="dom_events",
    target_grade="intern",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_delegation,
    a=1.2,
    b=-1.1,
    title="Делегирование: target и currentTarget",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- фазы события

# слушатель: (уровень 0=document … 3=кнопка, capture, метка)
Listener = tuple[int, bool, str]


def _dispatch_order(listeners: list[Listener], target: int = 3) -> list[str]:
    """Порядок вызова по актуальной спецификации DOM (на цели capture раньше bubble)."""
    order: list[str] = []
    for level in range(target):
        order += [lbl for lv, cap, lbl in listeners if lv == level and cap]
    order += [lbl for lv, cap, lbl in listeners if lv == target and cap]
    order += [lbl for lv, cap, lbl in listeners if lv == target and not cap]
    for level in range(target - 1, -1, -1):
        order += [lbl for lv, cap, lbl in listeners if lv == level and not cap]
    return order


def _el_ref(level: int, ids: tuple[str, str, str]) -> str:
    return "document" if level == 0 else ids[level - 1]


def _html_nested(ids: tuple[str, str, str]) -> str:
    return (
        f'<div id="{ids[0]}">\n'
        f'  <div id="{ids[1]}">\n'
        f'    <button id="{ids[2]}" type="button">OK</button>\n'
        "  </div>\n"
        "</div>"
    )


def _cap_arg(capture: bool, rng: random.Random) -> str:
    if not capture:
        return rng.choice(("", "", ", false", ", { capture: false }"))
    return rng.choice((", true", ", { capture: true }"))


def _gen_phases(rng: random.Random) -> Variant:
    ids = rng.choice(_ELEMENT_IDS)
    while True:
        n = rng.randint(4, 6)
        labels = rng.sample(_WORDS, n)
        listeners: list[Listener] = []
        for lbl in labels:
            level = rng.choice((0, 1, 1, 2, 2, 3))
            listeners.append((level, rng.random() < 0.5, lbl))
        order = _dispatch_order(listeners)
        if order != labels and any(c for _, c, _ in listeners):
            break
    js = [f"const {x} = document.getElementById('{x}');" for x in ids]
    js.append("const log = (s) => console.log(s);")
    for level, cap, lbl in listeners:
        js.append(
            f"{_el_ref(level, ids)}.addEventListener('click', () => log('{lbl}')"
            f"{_cap_arg(cap, rng)});"
        )
    js.append(f"{ids[2]}.click(); // клик пользователя по кнопке")
    return make_ordering(
        rng,
        "Пользователь кликнул по кнопке (последняя строка кода). Расставьте сообщения "
        "в порядке, в котором они появятся в консоли современного Chrome.",
        order,
        code=_code(_html_nested(ids), js),
        extra={"language": "javascript"},
        explanation=(
            "Сначала погружение от document к родителю цели, затем цель (сначала capture-, потом "
            "обычные обработчики), затем всплытие обратно; на одном элементе — порядок "
            "регистрации."
        ),
    )


DOM_PHASES = ItemTemplate(
    id="frontend.dom_event_phases",
    specialization="frontend",
    topic="dom_events",
    target_grade="junior",
    format=ItemFormat.ORDERING,
    generator=_gen_phases,
    a=1.4,
    b=-0.2,
    title="Порядок обработчиков: погружение и всплытие",
    time_limit_s=180,
)

# --------------------------------------------------------------------------- stopPropagation

# слушатель: (уровень, capture, метка, действие, once)
StopListener = tuple[int, bool, str, str, bool]


def _simulate_stop(listeners: list[StopListener], clicks: int) -> list[str]:
    alive = list(listeners)
    out: list[str] = []
    invocations = [(lv, True) for lv in range(3)] + [(3, False)] + [(lv, False) for lv in (2, 1, 0)]
    for _ in range(clicks):
        stop = False
        for level, cap in invocations:
            if stop:
                break
            for li in [x for x in alive if x[0] == level and x[1] == cap]:
                if li not in alive:
                    continue
                if li[4]:
                    alive.remove(li)
                out.append(li[2])
                if li[3] == "stop":
                    stop = True
                elif li[3] == "immediate":
                    stop = True
                    break
    return out


_ACTIONS = {
    "none": "",
    "stop": " e.stopPropagation();",
    "immediate": " e.stopImmediatePropagation();",
    "prevent": " e.preventDefault();",
}


def _gen_stop(rng: random.Random) -> Variant:
    ids = rng.choice(_ELEMENT_IDS)
    while True:
        n = rng.randint(4, 6)
        labels = rng.sample(_WORDS, n)
        listeners: list[StopListener] = []
        for lbl in labels:
            level = rng.choice((0, 1, 2, 2, 3, 3))
            cap = level < 3 and rng.random() < 0.3
            action = rng.choice(("none", "none", "none", "stop", "immediate", "prevent"))
            once = rng.random() < 0.2
            listeners.append((level, cap, lbl, action, once))
        clicks = 2 if any(x[4] for x in listeners) or rng.random() < 0.25 else 1
        out = _simulate_stop(listeners, clicks)
        stops = [x for x in listeners if x[3] in ("stop", "immediate")]
        fired_all = len(out) == n * clicks
        if stops and not fired_all and out:
            break
    js = [f"const {x} = document.getElementById('{x}');" for x in ids]
    for level, cap, lbl, action, once in listeners:
        opts = []
        if cap:
            opts.append("capture: true")
        if once:
            opts.append("once: true")
        arg = f", {{ {', '.join(opts)} }}" if opts else ""
        js.append(
            f"{_el_ref(level, ids)}.addEventListener('click', (e) => {{ console.log('{lbl}');"
            f"{_ACTIONS[action]} }}{arg});"
        )
    js.append(f"{ids[2]}.click(); // первый клик")
    if clicks == 2:
        js.append(f"{ids[2]}.click(); // второй клик")
    return Variant(
        prompt=(
            "Что выведет код в консоль браузера? Перечислите значения в порядке вывода "
            "через пробел."
        ),
        key=" ".join(out),
        code=_code(_html_nested(ids), js),
        extra={"language": "javascript"},
        explanation=(
            "stopPropagation останавливает переход к следующим элементам, но остальные "
            "обработчики текущего элемента выполнятся; stopImmediatePropagation останавливает "
            "и их; preventDefault на распространение не влияет; once снимает обработчик после "
            "первого вызова."
        ),
    )


DOM_STOP = ItemTemplate(
    id="frontend.dom_stop_propagation",
    specialization="frontend",
    topic="dom_events",
    target_grade="middle",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_stop,
    a=1.4,
    b=0.5,
    title="stopPropagation, stopImmediatePropagation и once",
    time_limit_s=240,
)

TEMPLATES = (DOM_DELEGATION, DOM_PHASES, DOM_STOP)
