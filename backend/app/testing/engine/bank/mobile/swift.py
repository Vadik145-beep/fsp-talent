"""Mobile / Swift: optionals, value/reference типы, defer, захват в замыканиях, retain cycle.

Независимая сверка — tests/engine/test_bank_mobile_swift.py: код задачи транслируется
в Python (defer → try/finally, capture list → аргумент по умолчанию) и выполняется.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from ...templates import ItemFormat, ItemTemplate, Variant, make_ordering

# --------------------------------------------------------------------------- optionals

_SW_WORDS = ("anna", "swift", "kazan", "token", "omsk", "ios", "pixel", "lena")


def _gen_optionals(rng: random.Random) -> Variant:
    kind = rng.randrange(10)
    n = rng.randint(2, 99)
    k = rng.randint(1, 9)
    if kind == 0:
        code = f"let x: Int? = {n}\nprint(x)"
        ans = f"Optional({n})"
    elif kind == 1:
        code = f"let x: Int? = nil\nprint(x ?? {n})"
        ans = str(n)
    elif kind == 2:
        w = rng.choice(_SW_WORDS)
        code = f'let name: String? = "{w}"\nprint(name?.count ?? 0)'
        ans = str(len(w))
    elif kind == 3:
        s, val = rng.choice(
            (
                (str(n), n),
                (f"+{n}", n),
                (f"-{n}", -n),
                (f"{n} ", None),
                (f" {n}", None),
                (f"{n}.5", None),
                (f"{n}a", None),
                (f"0x{n}", None),
            )
        )
        code = f'let s = "{s}"\nprint(Int(s) ?? -1)'
        ans = str(val if val is not None else -1)
    elif kind == 4:
        items = [rng.randint(1, 20) for _ in range(rng.choice((0, 2, 3, 4)))]
        code = (
            f"let items: [Int] = [{', '.join(map(str, items))}]\n"
            f"print(items.first.map {{ $0 * {k} }} ?? 0)"
        )
        ans = str(items[0] * k if items else 0)
    elif kind == 5:
        keys = rng.sample(("a", "b", "c", "d", "e"), 3)
        d = {key: rng.randint(1, 50) for key in keys}
        ask = rng.choice((*keys, "z", "x"))
        body = ", ".join(f'"{key}": {v}' for key, v in d.items())
        code = (
            f'let dict = [{body}]\nif let v = dict["{ask}"] {{ print(v) }} else {{ print("none") }}'
        )
        ans = str(d[ask]) if ask in d else "none"
    elif kind == 6:
        code = f"let x: Int? = {n}\nif let x {{ print(x + {k}) }} else {{ print(0) }}"
        ans = str(n + k)
    elif kind == 7:
        ok = rng.random() < 0.5
        s = str(n) if ok else f"{n}x"
        code = f'let s = "{s}"\nprint(Int(s).map {{ $0 + {k} }} as Any)'
        ans = f"Optional({n + k})" if ok else "nil"
    elif kind == 8:
        dv = rng.randint(1, 9)
        code = f"let a: Int? = {n}\nlet b: Int? = nil\nprint((a ?? 0) + (b ?? {dv}))"
        ans = str(n + dv)
    else:
        w = rng.choice(_SW_WORDS)
        dflt = rng.choice(("guest", "empty", "none"))
        code = f'var name: String? = "{w}"\nname = nil\nprint(name?.uppercased() ?? "{dflt}")'
        ans = dflt
    return Variant(
        prompt=(
            "Что напечатает этот код на Swift 5.9? Введите напечатанное значение "
            "ровно так, как его выведет print."
        ),
        key=(ans,),
        code=code,
        extra={"language": "swift"},
        explanation="print(Optional) печатает Optional(…), ?? подставляет значение для nil, "
        "Int(String) возвращает nil для строк с пробелами, точкой и т. п.",
    )


OPTIONALS = ItemTemplate(
    id="mobile.swift_optionals",
    specialization="mobile",
    topic="swift",
    target_grade="intern",
    format=ItemFormat.SHORT_TEXT,
    generator=_gen_optionals,
    a=1.1,
    b=-1.2,
    title="Optionals в Swift: что напечатает",
    time_limit_s=120,
)

# --------------------------------------------------------------------------- value vs reference


def _vr_run(ops: list[Item], is_struct: bool) -> list[int]:
    """Модель: struct копируется при присваивании, class — общая ссылка."""
    env: dict[str, list[int]] = {}  # имя -> «объект» (список из одного числа)
    for op in ops:
        kind = op[0]
        if kind == "new":
            env[op[1]] = [op[2]]
        elif kind == "copy":
            env[op[1]] = list(env[op[2]]) if is_struct else env[op[2]]
        elif kind == "mut":
            _, name, sym, k = op
            box = env[name]
            if sym == "+=":
                box[0] += k
            elif sym == "-=":
                box[0] -= k
            elif sym == "*=":
                box[0] *= k
            else:
                box[0] = k
    return [env[name][0] for name in ops_var_order(ops)]


def ops_var_order(ops: list[Item]) -> list[str]:
    seen: list[str] = []
    for op in ops:
        if op[0] in ("new", "copy") and op[1] not in seen:
            seen.append(op[1])
    return seen


def _gen_value_reference(rng: random.Random) -> Variant:
    tname, field_name = rng.choice(
        (("Counter", "value"), ("Wallet", "balance"), ("Score", "points"), ("Badge", "count"))
    )
    names = list(rng.choice((("a", "b", "c"), ("x", "y", "z"), ("first", "second", "third"))))
    is_struct = rng.random() < 0.5
    while True:
        ops: list[Item] = [("new", names[0], rng.randint(1, 9))]
        declared = [names[0]]
        lines = [f"var {names[0]} = {tname}({field_name}: {ops[0][2]})"]
        for name in names[1:]:
            if rng.random() < 0.85:
                src = rng.choice(declared)
                ops.append(("copy", name, src))
                lines.append(f"var {name} = {src}")
            else:
                v = rng.randint(1, 9)
                ops.append(("new", name, v))
                lines.append(f"var {name} = {tname}({field_name}: {v})")
            declared.append(name)
            if rng.random() < 0.5:
                tgt = rng.choice(declared)
                sym = rng.choice(("+=", "-=", "*=", "="))
                k = rng.randint(2, 9)
                ops.append(("mut", tgt, sym, k))
                lines.append(f"{tgt}.{field_name} {sym} {k}")
        for _ in range(rng.randint(2, 3)):
            if rng.random() < 0.2:
                tgt, src = rng.sample(names, 2)
                ops.append(("copy", tgt, src))
                lines.append(f"{tgt} = {src}")
            else:
                tgt = rng.choice(names)
                sym = rng.choice(("+=", "-=", "*=", "="))
                k = rng.randint(2, 9)
                ops.append(("mut", tgt, sym, k))
                lines.append(f"{tgt}.{field_name} {sym} {k}")
        res = _vr_run(ops, is_struct)
        if res != _vr_run(ops, not is_struct):
            break
    if is_struct:
        decl = [f"struct {tname} {{", f"    var {field_name}: Int", "}"]
    else:
        decl = [
            f"final class {tname} {{",
            f"    var {field_name}: Int",
            f"    init({field_name}: Int) {{ self.{field_name} = {field_name} }}",
            "}",
        ]
    printed = ", ".join(f"{n}.{field_name}" for n in names)
    code = "\n".join([*decl, "", *lines, f"print({printed})"])
    return Variant(
        prompt="Что напечатает код на Swift 5.9? Перечислите числа через пробел.",
        key=" ".join(map(str, res)),
        code=code,
        extra={"language": "swift"},
        explanation="struct — тип-значение (копируется при присваивании), "
        "class — ссылочный тип (переменные указывают на один объект).",
    )


VALUE_REFERENCE = ItemTemplate(
    id="mobile.swift_value_reference",
    specialization="mobile",
    topic="swift",
    target_grade="junior",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_value_reference,
    a=1.4,
    b=-0.5,
    title="struct и class в Swift: копирование",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- defer


Item = tuple[Any, ...]


@dataclass
class _Blk:
    kind: str  # "func" | "do" | "if" | "for"
    items: list[Item] = field(default_factory=list)
    cond: bool = True  # для if
    cond_text: str = ""


def _defer_exec(block: _Blk, out: list[str], it: int | None = None) -> bool:
    """Выполнить блок Swift. Возвращает True, если был return. defer — LIFO при выходе."""
    deferred: list[str] = []
    returned = False
    try:
        for item in block.items:
            kind = item[0]
            if kind == "print":
                out.append(item[1].replace("\\(i)", str(it)))
            elif kind == "defer":
                deferred.append(item[1])
            elif kind == "return":
                returned = True
                break
            elif kind == "block":
                sub: _Blk = item[1]
                if sub.kind == "for":
                    for i in (1, 2):
                        if _defer_exec(sub, out, i):
                            returned = True
                            break
                elif sub.kind == "do" or sub.cond:
                    returned = _defer_exec(sub, out, it)
                if returned:
                    break
    finally:
        for label in reversed(deferred):
            out.append(label.replace("\\(i)", str(it)))
    return returned


def _render_block(block: _Blk, indent: int) -> list[str]:
    pad = " " * indent
    lines: list[str] = []
    for item in block.items:
        kind = item[0]
        if kind == "print":
            lines.append(f'{pad}print("{item[1]}")')
        elif kind == "defer":
            lines.append(f'{pad}defer {{ print("{item[1]}") }}')
        elif kind == "return":
            lines.append(f"{pad}return")
        else:
            sub: _Blk = item[1]
            if sub.kind == "do":
                head = "do {"
            elif sub.kind == "for":
                head = "for i in 1...2 {"
            else:
                head = f"if {sub.cond_text} {{"
            lines.append(pad + head)
            lines += _render_block(sub, indent + 4)
            lines.append(pad + "}")
    return lines


def _defer_attempt(rng: random.Random, count: int) -> tuple[_Blk, list[str]] | None:
    """Одна попытка собрать функцию с defer; None — если вышло неинтересно."""
    letters = list("ABCDEFGHKMNPRSTUVWXY")
    rng.shuffle(letters)

    def label() -> str:
        return letters.pop()

    top: list[Item] = []
    n_top = rng.randint(4, 6)
    used_block = False
    for idx in range(n_top):
        r = rng.random()
        if r < 0.3 and not used_block:
            used_block = True
            kind = rng.choice(("do", "if", "if", "for"))
            blk = _Blk(kind=kind)
            if kind == "for":
                blk.items = [("defer", "L" + label() + r"\(i)"), ("print", label() + r"\(i)")]
                rng.shuffle(blk.items)
            else:
                blk.items = [
                    ("defer" if rng.random() < 0.5 else "print", label())
                    for _ in range(rng.randint(2, 3))
                ]
                if not any(i[0] == "defer" for i in blk.items):
                    blk.items[0] = ("defer", blk.items[0][1])
                if kind == "if":
                    t = rng.randint(0, 6)
                    blk.cond = count > t
                    blk.cond_text = f"count > {t}"
                    if blk.cond and idx < n_top - 1 and rng.random() < 0.4:
                        blk.items.append(("return",))
            top.append(("block", blk))
        elif r < 0.65:
            top.append(("defer", label()))
        else:
            top.append(("print", label()))
    if not used_block:
        return None
    func = _Blk(kind="func", items=top)
    out: list[str] = []
    _defer_exec(func, out)
    textual = _render_block(func, 0)
    textual_labels = [t.split('"')[1] for t in textual if '"' in t]
    if len(out) >= 4 and len(out) == len(set(out)) and out != textual_labels[: len(out)]:
        return func, out
    return None


def _gen_defer(rng: random.Random) -> Variant:
    fn = rng.choice(("run", "work", "process", "load", "handle"))
    while True:
        count = rng.randint(1, 5)
        res = _defer_attempt(rng, count)
        if res is not None:
            func, out = res
            break
    body = _render_block(func, 4)
    code = "\n".join([f"func {fn}() {{", f"    let count = {count}", *body, "}", "", f"{fn}()"])
    return make_ordering(
        rng,
        "В каком порядке будут напечатаны строки при вызове функции (Swift 5.9)? "
        "Расставьте их в порядке вывода.",
        out,
        code=code,
        extra={"language": "swift"},
        explanation="defer выполняется при выходе из своей области видимости, "
        "несколько defer — в обратном порядке; defer после return не регистрируется.",
    )


DEFER_ORDER = ItemTemplate(
    id="mobile.swift_defer_order",
    specialization="mobile",
    topic="swift",
    target_grade="middle",
    format=ItemFormat.ORDERING,
    generator=_gen_defer,
    a=1.3,
    b=0.4,
    title="Порядок выполнения defer в Swift",
    time_limit_s=180,
)

# --------------------------------------------------------------------------- захват в замыканиях


def _closure_attempt(
    rng: random.Random, xv: str, bv: str
) -> tuple[list[str], list[str], list[str]]:
    """Одна попытка: (строки кода, вывод, вывод «наивной» модели без копирования)."""
    x = rng.randint(1, 9)
    box_obj = [rng.randint(10, 40)]
    lines: list[str] = []
    out: list[str] = []
    naive: list[str] = []  # если бы capture list не копировал значение
    closures: dict[str, tuple[str, Any]] = {}
    names = iter(("f", "g", "h", "k", "m", "p"))

    def call(name: str) -> None:
        nonlocal x
        kind, captured = closures[name]
        if kind == "cap_int":
            out.append(str(captured))
            naive.append(str(x))
        elif kind == "int":
            out.append(str(x))
            naive.append(str(x))
        elif kind == "cap_box":
            out.append(str(captured[0]))
            naive.append(str(box_obj[0]))
        elif kind == "box":
            out.append(str(box_obj[0]))
            naive.append(str(box_obj[0]))
        else:  # inc
            x += captured

    lines.append(f"var {xv} = {x}")
    lines.append(f"var {bv} = Box({box_obj[0]})")
    defined: list[str] = []
    for _ in range(rng.randint(6, 8)):
        r = rng.random()
        if (r < 0.4 and len(defined) < 4) or not defined:
            kind = rng.choice(("cap_int", "cap_int", "int", "cap_box", "box", "inc"))
            name = next(names)
            if kind == "cap_int":
                closures[name] = (kind, x)
                lines.append(f"let {name} = {{ [{xv}] in print({xv}) }}")
            elif kind == "int":
                closures[name] = (kind, None)
                lines.append(f"let {name} = {{ print({xv}) }}")
            elif kind == "cap_box":
                closures[name] = (kind, box_obj)
                lines.append(f"let {name} = {{ [{bv}] in print({bv}.value) }}")
            elif kind == "box":
                closures[name] = (kind, None)
                lines.append(f"let {name} = {{ print({bv}.value) }}")
            else:
                d = rng.randint(1, 4)
                closures[name] = (kind, d)
                lines.append(f"let {name} = {{ {xv} += {d} }}")
            defined.append(name)
        elif r < 0.7:
            m = rng.randrange(3)
            if m == 0:
                d = rng.randint(2, 6)
                x += d
                lines.append(f"{xv} += {d}")
            elif m == 1:
                v = rng.randint(41, 70)
                box_obj[0] = v
                lines.append(f"{bv}.value = {v}")
            else:
                v = rng.randint(71, 99)
                box_obj = [v]
                lines.append(f"{bv} = Box({v})")
        else:
            name = rng.choice(defined)
            call(name)
            lines.append(f"{name}()")
    for name in rng.sample(defined, len(defined)):
        call(name)
        lines.append(f"{name}()")
    return lines, out, naive


def _gen_closure_capture(rng: random.Random) -> Variant:
    xv = rng.choice(("count", "total", "level", "step"))
    bv = rng.choice(("box", "holder", "cell", "store"))
    while True:
        lines, out, naive = _closure_attempt(rng, xv, bv)
        if len(out) >= 3 and out != naive:
            break
    decl = [
        "final class Box {",
        "    var value: Int",
        "    init(_ value: Int) { self.value = value }",
        "}",
        "",
    ]
    return Variant(
        prompt=(
            "Что напечатает код на Swift 5.9 (верхний уровень main.swift)? "
            "Перечислите числа через пробел в порядке вывода."
        ),
        key=" ".join(out),
        code="\n".join([*decl, *lines]),
        extra={"language": "swift"},
        explanation="Capture list [x] копирует значение (или ссылку на объект) в момент "
        "создания замыкания; без него замыкание видит текущее значение переменной.",
    )


CLOSURE_CAPTURE = ItemTemplate(
    id="mobile.swift_closure_capture",
    specialization="mobile",
    topic="swift",
    target_grade="senior",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_closure_capture,
    a=1.5,
    b=1.3,
    title="Capture list в замыканиях Swift",
    time_limit_s=240,
)

# --------------------------------------------------------------------------- retain cycle

# (категория, безопасная строка, строка с утечкой) — внутри viewDidLoad
_RC_PATTERNS = (
    (
        "sink",
        "viewModel.$items.sink { [weak self] items in self?.render(items) }"
        ".store(in: &cancellables)",
        "viewModel.$items.sink { items in self.render(items) }.store(in: &cancellables)",
    ),
    (
        "finish",
        "onFinish = { [weak self] in self?.dismiss(animated: true) }",
        "onFinish = { self.dismiss(animated: true) }",
    ),
    (
        "timer",
        "timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) "
        "{ [weak self] _ in self?.tick() }",
        "timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { _ in self.tick() }",
    ),
    (
        "action",
        "saveButton.addAction(UIAction { [weak self] _ in self?.save() }, for: .touchUpInside)",
        "saveButton.addAction(UIAction { _ in self.save() }, for: .touchUpInside)",
    ),
    (
        "update",
        "viewModel.onUpdate = { [unowned self] in self.render(self.viewModel.items) }",
        "viewModel.onUpdate = { self.render(self.viewModel.items) }",
    ),
)
_RC_SAFE_EXTRA = (
    'DispatchQueue.main.async { self.title = "Лента" }',
    "UIView.animate(withDuration: 0.3) { self.view.alpha = 1 }",
    "let titles = viewModel.items.map { self.format($0) }",
    "view.addSubview(saveButton)",
    "view.backgroundColor = .systemBackground",
)


def _gen_retain_cycle(rng: random.Random) -> Variant:
    cls = rng.choice(
        ("FeedViewController", "ProfileViewController", "CartViewController", "ChatViewController")
    )
    bug_cat = rng.randrange(len(_RC_PATTERNS))
    others = [p for i, p in enumerate(_RC_PATTERNS) if i != bug_cat]
    safe = [p[1] for p in rng.sample(others, rng.randint(2, 3))]
    safe += rng.sample(_RC_SAFE_EXTRA, rng.randint(2, 3))
    bug_stmt = _RC_PATTERNS[bug_cat][2]
    body = [*safe, bug_stmt]
    rng.shuffle(body)
    head = [
        "import UIKit",
        "import Combine",
        "",
        f"final class {cls}: UIViewController {{",
        "    private let viewModel = FeedViewModel()",
        "    private let saveButton = UIButton(type: .system)",
        "    private var cancellables = Set<AnyCancellable>()",
        "    private var timer: Timer?",
        "    var onFinish: (() -> Void)?",
        "",
        "    override func viewDidLoad() {",
        "        super.viewDidLoad()",
    ]
    tail = [
        "    }",
        "",
        "    private func render(_ items: [String]) { /* ... */ }",
        "    private func format(_ item: String) -> String { item.capitalized }",
        "    private func tick() { /* ... */ }",
        "    private func save() { /* ... */ }",
        "",
        '    deinit { print("deinit") }',
        "}",
    ]
    lines = head + ["        " + s for s in body] + tail
    bug_line = len(head) + body.index(bug_stmt) + 1
    return Variant(
        prompt=(
            f"После закрытия экрана {cls} никогда не освобождается: deinit не вызывается. "
            "FeedViewModel — класс с @Published var items: [String] и свойством "
            "var onUpdate: (() -> Void)?. В какой строке создаётся цикл сильных ссылок? "
            "Укажите номер строки."
        ),
        key=bug_line,
        code="\n".join(lines),
        extra={"language": "swift", "line_count": len(lines)},
        explanation=f"Строка {bug_line}: замыкание сильно захватывает self и хранится "
        "в объекте, которым владеет сам контроллер.",
    )


RETAIN_CYCLE = ItemTemplate(
    id="mobile.swift_retain_cycle",
    specialization="mobile",
    topic="swift",
    target_grade="senior",
    format=ItemFormat.FIND_BUG_LINE,
    generator=_gen_retain_cycle,
    a=1.4,
    b=1.2,
    title="Retain cycle в UIViewController",
    time_limit_s=210,
)

TEMPLATES = (OPTIONALS, VALUE_REFERENCE, DEFER_ORDER, CLOSURE_CAPTURE, RETAIN_CYCLE)
