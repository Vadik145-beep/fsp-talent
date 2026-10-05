"""QA — техники тест-дизайна: классы эквивалентности, таблица решений, попарное, состояния."""

from __future__ import annotations

import random
from typing import Any

from ...templates import (
    ItemFormat,
    ItemTemplate,
    NumericKey,
    Variant,
    make_multi_choice,
    make_single_choice,
)
from ._common import table

# --------------------------------------------------------------------------- классы эквивалентности

_EQ_FIELDS = (
    ("Сумма заказа", "₽", ("скидки нет", "скидка 5%", "скидка 10%"), (1,), (500, 3000), 100),
    (
        "Возраст пассажира",
        "лет",
        ("детский тариф", "взрослый тариф", "льготный тариф"),
        (0,),
        (7, 14),
        1,
    ),
    ("Вес посылки", "г", ("пакет", "посылка", "крупногабаритный груз"), (1,), (500, 2000), 100),
    (
        "Стаж сотрудника",
        "мес.",
        ("испытательный срок", "базовый отпуск", "доп. отпуск"),
        (0,),
        (2, 6),
        1,
    ),
)


def eq_class(v: int, b0: int, b1: int, b2: int) -> int:
    """Номер класса: -1 — ошибка ввода, 0, 1, 2 — допустимые диапазоны."""
    if v < b0:
        return -1
    if v < b1:
        return 0
    if v < b2:
        return 1
    return 2


def _gen_equivalence(rng: random.Random) -> Variant:
    field, unit, labels, (b0,), (lo, hi), step = rng.choice(_EQ_FIELDS)
    b1 = rng.randrange(lo, hi + 1, step)
    b2 = b1 + rng.randrange(max(step * 3, b1 // 2), max(step * 4, b1 * 3), step)
    cls = rng.choice((-1, 0, 1, 1, 2))
    spans = {-1: (b0 - 50, b0 - 1), 0: (b0, b1 - 1), 1: (b1, b2 - 1), 2: (b2, b2 * 3)}
    a, b = spans[cls]
    edge = rng.random() < 0.5
    x = b if (edge and cls in (-1, 0, 1)) else rng.randint(a, b)
    y = rng.randint(a, b)
    if cls == 1 and edge:
        x, y = b1, rng.randint(b1 + 1, b2 - 1)
    if x == y:
        y = a if x != a else b
    correct = f"{min(x, y)} и {max(x, y)}"
    crossing = [
        (b1 - 1, b1),
        (b2 - 1, b2),
        (b0 - 1, b0),
        (rng.randint(b0, b1 - 1), rng.randint(b1, b2 - 1)),
        (rng.randint(b1, b2 - 1), rng.randint(b2, b2 * 2)),
        (b1, b2),
    ]
    distractors = [
        f"{min(p)} и {max(p)}"
        for p in crossing
        if p[0] != p[1] and eq_class(p[0], b0, b1, b2) != eq_class(p[1], b0, b1, b2)
    ]
    return make_single_choice(
        rng,
        f"Поле «{field}» принимает целые числа. От {b0} до {b1 - 1} {unit} — {labels[0]}; "
        f"от {b1} до {b2 - 1} — {labels[1]}; от {b2} и больше — {labels[2]}; "
        f"меньше {b0} — ошибка ввода. Какие два значения относятся к одному классу "
        "эквивалентности?",
        correct,
        distractors,
        explanation=f"Классы: <{b0} | {b0}..{b1 - 1} | {b1}..{b2 - 1} | ≥{b2}.",
    )


EQUIVALENCE = ItemTemplate(
    id="qa.equivalence_classes",
    specialization="qa",
    topic="test_design",
    target_grade="intern",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_equivalence,
    a=1.2,
    b=-1.5,
    title="Классы эквивалентности",
    time_limit_s=120,
)

# --------------------------------------------------------------------------- таблица решений


def _decision_domains(rng: random.Random) -> list[dict[str, Any]]:
    limit = rng.choice((2000, 3000, 5000, 10000))
    weight = rng.choice((5, 10, 20))
    return [
        {
            "title": "Скидка в интернет-магазине",
            "conds": (
                "Покупатель — сотрудник компании",
                f"Сумма заказа ≥ {limit} ₽",
                "Есть карта лояльности",
            ),
            "actions": ("скидка 30%", "скидка 10%", "скидка 5%", "без скидки"),
            "extra": "скидка 15%",
            "case": lambda c: (
                f"{'Сотрудник' if c[0] else 'Не сотрудник'}, сумма заказа "
                f"{limit + rng.randint(1, 900) * 10 if c[1] else limit - rng.randint(1, 90) * 10}"
                f" ₽, карта лояльности {'есть' if c[2] else 'нет'}."
            ),
        },
        {
            "title": "Стоимость доставки",
            "conds": (f"Сумма заказа ≥ {limit} ₽", f"Вес > {weight} кг", "Доставка за город"),
            "actions": ("бесплатно", "900 ₽", "500 ₽", "300 ₽"),
            "extra": "1400 ₽",
            "case": lambda c: (
                f"Сумма {limit + rng.randint(1, 50) * 10 if c[0] else limit - rng.randint(1, 50) * 10}"  # noqa: E501
                f" ₽, вес {weight + rng.randint(1, 9) if c[1] else rng.randint(1, weight)} кг, "
                f"адрес {'в пригороде' if c[2] else 'в черте города'}."
            ),
        },
        {
            "title": "Доступ к разделу отчётов",
            "conds": ("Роль — администратор", "Оплачен тариф Pro", "Email подтверждён"),
            "actions": ("полный доступ", "расширенный доступ", "базовый доступ", "только просмотр"),
            "extra": "доступ запрещён",
            "case": lambda c: (
                f"Роль — {'администратор' if c[0] else rng.choice(('менеджер', 'аналитик'))}, "
                f"тариф {'Pro' if c[1] else rng.choice(('Free', 'Basic'))}, "
                f"email {'подтверждён' if c[2] else 'не подтверждён'}."
            ),
        },
    ]


def _gen_decision(rng: random.Random) -> Variant:
    d = rng.choice(_decision_domains(rng))
    c = (rng.random() < 0.3, rng.random() < 0.5, rng.random() < 0.6)
    rule = 0 if c[0] else 1 if c[1] else 2 if c[2] else 3
    rows = [
        [d["conds"][0], "да", "нет", "нет", "нет"],
        [d["conds"][1], "—", "да", "нет", "нет"],
        [d["conds"][2], "—", "—", "да", "нет"],
        ["Результат", *d["actions"]],
    ]
    code = table(["Условие", "R1", "R2", "R3", "R4"], rows) + "\n«—» — значение не важно."
    correct = d["actions"][rule]
    return make_single_choice(
        rng,
        f"{d['title']} задаётся таблицей решений. Какой результат ожидается в тесте?\n"
        f"Входные данные: {d['case'](c)}",
        correct,
        [a for a in d["actions"] if a != correct] + [d["extra"]],
        code=code,
        explanation=f"Срабатывает правило R{rule + 1}.",
    )


DECISION_TABLE = ItemTemplate(
    id="qa.decision_table",
    specialization="qa",
    topic="test_design",
    target_grade="junior",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_decision,
    a=1.2,
    b=-0.7,
    title="Таблица решений",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- попарное тестирование

_PARAMS = (
    ("Браузер", ("Chrome", "Firefox", "Safari", "Edge", "Opera")),
    ("ОС", ("Windows", "macOS", "Ubuntu", "Android", "iOS")),
    ("Язык интерфейса", ("ru", "en", "kk", "uz")),
    ("Способ оплаты", ("карта", "СБП", "наличные", "бонусы", "рассрочка")),
    ("Доставка", ("курьер", "самовывоз", "пункт выдачи", "почта")),
    ("Тип клиента", ("новый", "постоянный", "VIP")),
)


def _gen_pairwise(rng: random.Random) -> Variant:
    params = rng.sample(_PARAMS, 3)
    chosen = []
    for name, values in params:
        k = rng.randint(2, len(values))
        chosen.append((name, values[:k]))
    sizes = sorted((len(v) for _, v in chosen), reverse=True)
    q = rng.choice(("min_tests", "min_tests", "pairs"))
    if q == "min_tests":
        value = sizes[0] * sizes[1]
        ask = (
            "Какое минимальное число тестов нужно, чтобы каждая пара значений любых двух "
            "параметров встретилась хотя бы в одном тесте (попарное тестирование)?"
        )
    else:
        a, b, c = sizes
        value = a * b + a * c + b * c
        ask = (
            "Сколько всего разных пар значений (для каждой пары параметров) нужно покрыть "
            "при попарном тестировании?"
        )
    listing = "\n".join(f"{name}: {', '.join(values)}" for name, values in chosen)
    return Variant(
        prompt=f"Форма заказа тестируется по трём независимым параметрам.\n{ask}",
        key=NumericKey(value, 0),
        code=listing,
        extra={"answer_type": "integer"},
        explanation=f"Размеры {sizes}: ответ {value}.",
    )


PAIRWISE = ItemTemplate(
    id="qa.pairwise_count",
    specialization="qa",
    topic="test_design",
    target_grade="middle",
    format=ItemFormat.NUMERIC,
    generator=_gen_pairwise,
    a=1.3,
    b=0.6,
    title="Попарное тестирование: сколько тестов",
    time_limit_s=180,
)

# --------------------------------------------------------------------------- переходы состояний

_MACHINES = (
    (
        "Заказ",
        "Новый",
        [
            ("оплатить", "Новый", "Оплачен"),
            ("собрать", "Оплачен", "Собран"),
            ("отправить", "Собран", "Отправлен"),
            ("доставить", "Отправлен", "Доставлен"),
            ("отменить", "Новый", "Отменён"),
            ("отменить", "Оплачен", "Отменён"),
            ("вернуть", "Доставлен", "Возврат"),
        ],
        [("отменить", "Собран", "Отменён")],
    ),
    (
        "Заявка в поддержку",
        "Открыта",
        [
            ("взять в работу", "Открыта", "В работе"),
            ("запросить данные", "В работе", "Ждёт клиента"),
            ("ответить", "Ждёт клиента", "В работе"),
            ("решить", "В работе", "Решена"),
            ("закрыть", "Решена", "Закрыта"),
            ("переоткрыть", "Решена", "В работе"),
        ],
        [("закрыть", "Открыта", "Закрыта")],
    ),
    (
        "Документ",
        "Черновик",
        [
            ("отправить на согласование", "Черновик", "На согласовании"),
            ("согласовать", "На согласовании", "Согласован"),
            ("вернуть на доработку", "На согласовании", "Черновик"),
            ("подписать", "Согласован", "Подписан"),
            ("архивировать", "Подписан", "В архиве"),
        ],
        [("отозвать", "Согласован", "Черновик")],
    ),
)


def run_machine(transitions: list[tuple[str, str, str]], start: str, events: list[str]) -> bool:
    state = start
    for ev in events:
        nxt = [t for e, s, t in transitions if e == ev and s == state]
        if not nxt:
            return False
        state = nxt[0]
    return True


def _gen_states(rng: random.Random) -> Variant:
    name, start, base, optional = rng.choice(_MACHINES)
    transitions = list(base) + [t for t in optional if rng.random() < 0.5]
    events = sorted({e for e, _, _ in transitions})
    valid: set[str] = set()
    invalid: set[str] = set()
    while len(valid) < 3 or len(invalid) < 3:
        n = rng.randint(2, 4)
        state = start
        seq: list[str] = []
        for _ in range(n):
            options = [e for e, s, _ in transitions if s == state]
            if not options:
                break
            ev = rng.choice(options)
            seq.append(ev)
            state = next(t for e, s, t in transitions if e == ev and s == state)
        if len(seq) < 2:
            continue
        if rng.random() < 0.5:
            i = rng.randrange(len(seq))
            seq[i] = rng.choice(events)
        text = " → ".join(seq)
        (valid if run_machine(transitions, start, seq) else invalid).add(text)
    correct = rng.sample(sorted(valid), rng.randint(1, min(3, len(valid))))
    wrong = rng.sample(sorted(invalid), rng.randint(2, min(3, len(invalid))))
    rows = [[e, s, t] for e, s, t in transitions]
    return make_multi_choice(
        rng,
        f"Объект «{name}» создаётся в состоянии «{start}». Разрешены только переходы из "
        "таблицы, любое другое событие система должна отклонить. Отметьте все "
        "последовательности событий, которые система должна принять целиком.",
        correct,
        wrong,
        code=table(["событие", "из состояния", "в состояние"], rows),
        extra={"min_choices": 1},
        explanation="Допустимые: " + "; ".join(correct),
    )


STATE_TRANSITIONS = ItemTemplate(
    id="qa.state_transitions",
    specialization="qa",
    topic="test_design",
    target_grade="middle",
    format=ItemFormat.MULTI_CHOICE,
    generator=_gen_states,
    a=1.4,
    b=0.3,
    title="Диаграмма переходов состояний",
    time_limit_s=180,
)

TEMPLATES = [EQUIVALENCE, DECISION_TABLE, PAIRWISE, STATE_TRANSITIONS]
