"""Mobile / Swift: независимая сверка ключей трансляцией кода задачи в Python.

- defer → try/finally (finally в Python тоже выполняется при выходе из блока, вложенные
  try дают тот же обратный порядок, что и несколько defer);
- capture list [x] → аргумент лямбды по умолчанию (вычисляется в момент создания),
  замыкание без capture list → обращение к глобальной переменной (позднее связывание);
- struct → копия при присваивании, class → общая ссылка.
"""

import copy
import re

import pytest

from app.testing.engine.bank.mobile import swift
from app.testing.engine.templates import check

SEEDS = range(150)

# --------------------------------------------------------------------------- optionals


def _swift_int(s: str) -> int | None:
    """Int(String) в Swift: необязательный знак и только ASCII-цифры."""
    return int(s) if re.fullmatch(r"[+-]?[0-9]+", s) else None


def run_optionals(code: str) -> str:
    lines = code.split("\n")
    text = " ".join(lines)
    if m := re.fullmatch(r"let x: Int\? = (\d+) print\(x\)", text):
        return f"Optional({m[1]})"
    if m := re.fullmatch(r"let x: Int\? = nil print\(x \?\? (\d+)\)", text):
        return m[1]
    if m := re.fullmatch(r'let name: String\? = "(\w+)" print\(name\?\.count \?\? 0\)', text):
        return str(len(m[1]))
    if m := re.fullmatch(r'let s = "(.*)" print\(Int\(s\) \?\? -1\)', text):
        v = _swift_int(m[1])
        return str(-1 if v is None else v)
    if m := re.fullmatch(
        r"let items: \[Int\] = \[(.*)\] print\(items\.first\.map \{ \$0 \* (\d+) \} \?\? 0\)", text
    ):
        items = [int(v) for v in m[1].split(",") if v.strip()]
        return str(items[0] * int(m[2]) if items else 0)
    if m := re.fullmatch(
        r'let dict = \[(.*)\] if let v = dict\["(\w)"\] '
        r'\{ print\(v\) \} else \{ print\("none"\) \}',
        text,
    ):
        d = dict(re.findall(r'"(\w)": (\d+)', m[1]))
        return d.get(m[2], "none")
    if m := re.fullmatch(
        r"let x: Int\? = (\d+) if let x \{ print\(x \+ (\d+)\) \} else \{ print\(0\) \}", text
    ):
        return str(int(m[1]) + int(m[2]))
    if m := re.fullmatch(r'let s = "(.*)" print\(Int\(s\)\.map \{ \$0 \+ (\d+) \} as Any\)', text):
        v = _swift_int(m[1])
        return "nil" if v is None else f"Optional({v + int(m[2])})"
    if m := re.fullmatch(
        r"let a: Int\? = (\d+) let b: Int\? = nil print\(\(a \?\? 0\) \+ \(b \?\? (\d+)\)\)", text
    ):
        return str(int(m[1]) + int(m[2]))
    if m := re.fullmatch(
        r'var name: String\? = "\w+" name = nil print\(name\?\.uppercased\(\) \?\? "(\w+)"\)', text
    ):
        return m[1]
    raise AssertionError(code)


def test_optionals_independent():
    t = swift.OPTIONALS
    for seed in SEEDS:
        inst = t.generate(seed)
        assert check(inst, run_optionals(inst.public.code)), (seed, inst.public.code)


def test_optionals_manual_examples():
    # print(Optional) печатает Optional(…); Int(" 7") и Int("7.5") — nil; Int("+7") — 7
    assert run_optionals("let x: Int? = 5\nprint(x)") == "Optional(5)"
    assert run_optionals('let s = " 7"\nprint(Int(s) ?? -1)') == "-1"
    assert run_optionals('let s = "+7"\nprint(Int(s) ?? -1)') == "7"
    assert run_optionals('let s = "7.5"\nprint(Int(s) ?? -1)') == "-1"


# --------------------------------------------------------------------------- struct / class


def run_value_reference(code: str) -> str:
    lines = code.split("\n")
    is_struct = lines[0].startswith("struct")
    tname = lines[0].split()[-2] if is_struct else lines[0].split()[2]
    field = re.search(r"var (\w+): Int", code)[1]

    class Obj:
        def __init__(self, v):
            setattr(self, field, v)

    py: list[str] = []
    body = lines[lines.index("") + 1 :]
    for ln in body:
        if ln.startswith("print("):
            py.append(f"out = [{ln[6:-1]}]")
            continue
        ln = re.sub(r"^var ", "", ln)
        ln = re.sub(rf"{tname}\({field}: (-?\d+)\)", r"Obj(\1)", ln)
        if m := re.fullmatch(r"(\w+) = (\w+)", ln):
            # присваивание переменной другой переменной: struct копируется, class — нет
            ln = f"{m[1]} = copy.copy({m[2]})" if is_struct else ln
        py.append(ln)
    scope = {"Obj": Obj, "copy": copy}
    exec("\n".join(py), scope)
    return " ".join(str(v) for v in scope["out"])


def test_value_reference_independent():
    t = swift.VALUE_REFERENCE
    for seed in SEEDS:
        inst = t.generate(seed)
        assert check(inst, run_value_reference(inst.public.code)), (seed, inst.public.code)


def test_value_reference_manual_examples():
    tail = ["", "var a = Counter(value: 3)", "var b = a", "b.value += 5", "print(a.value, b.value)"]
    struct = ["struct Counter {", "    var value: Int", "}"]
    klass = [
        "final class Counter {",
        "    var value: Int",
        "    init(value: Int) { self.value = value }",
        "}",
    ]
    # The Swift Programming Language: «Structures and Enumerations Are Value Types»
    assert run_value_reference("\n".join(struct + tail)) == "3 8"
    assert run_value_reference("\n".join(klass + tail)) == "8 8"


# --------------------------------------------------------------------------- defer


def _parse_block(lines: list[str], i: int) -> tuple[list, int]:
    """Разобрать строки до закрывающей скобки. Возвращает (узлы, индекс после блока)."""
    nodes: list = []
    while i < len(lines):
        ln = lines[i].strip()
        if ln == "}":
            return nodes, i + 1
        if ln.endswith("{"):
            sub, i = _parse_block(lines, i + 1)
            nodes.append(("block", ln[:-1].strip(), sub))
            continue
        nodes.append(("stmt", ln))
        i += 1
    return nodes, i


def _emit(nodes: list, pad: str) -> list[str]:
    out: list[str] = []
    for k, node in enumerate(nodes):
        if node[0] == "block":
            head = node[1]
            if head == "do":
                out.append(f"{pad}if True:")
            elif head.startswith("for i in 1...2"):
                out.append(f"{pad}for i in (1, 2):")
            else:
                out.append(f"{pad}if {head[3:]}:")
            out += _emit(node[2], pad + "    ") or [pad + "    pass"]
            continue
        stmt = node[1]
        if m := re.fullmatch(r'defer \{ print\("(.*)"\) \}', stmt):
            rest = _emit(nodes[k + 1 :], pad + "    ") or [pad + "    pass"]
            label = m[1].replace("\\(i)", "{i}")
            return [*out, f"{pad}try:", *rest, f"{pad}finally:", f'{pad}    out.append(f"{label}")']
        if m := re.fullmatch(r'print\("(.*)"\)', stmt):
            out.append(f'{pad}out.append(f"{m[1].replace(chr(92) + "(i)", "{i}")}")')
        elif stmt == "return":
            out.append(f"{pad}return")
        elif m := re.fullmatch(r"let count = (\d+)", stmt):
            out.append(f"{pad}count = {m[1]}")
        else:
            raise AssertionError(stmt)
    return out


def run_defer(code: str) -> list[str]:
    lines = code.split("\n")
    nodes, _ = _parse_block(lines, 1)
    src = "def run(out):\n" + "\n".join(_emit(nodes, "    "))
    scope: dict = {}
    exec(src, scope)
    out: list[str] = []
    scope["run"](out)
    return out


def test_defer_independent():
    t = swift.DEFER_ORDER
    for seed in SEEDS:
        inst = t.generate(seed)
        expected = run_defer(inst.public.code)
        answer = [inst.public.options[i] for i in inst.key]
        assert answer == expected, (seed, inst.public.code)


def test_defer_manual_examples():
    code = "\n".join(
        [
            "func run() {",
            "    let count = 3",
            '    defer { print("A") }',
            "    if count > 2 {",
            '        defer { print("B") }',
            '        print("C")',
            "        return",
            "    }",
            '    defer { print("D") }',
            '    print("E")',
            "}",
        ]
    )
    # defer — при выходе из своей области, в обратном порядке; D не регистрируется
    assert run_defer(code) == ["C", "B", "A"]


# --------------------------------------------------------------------------- захват в замыканиях


class _Box:
    def __init__(self, v):
        self.value = v


def run_closures(code: str) -> str:
    lines = code.split("\n")[5:]
    py: list[str] = []
    for ln in lines:
        if m := re.fullmatch(r"var (\w+) = Box\((\d+)\)", ln):
            py.append(f"{m[1]} = Box({m[2]})")
        elif m := re.fullmatch(r"var (\w+) = (\d+)", ln):
            py.append(f"{m[1]} = {m[2]}")
        elif m := re.fullmatch(r"let (\w+) = \{ \[(\w+)\] in print\((\w+(?:\.value)?)\) \}", ln):
            py.append(f"{m[1]} = lambda {m[2]}={m[2]}: out.append(str({m[3]}))")
        elif m := re.fullmatch(r"let (\w+) = \{ print\((\w+(?:\.value)?)\) \}", ln):
            py.append(f"{m[1]} = lambda: out.append(str({m[2]}))")
        elif m := re.fullmatch(r"let (\w+) = \{ (\w+) \+= (\d+) \}", ln):
            py.append(f"def {m[1]}():\n    global {m[2]}\n    {m[2]} += {m[3]}")
        elif re.fullmatch(r"\w+\(\)", ln) or re.fullmatch(r"\w+(\.value)? (\+=|=) .*", ln):
            py.append(ln)
        else:
            raise AssertionError(ln)
    scope = {"Box": _Box, "out": []}
    exec("\n".join(py), scope)
    return " ".join(scope["out"])


def test_closure_capture_independent():
    t = swift.CLOSURE_CAPTURE
    for seed in SEEDS:
        inst = t.generate(seed)
        assert check(inst, run_closures(inst.public.code)), (seed, inst.public.code)


def test_closure_capture_manual_example():
    code = "\n".join(
        [
            "final class Box {",
            "    var value: Int",
            "    init(_ value: Int) { self.value = value }",
            "}",
            "",
            "var count = 1",
            "var box = Box(10)",
            "let f = { [count] in print(count) }",
            "let g = { print(count) }",
            "let h = { [box] in print(box.value) }",
            "count += 4",
            "box.value = 20",
            "box = Box(30)",
            "f()",
            "g()",
            "h()",
        ]
    )
    # The Swift Programming Language, «Capture Lists»: значение копируется при создании
    assert run_closures(code) == "1 5 20"


# --------------------------------------------------------------------------- retain cycle


def test_retain_cycle_bug_line_is_the_only_strong_stored_capture():
    t = swift.RETAIN_CYCLE
    safe_markers = (
        "[weak self]",
        "[unowned self]",
        "DispatchQueue.main.async",
        "UIView.animate",
        ".map {",
    )
    for seed in SEEDS:
        inst = t.generate(seed)
        lines = inst.public.code.split("\n")
        bug = lines[inst.key - 1]
        assert "self." in bug and not any(m in bug for m in safe_markers), bug
        start = lines.index("        super.viewDidLoad()") + 1
        end = lines.index("    }", start)
        assert start < inst.key <= end
        for n in range(start + 1, end + 1):
            ln = lines[n - 1]
            if n != inst.key:
                # остальные строки либо без self, либо захватывают его безопасно
                assert "self" not in ln or any(m in ln for m in safe_markers), (seed, ln)


@pytest.mark.parametrize("template", swift.TEMPLATES, ids=lambda t: t.id)
def test_swift_answers_vary(template):
    keys = {repr(template.generate(s).key) for s in range(100)}
    assert len(keys) >= 3
