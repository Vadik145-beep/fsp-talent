"""Состав frontend-банка и независимая сверка ключей там, где нет реального движка.

CSS (box-sizing, grid, flex, margin, наложение) и CLS пересчитываются второй реализацией
по тексту задачи (код/формулировка разбираются заново), CORS и порядок скриптов — по правилам
спецификаций, остальное — эталонными таблицами, проверенными вручную.
"""

from __future__ import annotations

import re
from collections import Counter
from html.parser import HTMLParser

import numpy as np
import pytest

from app.testing.engine.bank.frontend import TEMPLATES
from app.testing.engine.bank.frontend.dom_events import _dispatch_order
from app.testing.engine.bank.frontend.react import _Comp, _effect_logs
from app.testing.engine.templates import ItemFormat, ItemInstance, correct_response

BY_ID = {t.id: t for t in TEMPLATES}
GRADE_B = {"intern": -1.5, "junior": -0.5, "middle": 0.5, "senior": 1.5}

# --------------------------------------------------------------------------- состав


def test_composition() -> None:
    assert len(TEMPLATES) == 30
    assert len(BY_ID) == 30
    grades = Counter(t.target_grade for t in TEMPLATES)
    assert grades == {"intern": 6, "junior": 8, "middle": 9, "senior": 7}
    topics = Counter(t.topic for t in TEMPLATES)
    assert len(topics) >= 6, topics
    assert max(topics.values()) <= 7, topics
    assert {t.format for t in TEMPLATES} == set(ItemFormat)
    for t in TEMPLATES:
        assert t.specialization == "frontend"
        assert re.fullmatch(r"frontend\.[a-z0-9_]+", t.id), t.id
        assert re.fullmatch(r"[a-z_]+", t.topic), t.topic
        assert re.search("[а-яА-Я]", t.title), t.id
        assert 90 <= t.time_limit_s <= 300, t.id
        assert 0.5 <= t.a <= 2.5, t.id
        assert abs(t.b - GRADE_B[t.target_grade]) <= 0.45, t.id


def test_examples_not_duplicated() -> None:
    assert "frontend.event_loop_order" not in BY_ID
    assert "frontend.css_specificity" not in BY_ID


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda t: t.id)
def test_many_variants_and_strict_numeric(template) -> None:  # type: ignore[no-untyped-def]
    prints = {template.generate(seed).fingerprint for seed in range(300)}
    assert len(prints) >= 100, len(prints)
    inst = template.generate(1)
    if template.format is ItemFormat.NUMERIC:
        assert inst.key.tolerance < 1
    if template.format is ItemFormat.SHORT_TEXT:
        assert template.check(inst, correct_response(inst))


# --------------------------------------------------------------------------- разбор CSS


def _rules(code: str) -> dict[str, dict[str, str]]:
    """Селектор → свойства (поддерживаются однострочные и многострочные правила)."""
    css = code.split("/* CSS */")[-1] if "/* CSS */" in code else code
    css = re.sub(r"<[^>]+>[^\n]*\n", "", css)
    out: dict[str, dict[str, str]] = {}
    for sel, body in re.findall(r"([^{}]+)\{([^}]*)\}", css):
        props = {}
        for decl in body.split(";"):
            if ":" in decl:
                k, v = decl.split(":", 1)
                props[k.strip()] = v.strip()
        out[sel.strip()] = props
    return out


def _px(v: str) -> float:
    return float(v.strip().removesuffix("px"))


def _box4(v: str) -> tuple[float, float, float, float]:
    """top, right, bottom, left из сокращённой записи."""
    p = [_px(x) for x in v.split()]
    if len(p) == 1:
        return p[0], p[0], p[0], p[0]
    if len(p) == 2:
        return p[0], p[1], p[0], p[1]
    if len(p) == 3:
        return p[0], p[1], p[2], p[1]
    return p[0], p[1], p[2], p[3]


# --------------------------------------------------------------------------- box-sizing


def test_box_sizing_independent() -> None:
    t = BY_ID["frontend.css_box_sizing"]
    for seed in range(200):
        inst = t.generate(seed)
        rules = _rules(inst.public.code or "")
        sel = next(s for s in rules if s.startswith("."))
        p = rules[sel]
        global_bb = any("*" in s and rules[s].get("box-sizing") == "border-box" for s in rules)
        sizing = p.get("box-sizing", "border-box" if global_bb else "content-box")
        _, pr, _, pl = _box4(p["padding"])
        if "border" in p:
            bl = br = _px(p["border"].split()[0])
        else:
            _, br, _, bl = _box4(p["border-width"])
        _, mr, _, ml = _box4(p["margin"])
        w = _px(p["width"])
        outer = w if sizing == "border-box" else w + pl + pr + bl + br
        content = outer - pl - pr - bl - br
        prompt = inst.public.prompt
        if "offsetWidth" in prompt:
            expected = outer
        elif "содержимого" in prompt:
            expected = content
        else:
            expected = outer + ml + mr
        assert expected == inst.key.value, (seed, inst.public.code, prompt)


# --------------------------------------------------------------------------- grid


def test_grid_independent() -> None:
    t = BY_ID["frontend.css_grid_fr"]
    for seed in range(200):
        inst = t.generate(seed)
        p = next(iter(_rules(inst.public.code or "").values()))
        width = _px(p["width"])
        cols = re.sub(
            r"repeat\((\d+),\s*([^)]+)\)",
            lambda m: " ".join([m.group(2)] * int(m.group(1))),
            p["grid-template-columns"],
        ).split()
        gap = _px(p.get("gap", p.get("column-gap", "0")))
        fixed = sum(_px(c) for c in cols if c.endswith("px"))
        fixed += sum(float(c[:-1]) * width / 100 for c in cols if c.endswith("%"))
        frs = sum(float(c[:-2]) for c in cols if c.endswith("fr"))
        free = width - fixed - gap * (len(cols) - 1)
        m = re.search(r"№(\d+)", inst.public.prompt)
        assert m
        c = cols[int(m.group(1)) - 1]
        if c.endswith("fr"):
            got = free * float(c[:-2]) / frs
        elif c.endswith("%"):
            got = float(c[:-1]) * width / 100
        else:
            got = _px(c)
        assert abs(got - inst.key.value) < 1e-9, (seed, inst.public.code)


# --------------------------------------------------------------------------- flex


def _flex_props(p: dict[str, str]) -> tuple[float, float, float | None]:
    grow, shrink, basis = 0.0, 1.0, None  # начальные значения: 0 1 auto
    if "flex" in p:
        v = p["flex"].split()
        if v == ["none"]:
            grow, shrink, basis = 0, 0, None
        elif v == ["auto"]:
            grow, shrink, basis = 1, 1, None
        elif len(v) == 1:
            grow, shrink, basis = float(v[0]), 1, 0.0  # flex: N = N 1 0%
        else:
            grow, shrink, basis = float(v[0]), float(v[1]), _px(v[2])
    if "flex-grow" in p:
        grow = float(p["flex-grow"])
    if "flex-basis" in p:
        basis = _px(p["flex-basis"])
    return grow, shrink, basis


def _resolve_flex(
    container: float, gap: float, items: list[tuple[float, float, float]]
) -> list[float]:
    """Алгоритм CSS Flexbox §9.7 с заморозкой (min-width: 0, max не задан)."""
    n = len(items)
    bases = [b for _, _, b in items]
    inner = container - gap * (n - 1)
    grow_mode = sum(bases) <= inner
    sizes = list(bases)
    frozen = [False] * n
    for i, (g, s, _b) in enumerate(items):
        if (grow_mode and g == 0) or (not grow_mode and s == 0):
            frozen[i] = True
    while not all(frozen):
        used = sum(sizes[i] if frozen[i] else bases[i] for i in range(n))
        free = inner - used
        active = [i for i in range(n) if not frozen[i]]
        if grow_mode:
            total = sum(items[i][0] for i in active)
            for i in active:
                sizes[i] = bases[i] + free * items[i][0] / total
        else:
            total = sum(items[i][1] * bases[i] for i in active)
            for i in active:
                sizes[i] = bases[i] + (free * items[i][1] * bases[i] / total if total else 0)
        violations = [i for i in active if sizes[i] < 0]
        if not violations:
            break
        for i in violations:
            sizes[i] = 0
            frozen[i] = True
    return sizes


def test_flex_independent() -> None:
    t = BY_ID["frontend.css_flex_distribution"]
    for seed in range(200):
        inst = t.generate(seed)
        rules = _rules(inst.public.code or "")
        row = rules[".row"]
        container = _px(row["width"])
        gap = _px(row.get("gap", "0"))
        order = re.findall(r'<div class="(\w+)"></div>', inst.public.code or "")
        items = []
        for name in order:
            p = rules[f".{name}"]
            g, s, b = _flex_props(p)
            items.append((g, s, b if b is not None else _px(p["width"])))
        sizes = _resolve_flex(container, gap, items)
        m = re.search(r"элемента \.(\w+)", inst.public.prompt)
        assert m
        got = sizes[order.index(m.group(1))]
        assert abs(got - inst.key.value) < 1e-6, (seed, inst.public.code, sizes)


def test_flex_reference_examples() -> None:
    # пример из спецификации: 600px, basis 100/200/100, grow 1/1/2 → свободно 200 → 150/250/200
    assert _resolve_flex(600, 0, [(1, 1, 100), (1, 1, 200), (2, 1, 100)]) == [150, 250, 200]
    # сжатие пропорционально shrink × basis: 400px, basis 300/200, shrink 1/1 → −100 → 240/160
    assert _resolve_flex(400, 0, [(0, 1, 300), (0, 1, 200)]) == [240, 160]


# --------------------------------------------------------------------------- margin collapsing


class _Tree(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.root: dict[str, object] = {"cls": "body", "children": []}
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node: dict[str, object] = {"cls": dict(attrs).get("class"), "children": []}
        children = self.stack[-1]["children"]
        assert isinstance(children, list)
        children.append(node)
        self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        self.stack.pop()


def _layout(code: str) -> dict[str, tuple[float, float]]:
    """Блочная раскладка с «стойкой» margin (как в движках): класс → (верх, низ) рамки."""
    html = code.split("<!-- HTML -->\n")[1].split("\n\n/* CSS */")[0]
    rules = _rules(code)
    tree = _Tree()
    tree.feed(html)
    boxes: dict[str, tuple[float, float]] = {}

    def prop(node: dict[str, object], name: str) -> str | None:
        return rules.get(f".{node['cls']}", {}).get(name)

    def num(node: dict[str, object], name: str) -> float:
        v = prop(node, name)
        if v is None:
            return 0.0
        return _px(v.split()[0])

    def collapse(ms: list[float]) -> float:
        return max([m for m in ms if m > 0], default=0) + min([m for m in ms if m < 0], default=0)

    def place(
        container: dict[str, object], y: float, pending: list[float], flex: bool
    ) -> tuple[float, list[float]]:
        """Разложить детей; вернуть (позицию после последнего ребёнка, висящие margin)."""
        children = container["children"]
        assert isinstance(children, list)
        for child in children:
            mt, mb = num(child, "margin-top"), num(child, "margin-bottom")
            if flex:  # margin flex-элементов не схлопываются
                top = y + mt
                bottom = top + num(child, "height")
                boxes[str(child["cls"])] = (top, bottom)
                y = bottom + mb
                continue
            sep = num(child, "padding-top") + (
                _px(prop(child, "border-top").split()[0]) if prop(child, "border-top") else 0  # type: ignore[union-attr]
            )
            new_bfc = prop(child, "overflow") == "hidden" or prop(child, "display") in (
                "flow-root",
                "flex",
            )
            is_flex = prop(child, "display") == "flex"
            kids = child["children"]
            assert isinstance(kids, list)
            height = prop(child, "height")
            if not kids and height is None:  # пустой блок: margin схлопываются насквозь
                pending = [*pending, mt, mb]
                continue
            if not kids:
                top = y + collapse([*pending, mt])
                bottom = top + num(child, "height")
                boxes[str(child["cls"])] = (top, bottom)
                y, pending = bottom, [mb]
                continue
            if sep or new_bfc:
                top = y + collapse([*pending, mt])
                end, inner_pending = place(child, top + sep, [], is_flex)
                bottom = end + (collapse(inner_pending) if inner_pending else 0)
                boxes[str(child["cls"])] = (top, bottom)
                y, pending = bottom, [mb]
            else:  # верхний margin родителя схлопывается с margin первого ребёнка
                end, inner_pending = place(child, y, [*pending, mt], False)
                boxes[str(child["cls"])] = (y, end)
                y, pending = end, [*inner_pending, mb]
        return y, pending

    place(tree.root, 0.0, [], False)
    return boxes


def test_margin_collapse_independent() -> None:
    t = BY_ID["frontend.css_margin_collapse"]
    for seed in range(300):
        inst = t.generate(seed)
        boxes = _layout(inst.public.code or "")
        got = boxes["b"][0] - boxes["a"][1]
        assert got == inst.key.value, (seed, inst.public.code, boxes)


# --------------------------------------------------------------------------- контекст наложения


def _paint_order(code: str) -> list[str]:
    """Рекурсивная отрисовка по CSS 2.1 Appendix E (все элементы — блоки с фоном)."""
    html = code.split("<!-- HTML -->\n")[1].split("\n\n/* CSS */")[0]
    rules = _rules(code)
    tree = _Tree()
    tree.feed(html)
    pre: list[dict[str, object]] = []

    def walk(n: dict[str, object]) -> None:
        pre.append(n)
        kids = n["children"]
        assert isinstance(kids, list)
        for k in kids:
            walk(k)

    walk(tree.root)
    index = {id(n): i for i, n in enumerate(pre)}

    def p(n: dict[str, object]) -> dict[str, str]:
        return rules.get(f".{n['cls']}", {})

    def positioned(n: dict[str, object]) -> bool:
        return p(n).get("position") in ("relative", "absolute")

    def z(n: dict[str, object]) -> int | None:
        v = p(n).get("z-index")
        return int(v) if v is not None and positioned(n) else None

    def is_sc(n: dict[str, object]) -> bool:
        return z(n) is not None or "opacity" in p(n) or "transform" in p(n)

    def participants(sc: dict[str, object]) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []

        def collect(n: dict[str, object]) -> None:
            kids = n["children"]
            assert isinstance(kids, list)
            for k in kids:
                out.append(k)
                if not is_sc(k):
                    collect(k)

        collect(sc)
        return out

    def paint(sc: dict[str, object], order: list[str]) -> None:
        if sc is not tree.root:
            order.append(str(sc["cls"]))
        parts = participants(sc)
        neg = sorted((n for n in parts if (z(n) or 0) < 0), key=lambda n: (z(n), index[id(n)]))
        blocks = [n for n in parts if not positioned(n) and not is_sc(n)]
        zero = [
            n
            for n in parts
            if (positioned(n) and (z(n) or 0) == 0) or (is_sc(n) and not positioned(n))
        ]
        pos = sorted((n for n in parts if (z(n) or 0) > 0), key=lambda n: (z(n), index[id(n)]))
        for group in (neg, blocks, zero, pos):  # blocks и zero уже в порядке документа
            for n in group:
                if is_sc(n):
                    paint(n, order)
                else:
                    order.append(str(n["cls"]))

    order: list[str] = []
    paint(tree.root, order)
    return order


def test_stacking_independent() -> None:
    t = BY_ID["frontend.css_stacking_context"]
    for seed in range(300):
        inst = t.generate(seed)
        order = _paint_order(inst.public.code or "")
        assert len(order) == 4, order
        assert inst.public.options[inst.key] == "." + order[-1], (seed, inst.public.code, order)


def test_stacking_reference_examples() -> None:
    code = (
        '<!-- HTML -->\n<div class="a">\n  <div class="a1"></div>\n</div>\n'
        '<div class="b">\n  <div class="b1"></div>\n</div>\n\n/* CSS */\n'
        ".a { position: relative; z-index: 1; }\n.a1 { position: absolute; z-index: 999; }\n"
        ".b { position: relative; z-index: 2; }\n.b1 { position: absolute; z-index: -1; }"
    )
    # .a1 с z-index 999 заперт в контексте .a (z 1); .b (z 2) выше, .b1 (−1) внутри .b над фоном .b
    assert _paint_order(code) == ["a", "a1", "b", "b1"]
    code2 = code.replace(".b { position: relative; z-index: 2; }", ".b { position: relative; }")
    # .b без z-index контекст не создаёт: .b1 (−1) уходит под всё, .a (1) поверх .b (auto)
    assert _paint_order(code2) == ["b1", "b", "a", "a1"]


# --------------------------------------------------------------------------- CLS


def test_cls_independent_pixel_mask() -> None:
    t = BY_ID["frontend.cls_score"]
    for seed in range(120):
        inst = t.generate(seed)
        pr = inst.public.prompt
        m = re.search(r"Окно просмотра (\d+)×(\d+)px", pr)
        assert m
        vw, vh = int(m.group(1)), int(m.group(2))
        blocks = re.findall(
            r"x=(\d+), y=(\d+), ширина (\d+)px, высота (\d+)px — смещается вниз на (\d+)px"
            r"(?: и (вправо|влево) на (\d+)px)?",
            pr,
        )
        assert blocks
        if "после того, как пользователь" in pr:
            assert inst.key.value == 0
            continue
        mask = np.zeros((vh, vw), dtype=bool)
        dist = 0
        for x, y, w, h, dy, side, dx in blocks:
            x, y, w, h, dy = int(x), int(y), int(w), int(h), int(dy)
            ddx = (int(dx) if side == "вправо" else -int(dx)) if side else 0
            for xx, yy in ((x, y), (x + ddx, y + dy)):
                mask[max(yy, 0) : max(min(yy + h, vh), 0), max(xx, 0) : max(min(xx + w, vw), 0)] = (
                    True
                )
            dist = max(dist, dy, abs(ddx))
        score = mask.mean() * dist / max(vw, vh)
        assert abs(score - inst.key.value) < 1e-5, (seed, pr, score, inst.key)


def test_cls_reference_example() -> None:
    # пример web.dev: элемент на 50% окна сдвигается на 25% высоты → 0.75 × 0.25 = 0.1875
    from app.testing.engine.bank.frontend.browser_net import ClsCase, cls_score

    assert cls_score(ClsCase((400, 800), ((0, 0, 400, 400, 0, 200),), False)) == 0.1875


# --------------------------------------------------------------------------- CORS


def test_cors_rules_from_text() -> None:
    t = BY_ID["frontend.cors_preflight"]
    safelisted_ct = {"application/x-www-form-urlencoded", "multipart/form-data", "text/plain"}
    for seed in range(200):
        inst = t.generate(seed)
        expected = set()
        for i, opt in enumerate(inst.public.options):
            if opt.startswith("fetch('/"):
                continue  # тот же origin
            m = re.search(r"method: '(\w+)'", opt)
            method = m.group(1) if m else "GET"
            headers = dict(re.findall(r"'([A-Za-z-]+)': ('[^']*'|[^,}]+)", opt))
            bad = method not in ("GET", "HEAD", "POST")
            for name, value in headers.items():
                low = name.lower()
                if low == "content-type":
                    bad |= value.strip("'") not in safelisted_ct
                elif low not in ("accept", "accept-language", "content-language"):
                    bad = True
            if bad:
                expected.add(i)
        assert frozenset(expected) == inst.key, (seed, inst.public.options)


# --------------------------------------------------------------------------- порядок скриптов


def test_script_order_by_html_spec() -> None:
    t = BY_ID["frontend.script_loading_order"]
    for seed in range(200):
        inst = t.generate(seed)
        tags = re.findall(r"<script([^>]*)>(.*?)</script>", inst.public.code or "", re.S)
        parse_time, after_parse, slow = [], [], []
        for attrs, body in tags[1:]:
            src = re.search(r'src="(\w+)\.js"', attrs)
            m = re.search(r"console\.log\('(\w+)'\)", body)
            name = src.group(1) if src else (m.group(1) if m else "")
            if 'type="module"' in attrs:
                after_parse.append(name)  # модули всегда отложены
            elif not src:
                parse_time.append(name)  # у встроенных скриптов defer/async не действуют
            elif "async" in attrs:
                slow.append(name)
            elif "defer" in attrs:
                after_parse.append(name)
            else:
                parse_time.append(name)
        expected = [*parse_time, *after_parse, "DOMContentLoaded", *slow, "load"]
        assert [inst.public.options[k] for k in inst.key] == expected, inst.public.code


# --------------------------------------------------------------------------- модели DOM и React


def test_dispatch_order_reference() -> None:
    # уровни: 0 document, 1 внешний div, 2 внутренний div, 3 кнопка-цель
    listeners = [(3, False, "t-bubble"), (1, True, "o-cap"), (3, True, "t-cap"), (0, False, "d")]
    assert _dispatch_order(listeners) == ["o-cap", "t-cap", "t-bubble", "d"]


def test_effect_order_reference() -> None:
    app = _Comp("App", True, "count", "count")
    child = _Comp("List", True, "count", "count")
    assert _effect_logs([app, child], "mount") == [
        "render App",
        "render List",
        "layout List",
        "layout App",
        "effect List",
        "effect App",
    ]
    assert _effect_logs([app, child], "update")[2:] == [
        "cleanup layout List",
        "cleanup layout App",
        "layout List",
        "layout App",
        "cleanup effect List",
        "cleanup effect App",
        "effect List",
        "effect App",
    ]


# --------------------------------------------------------------------------- эталонные таблицы

_HTTP_EXPECTED = {
    "чтобы сервер мог ответить «не изменилось»": "if-none-match",
    "ETag сервер не отдаёт": "if-modified-since",
    "Какой код статуса": "304",
    "нельзя сохранять ни в каком": "no-store",
    "перед каждым использованием": "no-cache",
    "не в общих кэшах": "private",
    "а CDN": "s-maxage",
    "даже при обновлении страницы": "immutable",
    "Accept-Encoding. Какой": "vary",
}


def test_http_cache_reference_table() -> None:
    t = BY_ID["frontend.http_cache_headers"]
    seen = set()
    for seed in range(300):
        inst = t.generate(seed)
        for fragment, answer in _HTTP_EXPECTED.items():
            if fragment in inst.public.prompt:
                assert inst.key[0].lower() == answer, inst.public.prompt
                seen.add(fragment)
                break
        else:
            m = re.search(r"ровно (\d+) ч", inst.public.prompt)
            assert m and inst.key[0] == str(int(m.group(1)) * 3600)
            assert t.check(inst, f"max-age={inst.key[0]}")
        assert not t.check(inst, "max-age")
    assert seen == set(_HTTP_EXPECTED)


_SAMESITE_EXPECTED = {  # фрагмент описания → (Strict, Lax, None)
    "кликает обычную ссылку": (False, True, True),
    'method="POST"': (False, False, True),
    "<img": (False, False, True),
    "<iframe": (False, False, True),
    "location.href": (False, True, True),
    "в адресной строке": (True, True, True),
    "(без https)": (False, False, False),
}


def test_samesite_reference_table() -> None:
    t = BY_ID["frontend.cookie_samesite"]
    modes = ("Strict", "Lax", "None")
    for seed in range(200):
        inst = t.generate(seed)
        m = re.search(r"SameSite=(\w+)", inst.public.prompt)
        assert m
        mode = modes.index(m.group(1))
        for i, opt in enumerate(inst.public.options):
            if "fetch(" in opt:
                same_site = opt.startswith("Скрипт на https://pay.")
                expected = same_site or modes[mode] == "None"
            else:
                frag = next(f for f in _SAMESITE_EXPECTED if f in opt)
                expected = _SAMESITE_EXPECTED[frag][mode]
            assert (i in inst.key) == expected, (seed, mode, opt)


_FOCUSABLE = (
    "<button>",
    "<a href=",
    '<input type="text"',
    "<select",
    "<textarea",
    'tabindex="0"',
    "<summary>",
)


def test_focusable_reference_table() -> None:
    t = BY_ID["frontend.a11y_focusable"]
    for seed in range(200):
        inst = t.generate(seed)
        for i, opt in enumerate(inst.public.options):
            assert (i in inst.key) == any(f in opt for f in _FOCUSABLE), opt


_UNSAFE = re.compile(
    r"innerHTML = '<b>' \+|insertAdjacentHTML|document\.write|setTimeout\('|outerHTML|\.href = "
)


def test_xss_only_bug_line_is_sink() -> None:
    t = BY_ID["frontend.xss_sink"]
    lines_seen = Counter()
    for seed in range(200):
        inst: ItemInstance = t.generate(seed)
        lines = (inst.public.code or "").split("\n")
        hits = [i + 1 for i, line in enumerate(lines) if _UNSAFE.search(line)]
        assert hits == [inst.key], (seed, inst.public.code)
        lines_seen[inst.key] += 1
    assert len(lines_seen) >= 5


def test_hook_choice_accepts_variants() -> None:
    t = BY_ID["frontend.react_hook_choice"]
    for seed in range(100):
        inst = t.generate(seed)
        hook = inst.key[0]
        assert t.check(inst, hook.lower())
        assert t.check(inst, f"React.{hook}")
        assert not t.check(inst, "useState") or hook == "useState"
