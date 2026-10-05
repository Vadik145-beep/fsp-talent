"""Frontend / TypeScript: строка с ошибкой компиляции в strict-режиме, вывод условных типов.

Тест, если во временной папке установлен typescript, компилирует варианты настоящим tsc:
ошибка ровно одна и стоит в строке-ключе; тип R совпадает с верным вариантом ответа.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ...templates import ItemFormat, ItemTemplate, Variant, make_single_choice

# --------------------------------------------------------------------------- ошибка компиляции


@dataclass
class _TsProgram:
    desc: str
    types: list[str]
    sig: str
    body: list[str]  # строки тела (с отступом 2)
    tail: list[str] = field(default_factory=list)  # код после функции
    bug: tuple[str, int] = ("body", 0)  # где ошибка: body | tail | sig, индекс


def _ts_programs(rng: random.Random) -> list[_TsProgram]:
    fn = rng.choice(("load", "build", "resolve", "compute", "prepare", "format"))
    ent = rng.choice(("User", "Client", "Member", "Author"))
    progs: list[_TsProgram] = []

    progs.append(
        _TsProgram(
            f"возвращает имя по id из списка {ent}[]",
            [f"interface {ent} {{", "  id: number;", "  name: string;", "}"],
            f"function {fn}Name(list: {ent}[], id: number): string {{",
            ["  const found = list.find((x) => x.id === id);", "  return found.name;"],
            bug=("body", 1),
        )
    )

    wrong_circle = rng.random() < 0.5
    progs.append(
        _TsProgram(
            "считает площадь фигуры",
            [
                "interface Circle { kind: 'circle'; radius: number }",
                "interface Square { kind: 'square'; side: number }",
                "type Shape = Circle | Square;",
            ],
            "function area(s: Shape): number {",
            [
                "  if (s.kind === 'circle') {",
                "    return Math.PI * s.side ** 2;"
                if wrong_circle
                else "    return Math.PI * s.radius ** 2;",
                "  }",
                "  return s.side * s.side;" if wrong_circle else "  return s.radius * s.radius;",
            ],
            bug=("body", 1 if wrong_circle else 3),
        )
    )

    ro_port = rng.random() < 0.5
    progs.append(
        _TsProgram(
            "подставляет значения по умолчанию в конфиг",
            [
                "interface Config {",
                "  readonly port: number;" if ro_port else "  port: number;",
                "  host: string;" if ro_port else "  readonly host: string;",
                "}",
            ],
            f"function {fn}Config(cfg: Config): Config {{",
            [
                "  cfg.host = cfg.host || 'localhost';",
                f"  cfg.port = cfg.port || {rng.choice((3000, 8080, 8000))};",
                "  return cfg;",
            ],
            bug=("body", 1 if ro_port else 0),
        )
    )

    price = rng.randint(10, 999)
    progs.append(
        _TsProgram(
            "создаёт карточку товара",
            ["interface Product {", "  id: number;", "  title: string;", "  price: number;", "}"],
            f"function {fn}Product(title: string): Product {{",
            [
                f"  const base = {{ id: {rng.randint(1, 99)}, title, price: {price} }};",
                "  const item: Product = { id: base.id, title: base.title };",
                "  return { ...item, price: base.price };",
            ],
            bug=("body", 1),
        )
    )

    cur = rng.choice(("RUB", "USD", "EUR"))
    bad_first = rng.random() < 0.5
    calls = [
        f"const a = formatPrice({rng.randint(1, 99)}, '{cur}');",
        f"const b = formatPrice('{rng.randint(1, 99)}', '{cur}');",
    ]
    progs.append(
        _TsProgram(
            "форматирует цену",
            [],
            "function formatPrice(value: number, currency: string): string {",
            ["  return value.toFixed(2) + ' ' + currency;"],
            tail=calls[::-1] if bad_first else calls,
            bug=("tail", 0 if bad_first else 1),
        )
    )

    progs.append(
        _TsProgram(
            "считает элементы в JSON-ответе",
            [],
            f"function {fn}Count(text: string): number {{",
            ["  const data: unknown = JSON.parse(text);", "  return data.items.length;"],
            bug=("body", 1),
        )
    )

    bad_status = rng.choice(("failed", "error", "ready"))
    progs.append(
        _TsProgram(
            "переключает статус загрузки",
            ["type Status = 'idle' | 'loading' | 'done';"],
            f"function {fn}Status(ok: boolean): Status {{",
            [
                "  let status: Status = 'idle';",
                "  status = 'loading';",
                f"  status = ok ? 'done' : '{bad_status}';",
                "  return status;",
            ],
            bug=("body", 2),
        )
    )

    progs.append(
        _TsProgram(
            "ищет позицию строки в массиве",
            [],
            f"function {fn}Index(xs: string[], x: string): number {{",
            ["  const i = xs.indexOf(x);", "  return i >= 0 ? i : null;"],
            bug=("body", 1),
        )
    )

    k = rng.randint(2, 9)
    progs.append(
        _TsProgram(
            "умножает число",
            [],
            f"function {fn}Times(n) {{",
            [f"  const factor = {k};", "  return n * factor;"],
            tail=[f"const r = {fn}Times({rng.randint(1, 9)});"],
            bug=("sig", 0),
        )
    )

    progs.append(
        _TsProgram(
            "выполняет задачу и вызывает колбэк",
            [],
            f"function {fn}Task(job: () => number, done?: (n: number) => void): number {{",
            ["  const result = job();", "  done(result);", "  return result;"],
            bug=("body", 1),
        )
    )

    opt = rng.choice(("retry", "verbose", "cache"))
    progs.append(
        _TsProgram(
            "собирает опции запроса",
            ["interface Options {", "  timeout: number;", "  retries?: number;", "}"],
            f"function {fn}Options(ms: number): Options {{",
            [
                f"  const opts: Options = {{ timeout: ms, {opt}: true }};",
                "  return opts;",
            ],
            bug=("body", 0),
        )
    )
    return progs


_TOP_FILLERS = (
    "const VERSION = '1.{n}.0';",
    "// ---- вспомогательные функции ----",
    "const DEBUG = false;",
)
_BODY_FILLERS = (
    "  const startedAt = Date.now();",
    "  // TODO: логирование",
    "  const attempt = {n};",
)


def _gen_ts_bug(rng: random.Random) -> Variant:
    prog = rng.choice(_ts_programs(rng))
    n = rng.randint(1, 9)
    top = [f.format(n=n) for f in rng.sample(_TOP_FILLERS, rng.choice((0, 1, 1, 2)))]
    body_f = [f.format(n=n) for f in rng.sample(_BODY_FILLERS, rng.choice((0, 1, 1, 2)))]
    lines: list[str] = [*prog.types]
    if prog.types:
        lines.append("")
    lines += top
    if top:
        lines.append("")
    sig_line = len(lines)
    lines.append(prog.sig)
    body_start = len(lines)
    lines += body_f
    lines += prog.body
    lines.append("}")
    tail_start = len(lines) + (1 if prog.tail else 0)
    if prog.tail:
        lines.append("")
        lines += prog.tail
    where, idx = prog.bug
    if where == "sig":
        bug = sig_line
    elif where == "body":
        bug = body_start + len(body_f) + idx
    else:
        bug = tail_start + idx
    return Variant(
        prompt=(
            f'Код {prog.desc}. Компиляция идёт с "strict": true (TypeScript 5). В какой '
            "строке компилятор выдаст ошибку? Укажите номер строки."
        ),
        key=bug + 1,
        code="\n".join(lines),
        extra={"language": "typescript", "line_count": len(lines)},
        explanation=f"Ошибка в строке {bug + 1}: {lines[bug].strip()}",
    )


TS_COMPILE_ERROR = ItemTemplate(
    id="frontend.ts_compile_error",
    specialization="frontend",
    topic="typescript",
    target_grade="middle",
    format=ItemFormat.FIND_BUG_LINE,
    generator=_gen_ts_bug,
    a=1.3,
    b=0.5,
    title="Найди строку с ошибкой компиляции TypeScript",
    time_limit_s=210,
)

# --------------------------------------------------------------------------- условные типы

_BASE = ("string", "number", "bigint", "Date", "RegExp")
_WORDS = ("red", "green", "blue", "cat", "dog", "home", "work", "draft", "sent", "read")


def _q(words: list[str]) -> str:
    return " | ".join(f'"{w}"' for w in words)


def _cond_case(rng: random.Random) -> tuple[list[str], str, list[str]]:
    """(строки кода, верный тип, дистракторы)."""
    a, b = rng.sample(_BASE, 2)
    kind = rng.randrange(12)
    if kind == 0:
        return (
            ["type ToArray<T> = T extends unknown ? T[] : never;", f"type R = ToArray<{a} | {b}>;"],
            f"{a}[] | {b}[]",
            [f"({a} | {b})[]", "never", "unknown[]"],
        )
    if kind == 1:
        return (
            [
                "type ToArray<T> = [T] extends [unknown] ? T[] : never;",
                f"type R = ToArray<{a} | {b}>;",
            ],
            f"({a} | {b})[]",
            [f"{a}[] | {b}[]", "never", f"[{a} | {b}]"],
        )
    if kind == 2:
        return (
            [f"type Is<T> = T extends {a} ? 'yes' : 'no';", "type R = Is<never>;"],
            "never",
            ['"yes"', '"no"', '"yes" | "no"'],
        )
    if kind == 3:
        lit = rng.randint(1, 99)
        w = rng.choice(_WORDS)
        return (
            [
                "type IsText<T> = T extends string ? true : false;",
                f"type R = IsText<'{w}' | {lit}>;",
            ],
            "boolean",
            ["true", "false", "never"],
        )
    if kind == 4:
        ws = rng.sample(_WORDS, 4)
        return (
            [f"type R = Exclude<{_q(ws[:3])}, {_q([ws[0], ws[3]])}>;"],
            _q(ws[1:3]),
            [_q([ws[0], ws[3]]), _q(ws[1:4]), "never"],
        )
    if kind == 5:
        return (
            [f"type R = Extract<{a} | {b} | (() => void), Function>;"],
            "() => void",
            [f"{a} | {b}", "never", "Function"],
        )
    if kind == 6:
        return (
            ["type Elem<T> = T extends (infer U)[] ? U : T;", f"type R = Elem<{a}[][]>;"],
            f"{a}[]",
            [a, f"{a}[][]", "never"],
        )
    if kind == 7:
        return (
            [
                "type Unwrap<T> = T extends Promise<infer U> ? U : T;",
                f"type R = Unwrap<Promise<Promise<{a}>>>;",
            ],
            f"Promise<{a}>",
            [a, f"Promise<Promise<{a}>>", "never"],
        )
    if kind == 8:
        empty = rng.random() < 0.5
        arg = "[]" if empty else f"[{a}, {b}]"
        return (
            [
                "type First<T> = T extends [infer H, ...unknown[]] ? H : never;",
                f"type R = First<{arg}>;",
            ],
            "never" if empty else a,
            ([a, "undefined", "unknown"] if empty else [b, f"{a} | {b}", "never"]),
        )
    if kind == 9:
        k1, k2 = rng.sample(("id", "name", "email", "age", "role", "city"), 2)
        return (
            [f"interface Item {{ {k1}: {a}; {k2}: {b} }}", "type R = keyof Item;"],
            _q([k1, k2]),
            [f"{a} | {b}", "string", f'"{k1}"'],
        )
    if kind == 10:
        k1, k2, k3 = rng.sample(("id", "name", "email", "age", "role", "city"), 3)
        return (
            [
                f"interface Item {{ {k1}: {a}; {k2}: {b}; {k3}: boolean }}",
                f"type R = Item['{k1}' | '{k2}'];",
            ],
            f"{a} | {b}",
            [_q([k1, k2]), f"{a} | {b} | boolean", "never"],
        )
    fn = rng.choice(("pick", "lookup", "measure", "probe"))
    return (
        [
            f"function {fn}(items: {a}[], flag: boolean) {{",
            "  return flag ? items.length : undefined;",
            "}",
            f"type R = ReturnType<typeof {fn}>;",
        ],
        "number | undefined",
        ["number", f"{a}[] | undefined", "undefined"],
    )


def _gen_conditional(rng: random.Random) -> Variant:
    code, correct, distractors = _cond_case(rng)
    return make_single_choice(
        rng,
        "Чему равен тип R (TypeScript 5, strict)?",
        correct,
        distractors,
        code="\n".join(code),
        extra={"language": "typescript"},
        explanation=(
            "Условный тип над голым параметром распределяется по объединению (never → never); "
            "обёртка [T] отключает распределение; infer вытаскивает один уровень."
        ),
    )


TS_CONDITIONAL = ItemTemplate(
    id="frontend.ts_conditional_types",
    specialization="frontend",
    topic="typescript",
    target_grade="senior",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_conditional,
    a=1.4,
    b=1.7,
    title="Условные типы, infer и распределение по объединению",
    time_limit_s=210,
)

TEMPLATES = (TS_COMPILE_ERROR, TS_CONDITIONAL)
