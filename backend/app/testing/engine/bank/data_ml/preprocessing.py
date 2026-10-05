"""Data Science / ML — предобработка признаков: выбор кодирования, one-hot в pandas."""

from __future__ import annotations

import random

from ...templates import ItemFormat, ItemTemplate, Variant, make_single_choice

# --------------------------------------------------------------------------- выбор кодирования

_ENC = {
    "onehot": "One-hot: отдельный столбец 0/1 на каждое значение",
    "ordinal": "Порядковое кодирование: значения заменяются числами 0, 1, 2… по порядку",
    "target": "Target encoding: среднее целевой переменной по категории, считается по фолдам",
    "cyclic": "Два признака sin и cos от значения, нормированного на период",
    "log": "Логарифмирование: log(1 + x)",
    "binary01": "Замена на 0/1",
    "raw": "Оставить значение как есть",
    "drop": "Удалить признак, не проверяя его полезность",
    "standard": "Стандартизация: вычесть среднее и поделить на стандартное отклонение",
}


def _gen_encoding(rng: random.Random) -> Variant:
    k_colors = rng.randint(4, 9)
    k_shops = rng.choice((3000, 8000, 12000, 25000))
    scenarios = [
        (
            f"Признак «цвет автомобиля» — {k_colors} значений без естественного порядка. "
            "Модель — линейная регрессия.",
            "onehot",
            ["ordinal", "log", "cyclic", "standard"],
        ),
        (
            "Признак «уровень образования»: среднее < колледж < бакалавр < магистр < PhD. "
            "Нужно сохранить порядок в одном числовом признаке.",
            "ordinal",
            ["onehot", "cyclic", "log", "raw"],
        ),
        (
            f"Признак «id магазина» — {k_shops} уникальных значений, модель — градиентный "
            "бустинг, памяти мало.",
            "target",
            ["onehot", "cyclic", "log", "drop"],
        ),
        (
            f"Признак «{rng.choice(('час суток (0–23)', 'месяц (1–12)', 'день недели (0–6)'))}». "
            "Нужно, чтобы соседние значения через границу периода (например, конец и начало) "
            "оказались рядом.",
            "cyclic",
            ["raw", "log", "ordinal", "target"],
        ),
        (
            f"Признак «{rng.choice(('доход клиента', 'сумма покупок за год', 'число просмотров'))}»"
            ": неотрицательный, с длинным правым хвостом. Модель — линейная.",
            "log",
            ["onehot", "cyclic", "ordinal", "binary01"],
        ),
        (
            f"Признак «{rng.choice(('есть ли подписка', 'подтверждён email', 'был ли возврат'))}»"
            " принимает значения «да» и «нет».",
            "binary01",
            ["target", "cyclic", "log", "standard"],
        ),
        (
            f"Признаки «возраст» (лет) и «{rng.choice(('доход', 'стоимость квартиры'))}» (рублей)"
            " имеют разный масштаб, модель — kNN.",
            "standard",
            ["onehot", "cyclic", "ordinal", "raw"],
        ),
    ]
    text, correct, wrong = rng.choice(scenarios)
    return make_single_choice(
        rng,
        f"{text}\nКак лучше подготовить этот признак?",
        _ENC[correct],
        [_ENC[w] for w in wrong],
        explanation=f"Верно: {_ENC[correct]}",
    )


ENCODING_CHOICE = ItemTemplate(
    id="data_ml.encoding_choice",
    specialization="data_ml",
    topic="preprocessing",
    target_grade="intern",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_encoding,
    a=1.1,
    b=-1.3,
    title="Как закодировать признак",
    time_limit_s=90,
)

# --------------------------------------------------------------------------- one-hot в pandas

_CAT_COLS = (
    ("color", ("red", "blue", "green", "black", "white")),
    ("size", ("S", "M", "L", "XL")),
    ("city", ("Kazan", "Omsk", "Perm", "Tula", "Ufa")),
    ("tariff", ("basic", "pro", "max")),
)
_NUM_COLS = ("price", "qty", "age", "rating")


def _gen_one_hot(rng: random.Random) -> Variant:
    n = rng.randint(4, 8)
    cats = rng.sample(_CAT_COLS, rng.randint(2, 3))
    nums = rng.sample(_NUM_COLS, rng.randint(1, 2))
    data: dict[str, list[str] | list[int]] = {}
    uniq: dict[str, int] = {}
    for name, values in cats:
        col = [rng.choice(values) for _ in range(n)]
        data[name] = col
        uniq[name] = len(set(col))
    for name in nums:
        data[name] = [rng.randint(1, 500) for _ in range(n)]
    order = list(data)
    rng.shuffle(order)
    all_cats = [c for c in order if c in uniq]
    mode = rng.choice(("all", "subset", "subset"))
    encoded = all_cats if mode == "all" else rng.sample(all_cats, rng.randint(1, len(all_cats)))
    encoded = [c for c in order if c in encoded]
    drop_first = rng.random() < 0.5
    cols = len(order) - len(encoded) + sum(uniq[c] - (1 if drop_first else 0) for c in encoded)
    lines = ["import pandas as pd", "", "df = pd.DataFrame({"]
    for name in order:
        vals = ", ".join(f'"{v}"' if isinstance(v, str) else str(v) for v in data[name])
        lines.append(f'    "{name}": [{vals}],')
    lines.append("})")
    args = []
    if mode == "subset" or rng.random() < 0.5:
        args.append("columns=[" + ", ".join(f'"{c}"' for c in encoded) + "]")
    if drop_first or rng.random() < 0.3:
        args.append(f"drop_first={drop_first}")
    lines.append("out = pd.get_dummies(df" + "".join(f", {a}" for a in args) + ")")
    lines.append("print(out.shape)")
    return Variant(
        prompt=("Что выведет код? Запишите ответ так, как его напечатает Python, например (3, 7)."),
        key=f"({n}, {cols})",
        code="\n".join(lines),
        extra={"language": "python"},
        explanation=f"Закодированы {encoded}, drop_first={drop_first}: {cols} столбцов.",
    )


ONE_HOT_SHAPE = ItemTemplate(
    id="data_ml.one_hot_shape",
    specialization="data_ml",
    topic="preprocessing",
    target_grade="intern",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_one_hot,
    a=1.2,
    b=-1.1,
    title="Сколько столбцов после get_dummies",
    time_limit_s=150,
)

TEMPLATES = [ENCODING_CHOICE, ONE_HOT_SHAPE]
