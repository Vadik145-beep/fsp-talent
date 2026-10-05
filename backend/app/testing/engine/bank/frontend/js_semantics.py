"""Frontend / JavaScript: приведение типов, методы массивов, ==, замыкания в циклах,
копирование объектов, this. Ответы считает модель на Python, тест сверяет их с node."""

from __future__ import annotations

import math
import random

from ...templates import ItemFormat, ItemTemplate, Variant, make_multi_choice

_NODE_PROMPT = (
    "Что выведет этот код в Node.js? Перечислите выведенные значения в порядке вывода через пробел."
)


def _js_num(x: float) -> str:
    """Число так, как его печатает console.log."""
    if isinstance(x, float) and math.isnan(x):
        return "NaN"
    if float(x).is_integer():
        return str(int(x))
    return repr(float(x))


# --------------------------------------------------------------------------- приведение типов


def _coercion_pool(rng: random.Random) -> list[tuple[str, str]]:
    a, b, c = rng.sample(range(2, 10), 3)
    return [
        (f"'{a}' + {b}", f"{a}{b}"),
        (f"{a} + '{b}'", f"{a}{b}"),
        (f"'{a}' - {b}", _js_num(a - b)),
        (f"'{a}' * '{b}'", _js_num(a * b)),
        (f"{a} + +'{b}'", _js_num(a + b)),
        (f"{a} + {b} + '{c}'", f"{a + b}{c}"),
        (f"'{c}' + {a} + {b}", f"{c}{a}{b}"),
        (f"true + {a}", _js_num(a + 1)),
        (f"[{a}] + [{b}]", f"{a}{b}"),
        (f"null + {a}", _js_num(a)),
        (f"undefined + {a}", "NaN"),
        (f"'{a}' - 'x'", "NaN"),
        (f"'{a}' > '{b}{c}'", "true" if str(a) > f"{b}{c}" else "false"),
        (f"{a} > '{b}{c}'", "true" if a > int(f"{b}{c}") else "false"),
        (f"'{a * b}' / '{b}'", _js_num(a)),
        (f"+'' + {a}", _js_num(a)),
    ]


def _gen_coercion(rng: random.Random) -> Variant:
    pool = _coercion_pool(rng)
    chosen = rng.sample(pool, rng.randint(4, 5))
    code = "\n".join(f"console.log({expr});" for expr, _ in chosen)
    return Variant(
        prompt=_NODE_PROMPT,
        key=" ".join(out for _, out in chosen),
        code=code,
        extra={"language": "javascript"},
        explanation="+ со строкой склеивает, -, *, / приводят к числу; null → 0, undefined → NaN.",
    )


JS_COERCION = ItemTemplate(
    id="frontend.js_coercion",
    specialization="frontend",
    topic="javascript",
    target_grade="intern",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_coercion,
    a=1.1,
    b=-1.6,
    title="Приведение типов в выражениях",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- методы массивов

_ARR_NAMES = ("nums", "values", "prices", "scores", "items", "data")


def _gen_array_methods(rng: random.Random) -> Variant:
    name = rng.choice(_ARR_NAMES)
    arr = [rng.randint(1, 30) for _ in range(rng.randint(5, 6))]
    if rng.random() < 0.4:
        # для сортировки по умолчанию нужны числа разной длины
        arr[rng.randrange(len(arr))] = rng.choice((100, 5, 9, 25, 40))
    state = list(arr)
    lines = [f"const {name} = [{', '.join(map(str, arr))}];"]
    outs: list[str] = []
    ops = rng.sample(
        ["filter_map", "reduce", "max", "index", "slice", "find", "some_every", "sort", "splice"],
        rng.randint(3, 4),
    )
    for op in ops:
        if op == "filter_map":
            t, k = rng.randint(5, 20), rng.randint(2, 4)
            res = [x * k for x in state if x > t]
            lines.append(f"console.log({name}.filter(x => x > {t}).map(x => x * {k}).length);")
            outs.append(str(len(res)))
        elif op == "reduce":
            init = rng.choice((0, 10, 100))
            lines.append(f"console.log({name}.reduce((acc, x) => acc + x, {init}));")
            outs.append(str(init + sum(state)))
        elif op == "max":
            lines.append(f"console.log({name}.reduce((m, x) => (x > m ? x : m)));")
            outs.append(str(max(state)))
        elif op == "index":
            v = rng.choice([*state, rng.randint(31, 60)])
            lines.append(f"console.log({name}.indexOf({v}));")
            outs.append(str(state.index(v) if v in state else -1))
        elif op == "slice":
            i = rng.randint(0, 2)
            j = rng.randint(i + 1, len(state))
            lines.append(f"console.log({name}.slice({i}, {j}).join('-'));")
            outs.append("-".join(map(str, state[i:j])))
        elif op == "find":
            t = rng.randint(5, 35)
            found = next((x for x in state if x > t), None)
            lines.append(f"console.log({name}.find(x => x > {t}));")
            outs.append("undefined" if found is None else str(found))
        elif op == "some_every":
            t = rng.randint(3, 25)
            lines.append(f"console.log({name}.some(x => x > {t}), {name}.every(x => x > {t}));")
            outs.append(str(any(x > t for x in state)).lower())
            outs.append(str(all(x > t for x in state)).lower())
        elif op == "sort":
            lines.append(f"console.log([...{name}].sort().join('-'));")
            outs.append("-".join(sorted(map(str, state))))
        else:  # splice меняет исходный массив
            i = rng.randint(0, 2)
            n = rng.randint(1, 2)
            removed = state[i : i + n]
            del state[i : i + n]
            lines.append(f"console.log({name}.splice({i}, {n}).join('-'), {name}.length);")
            outs.append("-".join(map(str, removed)))
            outs.append(str(len(state)))
    return Variant(
        prompt=_NODE_PROMPT,
        key=" ".join(outs),
        code="\n".join(lines),
        extra={"language": "javascript"},
        explanation=(
            "sort() без компаратора сравнивает строки; splice меняет исходный массив; "
            "find без совпадения даёт undefined."
        ),
    )


JS_ARRAY_METHODS = ItemTemplate(
    id="frontend.js_array_methods",
    specialization="frontend",
    topic="javascript",
    target_grade="intern",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_array_methods,
    a=1.2,
    b=-1.2,
    title="Методы массивов: map, filter, reduce, sort, splice",
    time_limit_s=180,
)

# --------------------------------------------------------------------------- нестрогое равенство


def _equality_pool(rng: random.Random) -> list[tuple[str, bool]]:
    n = rng.randint(1, 99)
    m = rng.randint(2, 9)
    return [
        (f"'{n}' == {n}", True),
        (f"'{n}' === {n}", False),
        ("0 == ''", True),
        ("0 == '0'", True),
        ("'' == '0'", False),
        ("null == undefined", True),
        ("null === undefined", False),
        ("null == 0", False),
        ("null >= 0", True),
        ("undefined == 0", False),
        ("NaN == NaN", False),
        ("[] == false", True),
        (f"'{n}' == '{n}.0'", False),
        (f"{n} == '{n}.0'", True),
        ("true == '1'", True),
        (f"true == '{m}'", False),
        (f"[{n}] == {n}", True),
        (f"[1, {m}] == '1,{m}'", True),
        (f"{n} == '{n}px'", False),
        (f"' {n} ' == {n}", True),
        ("false == 'false'", False),
        ("0 == null", False),
    ]


def _gen_loose_equality(rng: random.Random) -> Variant:
    pool = _equality_pool(rng)
    while True:
        chosen = rng.sample(pool, 6)
        n_true = sum(v for _, v in chosen)
        if 2 <= n_true <= 4:
            break
    return make_multi_choice(
        rng,
        "Какие из выражений JavaScript вернут true? Отметьте все подходящие.",
        [e for e, v in chosen if v],
        [e for e, v in chosen if not v],
        extra={"language": "javascript"},
        explanation=(
            "== приводит строку к числу; null равен только undefined (но null >= 0 — true); "
            "NaN не равен ничему; массив сначала превращается в строку."
        ),
    )


JS_LOOSE_EQUALITY = ItemTemplate(
    id="frontend.js_loose_equality",
    specialization="frontend",
    topic="javascript",
    target_grade="junior",
    format=ItemFormat.MULTI_CHOICE,
    generator=_gen_loose_equality,
    a=1.2,
    b=-0.5,
    title="Нестрогое сравнение == и приведение типов",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- замыкания в циклах

_LOOP_KINDS = ("var", "let", "iife", "outer_let", "const_copy")


def _loop_values(start: int, end: int, step: int, inclusive: bool) -> tuple[list[int], int]:
    vals = []
    i = start
    while i <= end if inclusive else i < end:
        vals.append(i)
        i += step
    return vals, i


def _emit(style: str, body_expr: str, ind: str = "  ") -> str:
    if style == "timeout":
        return f"{ind}setTimeout(() => console.log({body_expr}), 0);"
    return f"{ind}fns.push(() => {body_expr});"


def _gen_closures_loop(rng: random.Random) -> Variant:
    while True:
        names = rng.sample(["i", "j", "k", "n", "idx"], 2)
        kinds = rng.sample(_LOOP_KINDS, 2)
        if "var" not in kinds and "outer_let" not in kinds and rng.random() < 0.7:
            continue
        style = rng.choice(("timeout", "fns"))
        lines: list[str] = []
        outs: list[str] = []
        if style == "fns":
            lines.append("const fns = [];")
        for kind, v in zip(kinds, names, strict=True):
            start = rng.randint(0, 3)
            step = rng.choice((1, 1, 2, 3))
            count = rng.randint(2, 3)
            inclusive = rng.random() < 0.4
            end = start + step * (count - 1) + (0 if inclusive else rng.randint(1, step))
            vals, final = _loop_values(start, end, step, inclusive)
            mult = rng.choice((1, 1, 10))
            expr = v if mult == 1 else f"{v} * {mult}"
            cond = f"{v} <= {end}" if inclusive else f"{v} < {end}"
            inc = f"{v}++" if step == 1 else f"{v} += {step}"

            if kind == "var":
                lines.append(f"for (var {v} = {start}; {cond}; {inc}) {{")
                lines.append(_emit(style, expr))
                got = [final] * len(vals)
            elif kind == "let":
                lines.append(f"for (let {v} = {start}; {cond}; {inc}) {{")
                lines.append(_emit(style, expr))
                got = vals
            elif kind == "iife":
                c = "x" if v != "x" else "y"
                cexpr = c if mult == 1 else f"{c} * {mult}"
                lines.append(f"for (var {v} = {start}; {cond}; {inc}) {{")
                lines.append(f"  (function ({c}) {{")
                lines.append(_emit(style, cexpr, "    "))
                lines.append(f"  }})({v});")
                got = vals
            elif kind == "outer_let":
                lines.append(f"let {v};")
                lines.append(f"for ({v} = {start}; {cond}; {inc}) {{")
                lines.append(_emit(style, expr))
                got = [final] * len(vals)
            else:
                c = f"{v}Copy"
                cexpr = c if mult == 1 else f"{c} * {mult}"
                lines.append(f"for (var {v} = {start}; {cond}; {inc}) {{")
                lines.append(f"  const {c} = {v};")
                lines.append(_emit(style, cexpr))
                got = vals
            lines.append("}")
            outs += [str(g * mult) for g in got]
        if style == "fns":
            lines.append("console.log(fns.map((f) => f()).join(' '));")
        break
    return Variant(
        prompt=_NODE_PROMPT,
        key=" ".join(outs),
        code="\n".join(lines),
        extra={"language": "javascript"},
        explanation=(
            "var и переменная, объявленная вне цикла, — одна на все итерации: замыкания видят "
            "итоговое значение. let в заголовке цикла, IIFE и const внутри тела дают копию."
        ),
    )


JS_CLOSURES_LOOP = ItemTemplate(
    id="frontend.js_closures_loop",
    specialization="frontend",
    topic="javascript",
    target_grade="junior",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_closures_loop,
    a=1.4,
    b=-0.7,
    title="Замыкания в циклах: var и let",
    time_limit_s=180,
)

# --------------------------------------------------------------------------- копирование объектов

_PEOPLE = ("Ann", "Bob", "Kate", "Max", "Olga", "Ivan", "Lena", "Petr", "Nina", "Egor")
_CITIES = ("Omsk", "Tula", "Kazan", "Perm", "Sochi", "Tver", "Ufa", "Kursk", "Samara")
_TAGS = ("admin", "beta", "vip", "new", "dev", "qa")
_COPIES = {
    "ref": "const copy = {src};",
    "spread": "const copy = {{ ...{src} }};",
    "assign": "const copy = Object.assign({{}}, {src});",
    "clone": "const copy = structuredClone({src});",
    "json": "const copy = JSON.parse(JSON.stringify({src}));",
}


def _gen_object_copy(rng: random.Random) -> Variant:
    src = rng.choice(("user", "profile", "account", "person"))
    name0, name1 = rng.sample(_PEOPLE, 2)
    city0, city1, city2 = rng.sample(_CITIES, 3)
    tags = rng.sample(_TAGS, rng.randint(1, 3))
    age = rng.randint(18, 60)
    method = rng.choice(tuple(_COPIES))
    deep = method in ("clone", "json")
    lines = [
        f"const {src} = {{",
        f"  name: '{name0}',",
        f"  age: {age},",
        f"  address: {{ city: '{city0}' }},",
        f"  tags: [{', '.join(repr(t) for t in tags)}],",
        "};",
        _COPIES[method].format(src=src),
    ]
    name, city, n_tags, cur_age = name0, city0, len(tags), age
    muts = rng.sample(["name", "city", "push", "address", "age"], rng.randint(2, 3))
    replaced = False  # copy.address заменён новым объектом
    for m in rng.sample(muts, len(muts)):
        if m == "name":
            lines.append(f"copy.name = '{name1}';")
            if method == "ref":
                name = name1
        elif m == "age":
            d = rng.randint(1, 9)
            lines.append(f"copy.age += {d};")
            if method == "ref":
                cur_age += d
        elif m == "city":
            lines.append(f"copy.address.city = '{city1}';")
            if not deep and not replaced:
                city = city1
        elif m == "push":
            lines.append(f"copy.tags.push('{rng.choice(('x', 'y', 'z'))}');")
            if not deep:
                n_tags += 1
        else:
            lines.append(f"copy.address = {{ city: '{city2}' }};")
            if method == "ref":
                city = city2
            else:
                replaced = True
    lines.append(f"console.log({src}.name, {src}.age, {src}.address.city, {src}.tags.length);")
    return Variant(
        prompt=_NODE_PROMPT,
        key=f"{name} {cur_age} {city} {n_tags}",
        code="\n".join(lines),
        extra={"language": "javascript"},
        explanation=(
            "Присваивание копирует ссылку; spread и Object.assign — поверхностная копия "
            "(вложенные объекты общие); structuredClone и JSON — глубокая."
        ),
    )


JS_OBJECT_COPY = ItemTemplate(
    id="frontend.js_object_copy",
    specialization="frontend",
    topic="javascript",
    target_grade="junior",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_object_copy,
    a=1.3,
    b=-0.3,
    title="Ссылки и копирование объектов",
    time_limit_s=180,
)

# --------------------------------------------------------------------------- this

_LABELS = ("Alpha", "Beta", "Gamma", "Delta", "Omega", "Sigma", "Kappa", "Zeta", "Theta")
_CLASSES = ("Widget", "Counter", "Player", "Timer", "Button", "Store")


def _gen_this(rng: random.Random) -> Variant:
    cls = rng.choice(_CLASSES)
    own, oth = rng.sample(_LABELS, 2)
    inst = cls[0].lower() + cls[1:]
    probes = [
        (f"{inst}.show()", own),
        ("show()", "undefined"),
        ("show.call(other)", oth),
        (f"{inst}.show.bind(other)()", oth),
        (f"{inst}.arrow.call(other)", own),
        (f"{inst}.show.bind(other).call({inst})", oth),
        ("other.show()", oth),
        ("other.arrow()", own),
        (f"(0, {inst}.show)()", "undefined"),
        (f"{inst}.show.call(null)", "undefined"),
        (f"{inst}.nested()", "undefined"),
        (f"{inst}.nestedArrow()", own),
        (f"{inst}.nested.call(other)", "undefined"),
        (f"{inst}.nestedArrow.call(other)", oth),
    ]
    while True:
        chosen = rng.sample(probes, 5)
        outs = [o for _, o in chosen]
        if len(set(outs)) >= 2 and outs.count("undefined") <= 3:
            break
    lines = [
        "'use strict';",
        f"class {cls} {{",
        f"  label = '{own}';",
        "  arrow = () => this.label;",
        "  show() {",
        "    return this?.label;",
        "  }",
        "  nested() {",
        "    return [1].map(function () {",
        "      return this?.label;",
        "    })[0];",
        "  }",
        "  nestedArrow() {",
        "    return [1].map(() => this?.label)[0];",
        "  }",
        "}",
        f"const {inst} = new {cls}();",
        f"const show = {inst}.show;",
        f"const other = {{ label: '{oth}', show: {inst}.show, arrow: {inst}.arrow }};",
        *(f"console.log({expr});" for expr, _ in chosen),
    ]
    return Variant(
        prompt=_NODE_PROMPT + " Код выполняется в строгом режиме.",
        key=" ".join(outs),
        code="\n".join(lines),
        extra={"language": "javascript"},
        explanation=(
            "this обычной функции задаётся способом вызова (в strict без объекта — undefined), "
            "bind фиксирует его навсегда; стрелочная функция берёт this из места объявления."
        ),
    )


JS_THIS = ItemTemplate(
    id="frontend.js_this_binding",
    specialization="frontend",
    topic="javascript",
    target_grade="middle",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_this,
    a=1.5,
    b=0.6,
    title="Значение this: вызов, call/bind, стрелочные функции",
    time_limit_s=240,
)

TEMPLATES = (
    JS_COERCION,
    JS_ARRAY_METHODS,
    JS_LOOSE_EQUALITY,
    JS_CLOSURES_LOOP,
    JS_OBJECT_COPY,
    JS_THIS,
)
