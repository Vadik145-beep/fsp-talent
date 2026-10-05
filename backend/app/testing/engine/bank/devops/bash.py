"""DevOps — bash: «что выведет скрипт». Ответы считаются на Python, тесты сверяют с bash."""

from __future__ import annotations

import random
from collections import Counter

from ...templates import ItemFormat, ItemTemplate, Variant

_PROMPT = (
    "Что выведет скрипт bash? Запишите вывод через пробел (переводы строк можно заменить "
    "пробелами)."
)

# --------------------------------------------------------------------------- основы


def _gen_basic(rng: random.Random) -> Variant:
    kind = rng.randrange(6)
    out: list[int | str]
    if kind == 0:
        n, k = rng.randint(3, 9), rng.randint(2, 5)
        code = (
            f"total=0\nfor i in $(seq 1 {n}); do\n  total=$((total + i * {k}))\ndone\necho $total"
        )
        out = [k * n * (n + 1) // 2]
    elif kind == 1:
        name = rng.choice(("devops", "kubernetes", "nginx", "terraform", "ansible"))
        code = f'name="{name}"\ngreeting="Hello, $name"\necho ${{#name}} $greeting'
        out = [len(name), "Hello,", name]
    elif kind == 2:
        a, b = rng.randint(10, 99), rng.randint(2, 9)
        code = f"a={a}\nb={b}\necho $((a / b)) $((a % b))"
        out = [a // b, a % b]
    elif kind == 3:
        n, step = rng.randint(5, 15), rng.randint(2, 4)
        code = f"n={n}\nwhile [ $n -gt 0 ]; do\n  echo $n\n  n=$((n - {step}))\ndone"
        out = list(range(n, 0, -step))
    elif kind == 4:
        files = [
            f"{rng.choice(('app', 'db', 'web', 'api', 'cron'))}{i}."
            f"{rng.choice(('log', 'txt', 'log', 'gz'))}"
            for i in range(rng.randint(4, 6))
        ]
        ext = rng.choice(("log", "txt"))
        code = (
            f"count=0\nfor f in {' '.join(files)}; do\n  case $f in\n"
            f"    *.{ext}) count=$((count + 1)) ;;\n  esac\ndone\necho $count"
        )
        out = [sum(1 for f in files if f.endswith("." + ext))]
    else:
        x, y = rng.randint(1, 20), rng.randint(1, 20)
        code = (
            f"x={x}\ny={y}\nif [ $x -gt $y ]; then\n  echo $((x - y))\n"
            f"elif [ $x -eq $y ]; then\n  echo equal\nelse\n  echo $((y - x))\nfi"
        )
        out = [x - y if x > y else "equal" if x == y else y - x]
    return Variant(
        prompt=_PROMPT,
        key=" ".join(map(str, out)),
        code="#!/bin/bash\n" + code,
        extra={"language": "bash"},
        explanation="Вывод: " + " ".join(map(str, out)),
    )


BASH_BASIC = ItemTemplate(
    id="devops.bash_basic_output",
    specialization="devops",
    topic="bash",
    target_grade="intern",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_basic,
    a=1.1,
    b=-1.4,
    title="bash: переменные, арифметика, циклы",
    time_limit_s=120,
)

# --------------------------------------------------------------------------- перенаправления

_LABEL_SETS = (
    ("alpha", "beta", "gamma"),
    ("start", "warn", "done"),
    ("one", "two", "three"),
    ("ok", "fail", "end"),
    ("info", "error", "bye"),
)


def _gen_redirect(rng: random.Random) -> Variant:
    labels = list(rng.choice(_LABEL_SETS))
    rng.shuffle(labels)
    kinds = rng.choice(
        (["o", "e", "o"], ["e", "o", "o"], ["o", "o", "e"], ["o", "e", "e"], ["e", "o", "e"])
    )
    out_lines = [lab for lab, k in zip(labels, kinds, strict=True) if k == "o"]
    err_lines = [lab for lab, k in zip(labels, kinds, strict=True) if k == "e"]
    all_lines = labels
    fn = rng.choice(("f", "run", "job"))
    cmds = {
        "all_to_file": (f"{fn} > out.log 2>&1", [], ("out.log", "w", all_lines)),
        "wrong_order": (f"{fn} 2>&1 > out.log", err_lines, ("out.log", "w", out_lines)),
        "err_to_file": (f"{fn} 2> err.log", out_lines, ("err.log", "w", err_lines)),
        "out_null": (f"{fn} > /dev/null", err_lines, None),
        "err_null": (f"{fn} 2>/dev/null", out_lines, None),
        "append": (f"{fn} >> out.log", err_lines, ("out.log", "a", out_lines)),
        "amp": (f"{fn} &> out.log", [], ("out.log", "w", all_lines)),
        "pipe_all": (f"{fn} 2>&1 | wc -l", [str(len(all_lines))], None),
        "pipe_out": (f"{fn} | wc -l", [*err_lines, str(len(out_lines))], None),
    }
    while True:
        chosen = rng.sample(tuple(cmds), 2)
        files: dict[str, list[str]] = {}
        terminal: list[str] = []
        for c in chosen:
            _, term, fileop = cmds[c]
            terminal += term
            if fileop:
                name, mode, data = fileop
                files[name] = (files.get(name, []) if mode == "a" else []) + list(data)
        for name in sorted(files):
            terminal += files[name]
        if terminal:
            break
    body = [f"{fn}() {{"]
    for lab, k in zip(labels, kinds, strict=True):
        body.append(f"  echo {lab}" + (" >&2" if k == "e" else ""))
    body.append("}")
    body += [cmds[c][0] for c in chosen]
    body += [f"cat {name}" for name in sorted(files)]
    return Variant(
        prompt=(
            "Скрипт запускают в терминале в пустом каталоге. Что появится в терминале "
            "(и stdout, и stderr)? Запишите слова через пробел в порядке появления."
        ),
        key=" ".join(terminal),
        code="#!/bin/bash\n" + "\n".join(body),
        extra={"language": "bash"},
        explanation="Перенаправления применяются слева направо.",
    )


REDIRECT = ItemTemplate(
    id="devops.bash_redirection",
    specialization="devops",
    topic="bash",
    target_grade="middle",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_redirect,
    a=1.5,
    b=0.5,
    title="bash: stdout, stderr и перенаправления",
    time_limit_s=210,
)

# --------------------------------------------------------------------------- конвейеры по логу

_PATHS = ("/cart", "/login", "/orders", "/search", "/profile", "/health")
_METHODS = ("GET", "GET", "GET", "POST", "PUT", "DELETE")


def _gen_pipeline(rng: random.Random) -> Variant:
    kind = rng.randrange(7)
    while True:
        ips = [f"10.0.{rng.randint(0, 3)}.{rng.randint(1, 30)}" for _ in range(4)]
        rows = []
        for _ in range(rng.randint(8, 12)):
            rows.append(
                (
                    rng.choice(ips),
                    rng.choice(_METHODS),
                    rng.choice(_PATHS),
                    rng.choice((200, 200, 200, 201, 404, 500, 502, 304)),
                    rng.randint(1, 99) * 64,
                )
            )
        if kind == 0:
            cnt = Counter(r[0] for r in rows).most_common()
            if len(cnt) > 1 and cnt[0][1] == cnt[1][1]:
                continue
            cmd = "awk '{print $1}' access.log | sort | uniq -c | sort -rn | head -1"
            out = [str(cnt[0][1]), cnt[0][0]]
        elif kind == 1:
            paths = sorted({r[2] for r in rows if r[3] >= 500})
            if not paths:
                continue
            cmd = "awk '$4 >= 500 {print $3}' access.log | sort -u"
            out = paths
        elif kind == 2:
            code_ = rng.choice((404, 200, 500))
            cmd = f"grep -c ' {code_} ' access.log"
            out = [str(sum(1 for r in rows if r[3] == code_))]
        elif kind == 3:
            cmd = "awk '{s += $5} END {print s}' access.log"
            out = [str(sum(r[4] for r in rows))]
        elif kind == 4:
            cmd = "cut -d' ' -f2 access.log | sort | uniq | wc -l"
            out = [str(len({r[1] for r in rows}))]
        elif kind == 5:
            m = rng.choice(("POST", "GET"))
            cmd = f"awk '$2 == \"{m}\"' access.log | wc -l"
            out = [str(sum(1 for r in rows if r[1] == m))]
        else:
            sizes = [r[4] for r in rows]
            if sizes.count(max(sizes)) > 1:
                continue
            cmd = "sort -t' ' -k5 -n access.log | tail -1 | cut -d' ' -f3"
            out = [max(rows, key=lambda r: r[4])[2]]
        break
    log = "\n".join(" ".join(map(str, r)) for r in rows)
    return Variant(
        prompt=(
            "Файл access.log (поля: IP, метод, путь, код ответа, байты) и команда — ниже. "
            "Что выведет последняя команда? Запишите вывод через пробел."
        ),
        key=" ".join(out),
        code=f"$ cat access.log\n{log}\n$ {cmd}",
        extra={"language": "bash"},
        explanation="Вывод: " + " ".join(out),
    )


TEXT_PIPELINE = ItemTemplate(
    id="devops.text_pipeline",
    specialization="devops",
    topic="bash",
    target_grade="middle",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_pipeline,
    a=1.4,
    b=0.3,
    title="Конвейеры grep, awk, sort, uniq",
    time_limit_s=210,
)

# --------------------------------------------------------------------------- кавычки и разбиение


def _gen_quoting(rng: random.Random) -> Variant:
    fn = rng.choice(("count", "nargs", "argc"))
    words = rng.sample(["red", "green", "blue", "cyan", "lime", "gray", "navy"], rng.randint(2, 4))
    sep = [rng.choice((" ", "  ")) for _ in words[1:]]
    v = words[0] + "".join(s + w for s, w in zip(sep, words[1:], strict=True))
    pos = [rng.choice(("a b", "x y z", "p")), rng.choice(("c", "d e"))]
    arr = [rng.choice(("one two", "q")), "r", rng.choice(("s t", "u"))][: rng.randint(2, 3)]

    def nwords(items: list[str]) -> int:
        return sum(len(i.split()) for i in items)

    pool = [
        (f"{fn} $v", len(words)),
        (f'{fn} "$v"', 1),
        (f'{fn} "$@"', len(pos)),
        (f"{fn} $@", nwords(pos)),
        (f'{fn} "$*"', 1),
        (f'{fn} "${{arr[@]}}"', len(arr)),
        (f"{fn} ${{arr[@]}}", nwords(arr)),
        (f'{fn} "${{arr[*]}}"', 1),
        (f"{fn} $empty", 0),
        (f'{fn} "$empty"', 1),
        (f'{fn} $v "$empty"', len(words) + 1),
        ("echo ${#arr[@]}", len(arr)),
    ]
    chosen = rng.sample(pool, rng.randint(3, 4))
    q = '" "'.join(arr)
    head = [
        f"{fn}() {{ echo $#; }}",
        f'v="{v}"',
        f'arr=("{q}")',
        'empty=""',
        "set -- " + " ".join(f'"{p}"' for p in pos),
    ]
    return Variant(
        prompt=_PROMPT,
        key=" ".join(str(r) for _, r in chosen),
        code="#!/bin/bash\n" + "\n".join(head + [c for c, _ in chosen]),
        extra={"language": "bash"},
        explanation='Без кавычек переменная разбивается на слова; "$@" сохраняет аргументы.',
    )


QUOTING = ItemTemplate(
    id="devops.bash_quoting",
    specialization="devops",
    topic="bash",
    target_grade="senior",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_quoting,
    a=1.5,
    b=1.3,
    title="bash: кавычки, $@ и разбиение на слова",
    time_limit_s=240,
)

TEMPLATES = [BASH_BASIC, REDIRECT, TEXT_PIPELINE, QUOTING]
