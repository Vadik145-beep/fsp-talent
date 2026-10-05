"""Backend · алгоритмы и структуры данных: бинарный поиск, выбор структуры, рост времени."""

from __future__ import annotations

import random
from typing import Any

from ...templates import ItemFormat, ItemTemplate, NumericKey, Variant, make_single_choice

# ------------------------------------------------------------ бинарный поиск


def _big(n: int) -> str:
    """1000000 → «1 000 000» (неразрывные пробелы)."""
    return f"{n:,}".replace(",", " ")


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def binary_search_steps(arr: list[int], target: int) -> int:
    """Число итераций цикла классического бинарного поиска (как в коде задачи)."""
    lo, hi = 0, len(arr) - 1
    steps = 0
    while lo <= hi:
        steps += 1
        mid = (lo + hi) // 2
        if arr[mid] == target:
            return steps
        if arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return steps


_BS_NAMES = (
    ("find", "lo", "hi", "mid", "steps"),
    ("search", "left", "right", "middle", "count"),
    ("bsearch", "low", "high", "m", "iters"),
    ("locate", "a", "b", "c", "n"),
)


def _make_binary_search(rng: random.Random) -> tuple[Variant, dict[str, Any]]:
    fn, lo, hi, mid, cnt = rng.choice(_BS_NAMES)
    size = rng.randint(7, 16)
    start = rng.randint(1, 30)
    arr = sorted(rng.sample(range(start, start + size * 6), size))
    if rng.random() < 0.65:
        target = rng.choice(arr)
    else:
        candidates = [v for v in range(arr[0] - 3, arr[-1] + 4) if v not in arr]
        target = rng.choice(candidates)
    mid_expr = f"({lo} + {hi}) // 2" if rng.random() < 0.6 else f"{lo} + ({hi} - {lo}) // 2"
    code = "\n".join(
        [
            f"def {fn}(arr, target):",
            f"    {lo}, {hi} = 0, len(arr) - 1",
            f"    {cnt} = 0",
            f"    while {lo} <= {hi}:",
            f"        {cnt} += 1",
            f"        {mid} = {mid_expr}",
            f"        if arr[{mid}] == target:",
            f"            return {cnt}",
            f"        if arr[{mid}] < target:",
            f"            {lo} = {mid} + 1",
            "        else:",
            f"            {hi} = {mid} - 1",
            f"    return {cnt}",
            "",
            "",
            f"print({fn}({arr}, {target}))",
        ]
    )
    answer = binary_search_steps(arr, target)
    variant = Variant(
        prompt="Какое число выведет программа (сколько итераций сделает цикл while)?",
        key=NumericKey(answer, 0),
        code=code,
        extra={"language": "python", "answer_type": "integer"},
        explanation=f"Трассировка бинарного поиска: {answer} итераций.",
    )
    return variant, {"arr": arr, "target": target}


BINARY_SEARCH = ItemTemplate(
    id="backend.binary_search_steps",
    specialization="backend",
    topic="algorithms",
    target_grade="intern",
    format=ItemFormat.NUMERIC,
    generator=lambda rng: _make_binary_search(rng)[0],
    a=1.1,
    b=-1.4,
    title="Сколько шагов сделает бинарный поиск",
    time_limit_s=180,
)

# ------------------------------------------------------------ выбор структуры данных

_SET = "set: add() и проверка x in s"
_LIST_SCAN = "list: append() и проверка x in lst"
_DEQUE_FIFO = "collections.deque: append() и popleft()"
_LIST_POP0 = "list: append() и pop(0)"
_LIST_STACK = "list: append() и pop()"
_HEAP = "heapq: heappush() и heappop()"
_LIST_MIN = "list: append(), затем min() и remove()"
_DICT = "dict: d[ключ] = значение и d[ключ]"
_LIST_PAIRS = "list пар (ключ, значение) и поиск перебором"
_COUNTER = "collections.Counter: c[x] += 1"
_LIST_COUNT = "list: append() каждого значения, затем lst.count(x)"


def _ds_scenarios(rng: random.Random) -> list[tuple[str, str, list[str]]]:
    n = rng.choice((50_000, 200_000, 1_000_000, 5_000_000))
    k = rng.choice((100, 500, 1000, 5000))
    ent = rng.choice(("заказов", "платежей", "сообщений", "событий", "запросов"))
    who = rng.choice(("сервис уведомлений", "воркер очереди", "API-шлюз", "сервис биллинга"))
    return [
        (
            (
                f"{_cap(who)} получает поток id {ent} (всего до {_big(n)} штук) и для каждого id "
                "проверяет, не обрабатывался ли он уже."
            ),
            _SET,
            [_LIST_SCAN, _DEQUE_FIFO, _HEAP, _LIST_PAIRS],
        ),
        (
            (
                f"{_cap(who)} складывает задачи в очередь и обрабатывает их строго в порядке "
                f"поступления; в очереди бывает до {_big(n)} задач."
            ),
            _DEQUE_FIFO,
            [_LIST_POP0, _LIST_STACK, _SET],
        ),
        (
            (
                f"{_cap(who)} хранит до {_big(n)} задач с дедлайнами; задачи постоянно "
                "добавляются, и каждый раз нужно забрать задачу с самым ранним дедлайном."
            ),
            _HEAP,
            [_LIST_MIN, _DEQUE_FIFO, _LIST_STACK, _SET],
        ),
        (
            (
                f"{_cap(who)} по логину пользователя достаёт его профиль; "
                f"пользователей до {_big(n)}."
            ),
            _DICT,
            [_LIST_PAIRS, _SET, _HEAP, _DEQUE_FIFO],
        ),
        (
            (
                f"Редактор хранит до {k} последних действий пользователя для отмены (undo): "
                "отменяется всегда самое последнее действие."
            ),
            _LIST_STACK,
            [_DEQUE_FIFO, _LIST_POP0, _HEAP, _SET],
        ),
        (
            (
                f"{_cap(who)} считает, сколько раз встретился каждый код ответа в логе "
                f"из {_big(n)} строк, и в конце выводит счётчики."
            ),
            _COUNTER,
            [_LIST_COUNT, _SET, _HEAP, _DEQUE_FIFO],
        ),
    ]


def _gen_ds_choice(rng: random.Random) -> Variant:
    scenario, correct, distractors = rng.choice(_ds_scenarios(rng))
    return make_single_choice(
        rng,
        f"{scenario}\nКакую структуру данных Python выбрать, чтобы каждая операция выполнялась "
        "в среднем за O(1) или O(log n)?",
        correct,
        distractors,
        extra={"language": "python"},
        explanation=f"Подходит: {correct}.",
    )


DS_CHOICE = ItemTemplate(
    id="backend.ds_choice",
    specialization="backend",
    topic="algorithms",
    target_grade="intern",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_ds_choice,
    a=1.0,
    b=-1.6,
    title="Какую структуру данных выбрать",
    time_limit_s=120,
)

# ------------------------------------------------------------ рост времени по O(f(n))


def _make_scaling(rng: random.Random) -> tuple[Variant, dict[str, Any]]:
    kind = rng.choice(("n", "n2", "n3", "nlogn", "logn", "2n"))
    t = rng.choice((2, 3, 4, 5, 6, 8, 10, 12, 15, 20))
    algo = {
        "n": ("O(n)", "один проход по массиву"),
        "n2": ("O(n²)", "сравнение всех пар элементов"),
        "n3": ("O(n³)", "тройной вложенный цикл по n"),
        "nlogn": ("O(n log n)", "сортировка слиянием"),
        "logn": ("O(log n)", "бинарный поиск"),
        "2n": ("O(2ⁿ)", "перебор всех подмножеств"),
    }[kind]
    if kind in ("n", "n2", "n3"):
        n1 = rng.choice((1000, 2000, 5000, 10_000, 20_000))
        mult = rng.choice((2, 3, 4, 5, 10))
        n2 = n1 * mult
        power = {"n": 1, "n2": 2, "n3": 3}[kind]
        ratio = mult**power
    elif kind == "nlogn":
        a, c = rng.choice(((10, 15), (10, 20), (8, 12), (8, 16), (16, 20), (12, 18)))
        n1, n2 = 2**a, 2**c
        ratio_f = 2 ** (c - a) * c / a
        assert ratio_f == int(ratio_f)
        ratio = int(ratio_f)
    elif kind == "logn":
        a = rng.choice((8, 10, 12, 16))
        c = a * rng.choice((2, 3, 4))
        n1, n2 = 2**a, 2**c
        ratio = c // a
    else:
        n1 = rng.choice((20, 24, 25, 30))
        d = rng.choice((1, 2, 3, 4, 5))
        n2 = n1 + d
        ratio = 2**d
    answer = t * ratio
    label, what = algo
    prompt = (
        f"Функция ({what}) имеет сложность {label}. На входе из n = {_big(n1)} элементов она "
        f"работает {t} мс. Сколько миллисекунд она будет работать при n = {_big(n2)}? "
        "Считайте, что время строго пропорционально функции сложности; ответ — целое число."
    )
    variant = Variant(
        prompt=prompt,
        key=NumericKey(answer, 0),
        extra={"answer_type": "integer", "unit": "мс"},
        explanation=f"Отношение f(n2)/f(n1) = {ratio}, ответ {t} × {ratio} = {answer}.",
    )
    return variant, {"kind": kind, "n1": n1, "n2": n2, "t": t}


COMPLEXITY_SCALING = ItemTemplate(
    id="backend.complexity_scaling",
    specialization="backend",
    topic="algorithms",
    target_grade="junior",
    format=ItemFormat.NUMERIC,
    generator=lambda rng: _make_scaling(rng)[0],
    a=1.2,
    b=-0.6,
    title="Как вырастет время работы алгоритма",
    time_limit_s=150,
)

TEMPLATES = [BINARY_SEARCH, DS_CHOICE, COMPLEXITY_SCALING]
