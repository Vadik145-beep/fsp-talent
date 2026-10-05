"""Frontend / CSS: box-sizing, grid fr, распределение flex, схлопывание margin, контекст наложения.

Каждый генератор строит код (HTML + CSS) и считает ответ своей моделью. Тест разбирает
сгенерированный CSS заново и считает ответ второй, независимой реализацией.
"""

from __future__ import annotations

import random
from fractions import Fraction

from ...templates import ItemFormat, ItemTemplate, NumericKey, Variant, make_single_choice

_CLASS_NAMES = ("card", "panel", "box", "tile", "banner", "modal", "item", "cell", "block")

# --------------------------------------------------------------------------- box-sizing


def _sides_css(prop: str, top: int, right: int, bottom: int, left: int, rng: random.Random) -> str:
    """Записать четыре стороны одним из способов CSS (полная форма, сокращения)."""
    if top == right == bottom == left:
        return f"{prop}: {top}px;"
    if top == bottom and left == right:
        return f"{prop}: {top}px {right}px;"
    if left == right and rng.random() < 0.5:
        return f"{prop}: {top}px {right}px {bottom}px;"
    return f"{prop}: {top}px {right}px {bottom}px {left}px;"


def _gen_box_sizing(rng: random.Random) -> Variant:
    cls = rng.choice(_CLASS_NAMES)
    width = rng.choice(range(120, 401, 10))
    pv = rng.choice((0, 4, 8, 10, 12, 16))
    ph = rng.choice((5, 8, 10, 12, 15, 16, 20, 24))
    pl, pr = (ph, ph) if rng.random() < 0.6 else (ph, rng.choice((0, 4, 6, 30)))
    bw = rng.choice((1, 2, 3, 4, 5))
    margin_h = rng.choice((0, 8, 10, 16, 20, 24))
    global_bb = rng.random() < 0.35
    own = rng.choice(("border-box", "content-box", None))
    if own is None and not global_bb:
        own = "content-box" if rng.random() < 0.3 else None
    sizing = own or ("border-box" if global_bb else "content-box")
    ask = rng.choice(("border", "border", "content", "margin"))
    lines = []
    if global_bb:
        lines += ["*, *::before, *::after {", "  box-sizing: border-box;", "}", ""]
    lines.append(f".{cls} {{")
    if own:
        lines.append(f"  box-sizing: {own};")
    lines.append(f"  width: {width}px;")
    lines.append("  " + _sides_css("padding", pv, pr, pv, pl, rng))
    if rng.random() < 0.5:
        lines.append(f"  border: {bw}px solid #333;")
    else:
        lines.append(f"  border-width: {rng.choice((1, 2, 6))}px {bw}px;")
        lines.append("  border-style: solid;")
    lines.append(f"  margin: {rng.choice((0, 10, 16))}px {margin_h}px;")
    lines.append("}")
    if sizing == "border-box":
        border_w = width
        content_w = width - pl - pr - 2 * bw
    else:
        content_w = width
        border_w = width + pl + pr + 2 * bw
    answer = {"border": border_w, "content": content_w, "margin": border_w + 2 * margin_h}[ask]
    question = {
        "border": "ширину рамки элемента (border-box, значение offsetWidth)",
        "content": "ширину области содержимого (content-box) элемента",
        "margin": "сколько места по горизонтали займёт элемент вместе с внешними отступами",
    }[ask]
    return Variant(
        prompt=(
            f'Элемент <div class="{cls}"> — блочный, родитель достаточно широкий, других стилей '
            f"нет. Укажите {question}, в пикселях."
        ),
        key=NumericKey(answer),
        code="/* CSS */\n" + "\n".join(lines),
        extra={"language": "css", "unit": "px"},
        explanation=(
            f"box-sizing: {sizing}; width задаёт ширину "
            + ("рамки" if sizing == "border-box" else "содержимого")
            + f". Ответ {answer}px."
        ),
    )


CSS_BOX_SIZING = ItemTemplate(
    id="frontend.css_box_sizing",
    specialization="frontend",
    topic="css",
    target_grade="intern",
    format=ItemFormat.NUMERIC,
    generator=_gen_box_sizing,
    a=1.3,
    b=-1.4,
    title="Ширина блока и box-sizing",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- grid fr

Track = tuple[str, int]  # ("px" | "fr" | "pct", значение)


def _track_css(tracks: list[Track]) -> str:
    parts: list[str] = []
    i = 0
    while i < len(tracks):
        kind, v = tracks[i]
        j = i
        while j < len(tracks) and tracks[j] == tracks[i]:
            j += 1
        unit = {"px": "px", "fr": "fr", "pct": "%"}[kind]
        if j - i >= 2:
            parts.append(f"repeat({j - i}, {v}{unit})")
        else:
            parts.append(f"{v}{unit}")
        i = j
    return " ".join(parts)


def _grid_widths(width: int, tracks: list[Track], gap: int) -> list[Fraction]:
    fixed = sum((Fraction(v) for k, v in tracks if k == "px"), Fraction(0))
    fixed += sum((Fraction(v * width, 100) for k, v in tracks if k == "pct"), Fraction(0))
    free = Fraction(width) - fixed - gap * (len(tracks) - 1)
    fr_total = sum(v for k, v in tracks if k == "fr")
    out: list[Fraction] = []
    for k, v in tracks:
        if k == "px":
            out.append(Fraction(v))
        elif k == "pct":
            out.append(Fraction(v * width, 100))
        else:
            out.append(free * v / fr_total if fr_total else Fraction(0))
    return out


def _gen_grid(rng: random.Random) -> Variant:
    cls = rng.choice(("grid", "layout", "gallery", "table", "board"))
    while True:
        n = rng.randint(3, 4)
        tracks: list[Track] = []
        for _ in range(n):
            r = rng.random()
            if r < 0.5:
                tracks.append(("fr", rng.choice((1, 1, 2, 3))))
            elif r < 0.85:
                tracks.append(("px", rng.choice((80, 100, 120, 150, 160, 200, 240))))
            else:
                tracks.append(("pct", rng.choice((10, 20, 25))))
        if not any(k == "fr" for k, _ in tracks):
            continue
        gap = rng.choice((0, 8, 10, 16, 20, 24, 30))
        unit = rng.choice(range(40, 201, 5))
        fixed_px = sum(v for k, v in tracks if k == "px")
        pct = sum(v for k, v in tracks if k == "pct")
        fr_total = sum(v for k, v in tracks if k == "fr")
        width_f = Fraction(fixed_px + gap * (n - 1) + unit * fr_total) / (1 - Fraction(pct, 100))
        if width_f.denominator != 1 or not 300 <= width_f <= 1600:
            continue
        width = int(width_f)
        widths = _grid_widths(width, tracks, gap)
        candidates = [i for i, (k, _) in enumerate(tracks) if k != "px"]
        idx = rng.choice(candidates)
        if widths[idx].denominator == 1:
            break
    gap_css = rng.choice(("gap", "column-gap"))
    code = (
        f'<div class="{cls}">…ячейки…</div>\n\n'
        f".{cls} {{\n"
        "  display: grid;\n"
        f"  width: {width}px;\n"
        f"  grid-template-columns: {_track_css(tracks)};\n"
        f"  {gap_css}: {gap}px;\n"
        "}"
    )
    return Variant(
        prompt=(
            f"Какой будет ширина колонки №{idx + 1} (считая слева) в пикселях? У контейнера нет "
            "padding и border, ячейки пустые (min-content равен 0)."
        ),
        key=NumericKey(int(widths[idx])),
        code=code,
        extra={"language": "css", "unit": "px"},
        explanation=(
            "Из ширины вычитаются фиксированные колонки, проценты и промежутки, остаток делится "
            f"пропорционально fr. Ответ {int(widths[idx])}px."
        ),
    )


CSS_GRID_FR = ItemTemplate(
    id="frontend.css_grid_fr",
    specialization="frontend",
    topic="css",
    target_grade="junior",
    format=ItemFormat.NUMERIC,
    generator=_gen_grid,
    a=1.3,
    b=-0.6,
    title="Ширина колонки CSS Grid с fr и gap",
    time_limit_s=180,
)

# --------------------------------------------------------------------------- flex

# (css-строки свойств, grow, shrink, basis | None=auto, width)
FlexItem = tuple[list[str], int, int, int | None, int]


def _flex_item(rng: random.Random) -> FlexItem:
    form = rng.choice(("full", "full", "one", "auto", "none", "grow_basis", "width"))
    width = rng.choice((60, 80, 100, 120, 150, 200, 240))
    basis = rng.choice((0, 50, 80, 100, 120, 150, 200, 250, 300))
    g = rng.choice((0, 1, 1, 2, 3))
    s = rng.choice((0, 1, 1, 2, 3))
    if form == "full":
        return [f"flex: {g} {s} {basis}px;"], g, s, basis, width
    if form == "one":
        g = rng.choice((1, 2, 3))
        return [f"flex: {g};"], g, 1, 0, width
    if form == "auto":
        return [f"width: {width}px;", "flex: auto;"], 1, 1, None, width
    if form == "none":
        return [f"width: {width}px;", "flex: none;"], 0, 0, None, width
    if form == "grow_basis":
        g = rng.choice((1, 2))
        return [f"flex-grow: {g};", f"flex-basis: {basis}px;"], g, 1, basis, width
    return [f"width: {width}px;"], 0, 1, None, width


def _flex_widths(container: int, gap: int, items: list[FlexItem]) -> list[Fraction] | None:
    bases = [Fraction(b if b is not None else w) for _, _, _, b, w in items]
    free = Fraction(container) - sum(bases, Fraction(0)) - gap * (len(items) - 1)
    if free >= 0:
        total = sum(g for _, g, _, _, _ in items)
        if total == 0:
            return bases
        return [
            b + free * Fraction(g, total) for b, (_, g, _, _, _) in zip(bases, items, strict=True)
        ]
    weights = [s * b for b, (_, _, s, _, _) in zip(bases, items, strict=True)]
    total_w = sum(weights, Fraction(0))
    if total_w == 0:
        return bases
    out = [b + free * w / total_w for b, w in zip(bases, weights, strict=True)]
    if any(x <= 0 for x in out):
        return None  # потребовалась бы заморозка на min-width — такие варианты не берём
    return out


def _gen_flex(rng: random.Random) -> Variant:
    while True:
        n = rng.randint(3, 4)
        items = [_flex_item(rng) for _ in range(n)]
        container = rng.choice(range(400, 1001, 20))
        gap = rng.choice((0, 0, 10, 16, 20))
        widths = _flex_widths(container, gap, items)
        if widths is None:
            continue
        idx = rng.randrange(n)
        w = widths[idx]
        bases = [b if b is not None else wd for _, _, _, b, wd in items]
        if w.denominator != 1 or (w == bases[idx] and rng.random() < 0.75):
            continue
        break
    names = rng.sample(("a", "b", "c", "d", "e", "f", "g", "h"), n)
    css = [
        ".row {",
        "  display: flex;",
        f"  width: {container}px;",
        *([f"  gap: {gap}px;"] if gap else []),
        "}",
    ]
    for name, (props, *_rest) in zip(names, items, strict=True):
        css.append(f".{name} {{ {' '.join(props)} }}")
    html = (
        '<div class="row">\n' + "\n".join(f'  <div class="{x}"></div>' for x in names) + "\n</div>"
    )
    return Variant(
        prompt=(
            f"Какой будет ширина элемента .{names[idx]} в пикселях? У элементов нет содержимого, "
            "padding, border и margin, min-width: 0; у контейнера нет padding и border."
        ),
        key=NumericKey(int(w)),
        code=f"<!-- HTML -->\n{html}\n\n/* CSS */\n" + "\n".join(css),
        extra={"language": "css", "unit": "px"},
        explanation=(
            "Свободное место = ширина − сумма flex-basis − gap. Положительное делится по "
            "flex-grow, отрицательное — по flex-shrink × flex-basis. flex: N = N 1 0%, "
            f"flex: auto = 1 1 auto, flex: none = 0 0 auto. Ответ {int(w)}px."
        ),
    )


CSS_FLEX = ItemTemplate(
    id="frontend.css_flex_distribution",
    specialization="frontend",
    topic="css",
    target_grade="middle",
    format=ItemFormat.NUMERIC,
    generator=_gen_flex,
    a=1.4,
    b=0.8,
    title="Распределение места во flex: grow, shrink, basis",
    time_limit_s=270,
)

# --------------------------------------------------------------------------- margin collapsing

_MARGIN_SCENARIOS = (
    "siblings",
    "wrap_plain",
    "wrap_padding",
    "wrap_border",
    "wrap_overflow",
    "wrap_flowroot",
    "empty_between",
    "flex_parent",
)


def _collapse(margins: list[int]) -> int:
    pos = max([m for m in margins if m > 0], default=0)
    neg = min([m for m in margins if m < 0], default=0)
    return pos + neg


def _margin(rng: random.Random, allow_neg: bool) -> int:
    if allow_neg and rng.random() < 0.35:
        return -rng.choice((5, 10, 15, 20))
    return rng.choice((0, 10, 12, 16, 20, 24, 30, 40, 50))


def _gen_margin(rng: random.Random) -> Variant:
    while True:
        sc = rng.choice(_MARGIN_SCENARIOS)
        neg = rng.random() < 0.4
        x, y, z = _margin(rng, neg), _margin(rng, neg), _margin(rng, neg)
        p = rng.choice((1, 2, 4, 5, 8, 10))
        ha, hb = rng.choice((40, 50, 60, 80)), rng.choice((40, 50, 60, 80))
        a_css = f".a {{ height: {ha}px; margin-bottom: {x}px; }}"
        b_css = f".b {{ height: {hb}px; margin-top: {y}px; }}"
        b_html = '<div class="b"></div>'
        if sc == "siblings":
            html = ['<div class="a"></div>', b_html]
            css = [a_css, b_css]
            ans = _collapse([x, y])
        elif sc == "empty_between":
            e1, e2 = _margin(rng, neg), _margin(rng, neg)
            html = ['<div class="a"></div>', '<div class="gap"></div>', b_html]
            css = [a_css, f".gap {{ margin-top: {e1}px; margin-bottom: {e2}px; }}", b_css]
            ans = _collapse([x, e1, e2, y])
        elif sc == "flex_parent":
            html = [
                '<div class="list">',
                '  <div class="a"></div>',
                '  <div class="b"></div>',
                "</div>",
            ]
            css = [".list { display: flex; flex-direction: column; }", a_css, b_css]
            ans = x + y
        else:
            extra = {
                "wrap_plain": "",
                "wrap_padding": f" padding-top: {p}px;",
                "wrap_border": f" border-top: {p}px solid #ccc;",
                "wrap_overflow": " overflow: hidden;",
                "wrap_flowroot": " display: flow-root;",
            }[sc]
            html = ['<div class="a"></div>', '<div class="wrap">', f"  {b_html}", "</div>"]
            css = [a_css, f".wrap {{ margin-top: {z}px;{extra} }}", b_css]
            if sc == "wrap_plain":
                ans = _collapse([x, z, y])
            elif sc in ("wrap_padding", "wrap_border"):
                ans = _collapse([x, z]) + p + y
            else:
                ans = _collapse([x, z]) + y
        if ans >= 0 or sc == "flex_parent":
            break
    code = "<!-- HTML -->\n" + "\n".join(html) + "\n\n/* CSS */\n" + "\n".join(css)
    return Variant(
        prompt=(
            "Блоки идут в обычном потоке внутри <body> (у body свой padding, он не мешает). "
            "Какое расстояние в пикселях от нижнего края рамки .a до верхнего края рамки .b? "
            "Если .b заходит на .a, ответ отрицательный. Других стилей нет."
        ),
        key=NumericKey(ans),
        code=code,
        extra={"language": "css", "unit": "px"},
        explanation=(
            "Соседние вертикальные margin схлопываются: максимум положительных плюс минимум "
            "отрицательных. Padding, border, overflow: hidden, flow-root и flex-контейнер "
            f"мешают схлопыванию с потомками. Ответ {ans}px."
        ),
    )


CSS_MARGIN_COLLAPSE = ItemTemplate(
    id="frontend.css_margin_collapse",
    specialization="frontend",
    topic="css",
    target_grade="middle",
    format=ItemFormat.NUMERIC,
    generator=_gen_margin,
    a=1.3,
    b=0.3,
    title="Схлопывание вертикальных margin",
    time_limit_s=210,
)

# --------------------------------------------------------------------------- контекст наложения

_PARENTS = ("card", "modal", "header", "menu", "sidebar", "panel", "toolbar", "dialog")
_CHILDREN = ("badge", "icon", "popup", "dot", "hint", "label", "avatar", "tag")

# Стиль элемента: (css-свойства, positioned, z | None, образует ли контекст наложения)
Style = tuple[str, bool, int | None, bool]


def _parent_style(rng: random.Random) -> Style:
    r = rng.random()
    if r < 0.4:
        z = rng.choice((0, 1, 2, 3, 5, 10))
        return f"position: relative; z-index: {z};", True, z, True
    if r < 0.6:
        return "position: relative;", True, None, False
    if r < 0.75:
        return "position: relative; opacity: 0.9;", True, None, True
    if r < 0.88:
        z = rng.choice((5, 10, 50))
        return f"z-index: {z};", False, None, False  # z-index без position не работает
    return "transform: translateX(0);", False, None, True


def _child_style(rng: random.Random) -> Style:
    if rng.random() < 0.15:
        return "position: absolute;", True, None, False
    z = rng.choice((-1, 0, 1, 2, 5, 10, 50, 100, 999))
    return f"position: absolute; z-index: {z};", True, z, True


def _participant_key(style: Style, preorder: int) -> tuple[int, int, int]:
    _, positioned, z, sc = style
    if positioned and z is not None:
        bucket = 0 if z < 0 else (2 if z == 0 else 3)
        return bucket, z, preorder
    if sc or positioned:
        return 2, 0, preorder
    return 1, 0, preorder


def _stack_top(styles: list[Style]) -> int:
    """Индекс верхнего элемента. Порядок: P1(0) > C1(1), P2(2) > C2(3)."""
    parent = {1: 0, 3: 2}
    paths: list[list[tuple[int, int, int]]] = []
    for i in range(4):
        path = [_participant_key(styles[i], i)]
        p = parent.get(i)
        if p is not None and styles[p][3]:
            path = [_participant_key(styles[p], p), *path]
        paths.append(path)
    return max(range(4), key=lambda i: paths[i])


def _gen_stacking(rng: random.Random) -> Variant:
    while True:
        p1, p2 = rng.sample(_PARENTS, 2)
        c1, c2 = rng.sample(_CHILDREN, 2)
        names = [p1, c1, p2, c2]
        styles = [_parent_style(rng), _child_style(rng), _parent_style(rng), _child_style(rng)]
        top = _stack_top(styles)
        zs = [s[2] if s[1] and s[2] is not None else -(10**6) for s in styles]
        naive = max(range(4), key=lambda i: (zs[i], i))
        if top != naive or rng.random() < 0.3:
            break
    html = (
        f'<div class="{p1}">\n  <div class="{c1}"></div>\n</div>\n'
        f'<div class="{p2}">\n  <div class="{c2}"></div>\n</div>'
    )
    css = "\n".join(f".{n} {{ {s[0]} }}" for n, s in zip(names, styles, strict=True))
    return make_single_choice(
        rng,
        "Все четыре элемента имеют фон и перекрываются в одной точке (размеры и координаты "
        "опущены). Какой элемент будет виден в этой точке — то есть нарисован поверх остальных?",
        f".{names[top]}",
        [f".{n}" for i, n in enumerate(names) if i != top],
        code=f"<!-- HTML -->\n{html}\n\n/* CSS */\n{css}",
        extra={"language": "css"},
        explanation=(
            "z-index сравнивается только внутри одного контекста наложения; контекст создают "
            "position + z-index, opacity < 1, transform; z-index без position игнорируется."
        ),
    )


CSS_STACKING = ItemTemplate(
    id="frontend.css_stacking_context",
    specialization="frontend",
    topic="css",
    target_grade="senior",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_stacking,
    a=1.5,
    b=1.5,
    title="z-index и контекст наложения",
    time_limit_s=240,
)

TEMPLATES = (CSS_BOX_SIZING, CSS_GRID_FR, CSS_FLEX, CSS_MARGIN_COLLAPSE, CSS_STACKING)
