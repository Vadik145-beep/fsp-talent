"""Mobile / Kotlin: null-safety, коллекции, data class, scope-функции.

Во всех задачах ответ вычисляется моделью на Python по той же структуре, из которой
собирается код. Независимая сверка — в tests/engine/test_bank_mobile_kotlin.py
(разбор текста кода и пересчёт другим способом).
"""

from __future__ import annotations

import itertools
import random

from ...templates import ItemFormat, ItemTemplate, NumericKey, Variant

_WORDS = ("anna", "oleg", "kazan", "token", "admin", "mobile", "pixel", "sochi", "omsk", "lena")
_DEFAULTS = ("guest", "unknown", "empty", "none", "anon")

# --------------------------------------------------------------------------- null-safety


def _ns_statement(rng: random.Random, kind: int, v: str, s: str | None) -> tuple[str, list[str]]:
    """Строка Kotlin и то, что она напечатает (список строк вывода)."""
    if kind == 0:
        return f"println({v}?.length)", [str(len(s)) if s is not None else "null"]
    if kind == 1:
        d = rng.choice((-1, 0, 99))
        return f"println({v}?.length ?: {d})", [str(len(s) if s is not None else d)]
    if kind == 2:
        w = rng.choice(_DEFAULTS)
        return f'println({v} ?: "{w}")', [s if s is not None else w]
    if kind == 3:
        return f"{v}?.let {{ println(it.uppercase()) }}", [s.upper()] if s is not None else []
    if kind == 4:
        return f"println({v}.isNullOrEmpty())", ["true" if s is None else "false"]
    if kind == 5:
        k = rng.randint(1, 9)
        return f"println({v}.orEmpty().length + {k})", [str((len(s) if s else 0) + k)]
    if kind == 6:
        k = rng.randint(2, 5)
        n = len(s) if s is not None else 0
        return f"println(({v}?.length ?: 0) > {k})", ["true" if n > k else "false"]
    if kind == 7:
        k = rng.randint(2, 3)
        return (
            f"println({v}?.uppercase()?.take({k}))",
            [s.upper()[:k] if s is not None else "null"],
        )
    if kind == 8:
        k = rng.randint(2, 4)
        w = rng.choice(_DEFAULTS)
        return (
            f'if ({v} != null) println({v}.length * {k}) else println("{w}")',
            [str(len(s) * k) if s is not None else w],
        )
    k = rng.randint(2, 4)
    d = rng.choice((-1, 0, 100))
    return (
        f"println({v}?.let {{ it.length * {k} }} ?: {d})",
        [str(len(s) * k if s is not None else d)],
    )


def _gen_null_safety(rng: random.Random) -> Variant:
    fn = rng.choice(("show", "render", "printInfo", "dump", "report"))
    while True:
        names = rng.sample(("a", "b", "name", "city", "email", "nick", "login", "title"), 2)
        values = [rng.choice(_WORDS), None]
        rng.shuffle(values)
        if rng.random() < 0.2:
            values = [None, None]
        vals = dict(zip(names, values, strict=True))
        kinds = rng.sample(range(10), 4)
        lines: list[str] = []
        out: list[str] = []
        for kind in kinds:
            v = rng.choice(names)
            line, printed = _ns_statement(rng, kind, v, vals[v])
            lines.append("    " + line)
            out += printed
        if len(out) >= 3:
            break
    args = ", ".join("null" if vals[n] is None else f'"{vals[n]}"' for n in names)
    params = ", ".join(f"{n}: String?" for n in names)
    code = "\n".join(
        [f"fun {fn}({params}) {{", *lines, "}", "", "fun main() {", f"    {fn}({args})", "}"]
    )
    return Variant(
        prompt=(
            "Что выведет программа на Kotlin 1.9? Перечислите напечатанные значения "
            "в порядке вывода через пробел (null печатается как null)."
        ),
        key=" ".join(out),
        code=code,
        extra={"language": "kotlin"},
        explanation="?. возвращает null для null-получателя, ?: подставляет значение справа, "
        "let выполняется только для не-null.",
    )


NULL_SAFETY = ItemTemplate(
    id="mobile.kotlin_null_safety",
    specialization="mobile",
    topic="kotlin",
    target_grade="intern",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_null_safety,
    a=1.2,
    b=-1.4,
    title="Null-safety в Kotlin: что выведет",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- коллекции


def _coll_line(rng: random.Random, kind: int, xs: list[int]) -> tuple[str, str]:
    """Строка с println и её вывод."""
    if kind == 0:
        t = rng.choice(sorted(xs)[1:-1])
        k = rng.randint(2, 4)
        res = sum(x * k for x in xs if x > t)
        return f"println(xs.filter {{ it > {t} }}.map {{ it * {k} }}.sum())", str(res)
    if kind == 1:
        m = rng.randint(3, 5)
        return f"println(xs.map {{ it % {m} }}.distinct().size)", str(len({x % m for x in xs}))
    if kind == 2:
        s = rng.randint(0, 10)
        d = rng.randint(2, 4)
        res = s + sum(x // d for x in xs)
        return f"println(xs.fold({s}) {{ acc, x -> acc + x / {d} }})", str(res)
    if kind == 3:
        n = rng.randint(2, 3)
        top = sorted(xs, reverse=True)[:n]
        return (
            f'println(xs.sortedDescending().take({n}).joinToString(" "))',
            " ".join(map(str, top)),
        )
    if kind == 4:
        m = rng.randint(3, 4)
        r = rng.randrange(m)
        res = sum(x for x in xs if x % m == r)
        return f"println(xs.groupBy {{ it % {m} }}[{r}]?.sum() ?: 0)", str(res)
    if kind == 5:
        lo = rng.choice(xs)
        hi = rng.choice([x for x in xs if x >= lo] + [lo + 3])
        res = sum(1 for x in xs if lo <= x <= hi)
        return f"println(xs.count {{ it in {lo}..{hi} }})", str(res)
    if kind == 6:
        res = sum(1 for a, b in itertools.pairwise(xs) if b > a)
        return "println(xs.zipWithNext().count { (a, b) -> b > a })", str(res)
    if kind == 7:
        m = rng.randint(2, 3)
        last: dict[int, int] = {}
        for x in xs:
            last[x % m] = x
        return f"println(xs.associateBy {{ it % {m} }}.values.sum())", str(sum(last.values()))
    if kind == 8:
        n = rng.randint(1, 3)
        t = rng.choice(xs)
        found = next((x for x in xs[n:] if x > t), None)
        return (
            f"println(xs.drop({n}).firstOrNull {{ it > {t} }})",
            "null" if found is None else str(found),
        )
    if kind == 9:
        m = rng.randint(2, 4)
        res = sum(1 for x in xs if x % m != 0)
        return f"println(xs.partition {{ it % {m} == 0 }}.second.size)", str(res)
    if kind == 10:
        n = rng.randint(2, 4)
        head = list(reversed(xs[:n]))
        return f'println(xs.take({n}).reversed().joinToString(","))', ",".join(map(str, head))
    if kind == 11:
        n = rng.randint(2, 3)
        chunks = [xs[i : i + n] for i in range(0, len(xs), n)]
        return f"println(xs.chunked({n}).map {{ it.sum() }}.max())", str(max(map(sum, chunks)))
    t = rng.choice(xs)
    idx = next((i for i, x in enumerate(xs) if x > t), -1)
    return f"println(xs.indexOfFirst {{ it > {t} }})", str(idx)


def _gen_collections(rng: random.Random) -> Variant:
    xs = rng.sample(range(1, 31), rng.randint(6, 8))
    kinds = rng.sample(range(13), 3)
    lines: list[str] = []
    out: list[str] = []
    for kind in kinds:
        res = _coll_line(rng, kind, xs)
        lines.append("    " + res[0])
        out.append(res[1])
    code = "\n".join(
        ["fun main() {", f"    val xs = listOf({', '.join(map(str, xs))})", *lines, "}"]
    )
    return Variant(
        prompt=(
            "Что выведет программа на Kotlin 1.9? Перечислите всё напечатанное "
            "в порядке вывода через пробел."
        ),
        key=" ".join(out),
        code=code,
        extra={"language": "kotlin"},
        explanation="Операции над List<Int>: деление целочисленное, .. включает правую границу, "
        "associateBy оставляет последний элемент на ключ.",
    )


COLLECTIONS = ItemTemplate(
    id="mobile.kotlin_collections",
    specialization="mobile",
    topic="kotlin",
    target_grade="junior",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_collections,
    a=1.3,
    b=-0.4,
    title="Цепочки коллекций Kotlin: что выведет",
    time_limit_s=210,
)

# --------------------------------------------------------------------------- data class


_DC_TYPES = (
    ("Item", "id", "title", ("pen", "cup", "book", "lamp")),
    ("Point", "x", "label", ("a", "b", "c", "d")),
    ("User", "age", "name", ("anna", "oleg", "ivan", "lena")),
    ("Product", "price", "sku", ("p1", "p2", "p3", "p4")),
)


def _dc_values(
    rng: random.Random, base_i: int, base_s: str, strs: tuple[str, ...]
) -> tuple[int, str]:
    return rng.choice((base_i, base_i, base_i + 1)), rng.choice((base_s, base_s, strs[0]))


def _gen_data_class(rng: random.Random) -> Variant:
    cls, f_int, f_str, strs = rng.choice(_DC_TYPES)
    is_data = rng.random() < 0.6
    set_name = rng.choice(("items", "seen", "unique", "bag"))
    while True:
        # окружение: имя переменной -> (int, str, instance_id)
        env: dict[str, tuple[int, str, int]] = {}
        next_id = 0
        members_data: set[tuple[int, str]] = set()
        members_plain: set[int] = set()
        lines: list[str] = []
        var_names = ["first", "second", "third"]
        base_i = rng.randint(1, 9)
        base_s = rng.choice(strs)

        n_vars = rng.randint(2, 3)
        for name in var_names[:n_vars]:
            if env and rng.random() < 0.3:
                src = rng.choice(list(env))
                env[name] = env[src]
                lines.append(f"val {name} = {src}")
            else:
                i, s = _dc_values(rng, base_i, base_s, strs)
                env[name] = (i, s, next_id)
                next_id += 1
                lines.append(f'val {name} = {cls}({i}, "{s}")')
        lines.append(f"val {set_name} = mutableSetOf<{cls}>()")
        n_ops = rng.randint(4, 6)
        for _ in range(n_ops):
            op = rng.choice(("var", "var", "new", "copy", "copy_mod", "remove"))
            if op in ("copy", "copy_mod") and not is_data:
                op = "new"
            if op == "var":
                name = rng.choice(list(env))
                i, s, oid = env[name]
                lines.append(f"{set_name}.add({name})")
                members_data.add((i, s))
                members_plain.add(oid)
            elif op == "new":
                i, s = _dc_values(rng, base_i, base_s, strs)
                lines.append(f'{set_name}.add({cls}({i}, "{s}"))')
                members_data.add((i, s))
                members_plain.add(next_id)
                next_id += 1
            elif op == "copy":
                name = rng.choice(list(env))
                i, s, _ = env[name]
                lines.append(f"{set_name}.add({name}.copy())")
                members_data.add((i, s))
            elif op == "copy_mod":
                name = rng.choice(list(env))
                i, s, _ = env[name]
                if rng.random() < 0.5:
                    ni = rng.choice((i, i + 1))
                    lines.append(f"{set_name}.add({name}.copy({f_int} = {ni}))")
                    members_data.add((ni, s))
                else:
                    ns = rng.choice((s, base_s, strs[0]))
                    lines.append(f'{set_name}.add({name}.copy({f_str} = "{ns}"))')
                    members_data.add((i, ns))
            else:
                i, s = _dc_values(rng, base_i, base_s, strs)
                lines.append(f'{set_name}.remove({cls}({i}, "{s}"))')
                members_data.discard((i, s))
                # обычный класс: новый экземпляр не равен ни одному элементу множества
        lines.append(f"println({set_name}.size)")
        size = len(members_data) if is_data else len(members_plain)
        other = len(members_plain) if is_data else len(members_data)
        if size != other and size > 0:
            break
    decl = ("data class" if is_data else "class") + f" {cls}(val {f_int}: Int, val {f_str}: String)"
    code = "\n".join([decl, "", "fun main() {", *("    " + ln for ln in lines), "}"])
    return Variant(
        prompt="Что напечатает программа на Kotlin 1.9? Ответ — одно целое число.",
        key=NumericKey(size),
        code=code,
        extra={"language": "kotlin"},
        explanation=(
            "data class сравнивается по полям основного конструктора (equals/hashCode), "
            "обычный класс — по ссылке."
        ),
    )


DATA_CLASS = ItemTemplate(
    id="mobile.kotlin_data_class_equality",
    specialization="mobile",
    topic="kotlin",
    target_grade="junior",
    format=ItemFormat.NUMERIC,
    generator=_gen_data_class,
    a=1.2,
    b=-0.6,
    title="data class и обычный класс в множестве",
    time_limit_s=180,
)

# --------------------------------------------------------------------------- scope-функции


def _scope_stmt(rng: random.Random, kind: int, xs: list[int]) -> tuple[str, str] | None:
    """Выражение и его значение; xs изменяется на месте, как в Kotlin. None — не подходит."""
    k = rng.randint(2, 9)
    if kind == 0:
        xs.append(k)
        return f"xs.apply {{ add({k}) }}.size", str(len(xs))
    if kind == 1:
        xs.append(k)
        return f"xs.let {{ it.add({k}) }}", "true"
    if kind == 2:
        if len(xs) < 3:
            return None
        xs.pop(0)
        return "xs.also { it.removeAt(0) }.first()", str(xs[0])
    if kind == 3:
        return "xs.run { sum() }", str(sum(xs))
    if kind == 4:
        return f"with(xs) {{ size * {k} }}", str(len(xs) * k)
    if kind == 5:
        xs.append(k)
        return f"xs.run {{ add({k}); size }}", str(len(xs))
    if kind == 6:
        return "xs.let { it.map { x -> x * 2 } }.sum()", str(2 * sum(xs))
    if kind == 7:
        return "xs.apply { map { it * 2 } }.sum()", str(sum(xs))
    if kind == 8:
        return f"xs.also {{ it.map {{ x -> x + {k} }} }}.size", str(len(xs))
    if kind == 9:
        t = rng.randint(2, 6)
        return f"xs.takeIf {{ it.size > {t} }}?.size ?: -1", str(len(xs) if len(xs) > t else -1)
    if kind == 10:
        if len(xs) < 3:
            return None
        xs.pop()
        return "xs.apply { removeAt(lastIndex) }.last()", str(xs[-1])
    return "xs.let { it.first() + it.last() }", str(xs[0] + xs[-1])


def _gen_scope(rng: random.Random) -> Variant:
    while True:
        xs = [rng.randint(1, 9) for _ in range(rng.randint(3, 5))]
        start = list(xs)
        kinds = rng.sample(range(12), 4)
        # хотя бы одна «ловушка»: apply/also возвращают получателя, let/run — результат лямбды
        if not set(kinds) & {1, 7, 8, 2}:
            continue
        stmts = [_scope_stmt(rng, k, xs) for k in kinds]
        if all(s is not None for s in stmts):
            break
    lines = [f"    val r{i + 1} = {s[0]}" for i, s in enumerate(stmts) if s is not None]
    values = [s[1] for s in stmts if s is not None]
    refs = " ".join(f"$r{i + 1}" for i in range(len(values)))
    code = "\n".join(
        [
            "fun main() {",
            f"    val xs = mutableListOf({', '.join(map(str, start))})",
            *lines,
            f'    println("{refs} ${{xs.size}}")',
            "}",
        ]
    )
    return Variant(
        prompt=(
            "Что выведет программа на Kotlin 1.9? Перечислите значения через пробел "
            "в том порядке, в котором они напечатаны."
        ),
        key=" ".join([*values, str(len(xs))]),
        code=code,
        extra={"language": "kotlin"},
        explanation="let/run/with возвращают результат лямбды, apply/also — сам объект.",
    )


SCOPE_FUNCTIONS = ItemTemplate(
    id="mobile.kotlin_scope_functions",
    specialization="mobile",
    topic="kotlin",
    target_grade="middle",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_scope,
    a=1.4,
    b=0.6,
    title="Scope-функции Kotlin: что вернут let/run/apply/also",
    time_limit_s=210,
)

TEMPLATES = (NULL_SAFETY, COLLECTIONS, DATA_CLASS, SCOPE_FUNCTIONS)
