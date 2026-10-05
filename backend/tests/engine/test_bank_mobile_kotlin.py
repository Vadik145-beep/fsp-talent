"""Mobile / Kotlin: независимая сверка ключей.

Рантайма Kotlin нет, поэтому ответ пересчитывается по ТЕКСТУ кода задачи (а не по
внутренней структуре генератора): строки разбираются регулярными выражениями и
выполняются эквивалентным кодом на Python. Плюс эталонные примеры, проверенные вручную.
"""

import dataclasses
import re

import pytest

from app.testing.engine.bank.mobile import kotlin
from app.testing.engine.templates import check

SEEDS = range(150)


def _lines(code: str) -> list[str]:
    return [ln.strip() for ln in code.split("\n")]


# --------------------------------------------------------------------------- null-safety


def _ns_eval(line: str, env: dict) -> list[str]:
    """Выполнить одну строку тела функции из задачи null-safety."""

    def val(v):
        return env[v]

    def length(v):
        return None if val(v) is None else len(val(v))

    def show(x):
        if x is None:
            return "null"
        if isinstance(x, bool):
            return "true" if x else "false"
        return str(x)

    if m := re.fullmatch(r"println\((\w+)\?\.length\)", line):
        return [show(length(m[1]))]
    if m := re.fullmatch(r"println\((\w+)\?\.length \?: (-?\d+)\)", line):
        n = length(m[1])
        return [show(int(m[2]) if n is None else n)]
    if m := re.fullmatch(r'println\((\w+) \?: "(\w+)"\)', line):
        return [show(m[2] if val(m[1]) is None else val(m[1]))]
    if m := re.fullmatch(r"(\w+)\?\.let \{ println\(it\.uppercase\(\)\) \}", line):
        return [] if val(m[1]) is None else [val(m[1]).upper()]
    if m := re.fullmatch(r"println\((\w+)\.isNullOrEmpty\(\)\)", line):
        return [show(not val(m[1]))]
    if m := re.fullmatch(r"println\((\w+)\.orEmpty\(\)\.length \+ (\d+)\)", line):
        return [show(len(val(m[1]) or "") + int(m[2]))]
    if m := re.fullmatch(r"println\(\((\w+)\?\.length \?: 0\) > (\d+)\)", line):
        return [show((length(m[1]) or 0) > int(m[2]))]
    if m := re.fullmatch(r"println\((\w+)\?\.uppercase\(\)\?\.take\((\d+)\)\)", line):
        return [show(None if val(m[1]) is None else val(m[1]).upper()[: int(m[2])])]
    if m := re.fullmatch(
        r'if \((\w+) != null\) println\(\1\.length \* (\d+)\) else println\("(\w+)"\)', line
    ):
        return [show(m[3] if val(m[1]) is None else len(val(m[1])) * int(m[2]))]
    if m := re.fullmatch(r"println\((\w+)\?\.let \{ it\.length \* (\d+) \} \?: (-?\d+)\)", line):
        return [show(int(m[3]) if val(m[1]) is None else len(val(m[1])) * int(m[2]))]
    raise AssertionError(f"неизвестная строка: {line}")


def run_null_safety(code: str) -> str:
    lines = _lines(code)
    params = re.findall(r"(\w+): String\?", lines[0])
    call = lines[lines.index("fun main() {") + 1]
    args = [
        None if a.strip() == "null" else a.strip().strip('"')
        for a in call[call.index("(") + 1 : -1].split(",")
    ]
    env = dict(zip(params, args, strict=True))
    out: list[str] = []
    body = lines[1 : lines.index("}")]
    for ln in body:
        out += _ns_eval(ln, env)
    return " ".join(out)


def test_null_safety_independent():
    t = kotlin.NULL_SAFETY
    for seed in SEEDS:
        inst = t.generate(seed)
        assert check(inst, run_null_safety(inst.public.code)), (seed, inst.public.code)


def test_null_safety_manual_examples():
    code = "\n".join(
        [
            "fun show(a: String?, b: String?) {",
            "    println(a?.length)",
            '    println(b ?: "guest")',
            "    a?.let { println(it.uppercase()) }",
            "    println(b.isNullOrEmpty())",
            "}",
            "",
            "fun main() {",
            '    show(null, "anna")',
            "}",
        ]
    )
    # проверено вручную по документации Kotlin (Null safety): ?. → null, ?: → правая часть
    assert run_null_safety(code) == "null anna false"


# --------------------------------------------------------------------------- коллекции


def _coll_eval(line: str, xs: list[int]) -> str:
    def s(x):
        return "null" if x is None else str(x)

    if m := re.fullmatch(
        r"println\(xs\.filter \{ it > (\d+) \}\.map \{ it \* (\d+) \}\.sum\(\)\)", line
    ):
        return s(sum(x * int(m[2]) for x in xs if x > int(m[1])))
    if m := re.fullmatch(r"println\(xs\.map \{ it % (\d+) \}\.distinct\(\)\.size\)", line):
        return s(len(set(x % int(m[1]) for x in xs)))
    if m := re.fullmatch(r"println\(xs\.fold\((\d+)\) \{ acc, x -> acc \+ x / (\d+) \}\)", line):
        acc = int(m[1])
        for x in xs:
            acc += int(x / int(m[2]))  # Kotlin: деление Int с отбрасыванием дроби
        return s(acc)
    if m := re.fullmatch(
        r'println\(xs\.sortedDescending\(\)\.take\((\d+)\)\.joinToString\(" "\)\)', line
    ):
        return " ".join(map(str, sorted(xs)[::-1][: int(m[1])]))
    if m := re.fullmatch(
        r"println\(xs\.groupBy \{ it % (\d+) \}\[(\d+)\]\?\.sum\(\) \?: 0\)", line
    ):
        groups: dict[int, list[int]] = {}
        for x in xs:
            groups.setdefault(x % int(m[1]), []).append(x)
        g = groups.get(int(m[2]))
        return s(sum(g) if g is not None else 0)
    if m := re.fullmatch(r"println\(xs\.count \{ it in (\d+)\.\.(\d+) \}\)", line):
        return s(len([x for x in xs if x in range(int(m[1]), int(m[2]) + 1)]))
    if line == "println(xs.zipWithNext().count { (a, b) -> b > a })":
        return s(len([i for i in range(len(xs) - 1) if xs[i + 1] > xs[i]]))
    if m := re.fullmatch(r"println\(xs\.associateBy \{ it % (\d+) \}\.values\.sum\(\)\)", line):
        d = {}
        for x in xs:
            d[x % int(m[1])] = x
        return s(sum(d.values()))
    if m := re.fullmatch(r"println\(xs\.drop\((\d+)\)\.firstOrNull \{ it > (\d+) \}\)", line):
        rest = [x for x in xs[int(m[1]) :] if x > int(m[2])]
        return s(rest[0] if rest else None)
    if m := re.fullmatch(r"println\(xs\.partition \{ it % (\d+) == 0 \}\.second\.size\)", line):
        return s(len(xs) - len([x for x in xs if x % int(m[1]) == 0]))
    if m := re.fullmatch(r'println\(xs\.take\((\d+)\)\.reversed\(\)\.joinToString\(","\)\)', line):
        return ",".join(map(str, xs[: int(m[1])][::-1]))
    if m := re.fullmatch(r"println\(xs\.chunked\((\d+)\)\.map \{ it\.sum\(\) \}\.max\(\)\)", line):
        n = int(m[1])
        return s(max(sum(xs[i : i + n]) for i in range(0, len(xs), n)))
    if m := re.fullmatch(r"println\(xs\.indexOfFirst \{ it > (\d+) \}\)", line):
        return s(next((i for i, x in enumerate(xs) if x > int(m[1])), -1))
    raise AssertionError(f"неизвестная строка: {line}")


def run_collections(code: str) -> str:
    lines = _lines(code)
    xs = [int(v) for v in re.search(r"listOf\((.*)\)", lines[1])[1].split(",")]
    return " ".join(_coll_eval(ln, xs) for ln in lines[2:-1])


def test_collections_independent():
    t = kotlin.COLLECTIONS
    for seed in SEEDS:
        inst = t.generate(seed)
        assert check(inst, run_collections(inst.public.code)), (seed, inst.public.code)


def test_collections_manual_examples():
    code = "\n".join(
        [
            "fun main() {",
            "    val xs = listOf(5, 12, 7, 3, 20, 8)",
            "    println(xs.fold(0) { acc, x -> acc + x / 4 })",
            "    println(xs.associateBy { it % 2 }.values.sum())",
            "    println(xs.count { it in 7..12 })",
            "}",
        ]
    )
    # 1+3+1+0+5+2 = 12; последние по ключу: нечётный 3, чётный 8 → 11; 12, 7, 8 → 3
    assert run_collections(code) == "12 11 3"


# --------------------------------------------------------------------------- data class


def run_data_class(code: str) -> int:
    """Транслировать в Python: data class → frozen dataclass, class → сравнение по ссылке."""
    lines = _lines(code)
    m = re.fullmatch(r"(data class|class) (\w+)\(val (\w+): Int, val (\w+): String\)", lines[0])
    is_data, cls, f_int, f_str = m[1] == "data class", m[2], m[3], m[4]
    if is_data:
        klass = dataclasses.make_dataclass(cls, [(f_int, int), (f_str, str)], frozen=True)
    else:

        def init(self, a, b):
            setattr(self, f_int, a)
            setattr(self, f_str, b)

        klass = type(cls, (), {"__init__": init})
    py: list[str] = []
    for ln in lines[3:-1]:
        ln = re.sub(r"^val ", "", ln)
        ln = re.sub(r"mutableSetOf<\w+>\(\)", "set()", ln)
        ln = re.sub(r"(\w+)\.copy\(\)", r"replace(\1)", ln)
        ln = re.sub(r"(\w+)\.copy\((\w+) = ([^)]*)\)", r"replace(\1, \2=\3)", ln)
        ln = re.sub(r"\.remove\(", ".discard(", ln)
        ln = re.sub(r"println\((\w+)\.size\)", r"result = len(\1)", ln)
        py.append(ln)
    scope = {cls: klass, "replace": dataclasses.replace}
    exec("\n".join(py), scope)
    return scope["result"]


def test_data_class_independent():
    t = kotlin.DATA_CLASS
    for seed in SEEDS:
        inst = t.generate(seed)
        assert run_data_class(inst.public.code) == inst.key.value, (seed, inst.public.code)


def test_data_class_manual_examples():
    base = [
        "",
        "fun main() {",
        '    val first = Item(1, "pen")',
        "    val items = mutableSetOf<Item>()",
        "    items.add(first)",
        '    items.add(Item(1, "pen"))',
        "    items.add(first)",
        '    items.remove(Item(1, "pen"))',
        "    println(items.size)",
        "}",
    ]
    # data class: equals по полям — после remove множество пустое
    assert (
        run_data_class("\n".join(["data class Item(val id: Int, val title: String)", *base])) == 0
    )
    # обычный класс: два разных объекта, remove нового экземпляра ничего не удаляет
    assert run_data_class("\n".join(["class Item(val id: Int, val title: String)", *base])) == 2


# --------------------------------------------------------------------------- scope-функции


def _scope_eval(expr: str, xs: list[int]) -> str:
    """Значение выражения; xs изменяется на месте, как MutableList в Kotlin."""
    if m := re.fullmatch(r"xs\.apply \{ add\((\d+)\) \}\.size", expr):
        xs.append(int(m[1]))  # apply возвращает получателя
        return str(len(xs))
    if m := re.fullmatch(r"xs\.let \{ it\.add\((\d+)\) \}", expr):
        xs.append(int(m[1]))  # let возвращает результат лямбды: add → true
        return "true"
    if expr == "xs.also { it.removeAt(0) }.first()":
        del xs[0]
        return str(xs[0])
    if expr == "xs.run { sum() }":
        return str(sum(xs))
    if m := re.fullmatch(r"with\(xs\) \{ size \* (\d+) \}", expr):
        return str(len(xs) * int(m[1]))
    if m := re.fullmatch(r"xs\.run \{ add\((\d+)\); size \}", expr):
        xs.append(int(m[1]))
        return str(len(xs))
    if expr == "xs.let { it.map { x -> x * 2 } }.sum()":
        return str(sum(2 * x for x in xs))
    if expr == "xs.apply { map { it * 2 } }.sum()":
        return str(sum(xs))  # результат map выброшен, apply вернул xs
    if m := re.fullmatch(r"xs\.also \{ it\.map \{ x -> x \+ (\d+) \} \}\.size", expr):
        return str(len(xs))
    if m := re.fullmatch(r"xs\.takeIf \{ it\.size > (\d+) \}\?\.size \?: -1", expr):
        return str(len(xs) if len(xs) > int(m[1]) else -1)
    if expr == "xs.apply { removeAt(lastIndex) }.last()":
        xs.pop()
        return str(xs[-1])
    if expr == "xs.let { it.first() + it.last() }":
        return str(xs[0] + xs[-1])
    raise AssertionError(f"неизвестное выражение: {expr}")


def run_scope(code: str) -> str:
    lines = _lines(code)
    xs = [int(v) for v in re.search(r"mutableListOf\((.*)\)", lines[1])[1].split(",")]
    vals = {}
    for ln in lines[2:]:
        if m := re.fullmatch(r"val (r\d) = (.*)", ln):
            vals[m[1]] = _scope_eval(m[2], xs)
        elif ln.startswith("println("):
            tmpl = re.search(r'"(.*)"', ln)[1]
            tmpl = tmpl.replace("${xs.size}", str(len(xs)))
            return re.sub(r"\$(r\d)", lambda mm: vals[mm[1]], tmpl)
    raise AssertionError("нет println")


def test_scope_independent():
    t = kotlin.SCOPE_FUNCTIONS
    for seed in SEEDS:
        inst = t.generate(seed)
        assert check(inst, run_scope(inst.public.code)), (seed, inst.public.code)


def test_scope_manual_examples():
    code = "\n".join(
        [
            "fun main() {",
            "    val xs = mutableListOf(1, 2, 3)",
            "    val r1 = xs.apply { add(4) }.size",
            "    val r2 = xs.let { it.add(5) }",
            "    val r3 = xs.apply { map { it * 2 } }.sum()",
            "    val r4 = xs.run { add(6); size }",
            '    println("$r1 $r2 $r3 $r4 ${xs.size}")',
            "}",
        ]
    )
    # по документации Scope functions: apply → объект, let/run → результат лямбды
    assert run_scope(code) == "4 true 15 6 6"


@pytest.mark.parametrize("template", kotlin.TEMPLATES, ids=lambda t: t.id)
def test_kotlin_answers_vary(template):
    keys = {repr(template.generate(s).key) for s in range(100)}
    assert len(keys) >= 3
