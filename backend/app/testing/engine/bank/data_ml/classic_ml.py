"""Data Science / ML — классические модели: kNN, критерий разбиения дерева, регуляризация."""

from __future__ import annotations

import math
import random

from ...templates import ItemFormat, ItemTemplate, Variant, make_multi_choice
from ._common import dec_key, table

# --------------------------------------------------------------------------- kNN

_LABEL_SETS = (
    ("A", "B", "C"),
    ("кошка", "собака", "лиса"),
    ("red", "green", "blue"),
    ("эконом", "комфорт", "бизнес"),
)


def knn_distance(metric: str, p: tuple[int, int], q: tuple[int, int]) -> float:
    if metric == "manhattan":
        return abs(p[0] - q[0]) + abs(p[1] - q[1])
    return math.hypot(p[0] - q[0], p[1] - q[1])


def _gen_knn(rng: random.Random) -> Variant:
    labels = rng.choice(_LABEL_SETS)
    k = rng.choice((3, 5))
    metric = rng.choice(("euclidean", "manhattan"))
    while True:
        n = rng.randint(7, 10)
        pts = list({(rng.randint(0, 9), rng.randint(0, 9)) for _ in range(n)})
        if len(pts) < 7:
            continue
        cls = [rng.choice(labels) for _ in pts]
        q = (rng.randint(1, 8), rng.randint(1, 8))
        if q in pts:
            continue
        d = sorted((knn_distance(metric, p, q), i) for i, p in enumerate(pts))
        if d[k - 1][0] == d[k][0]:
            continue  # граница k-го соседа неоднозначна
        votes: dict[str, int] = {}
        for _, i in d[:k]:
            votes[cls[i]] = votes.get(cls[i], 0) + 1
        ranked = sorted(votes.values(), reverse=True)
        if len(ranked) > 1 and ranked[0] == ranked[1]:
            continue
        answer = max(votes, key=lambda c: votes[c])
        # класс ближайшего соседа должен иногда отличаться от ответа: k имеет значение
        if cls[d[0][1]] == answer and rng.random() < 0.5:
            continue
        break
    rows = [[str(i + 1), str(p[0]), str(p[1]), cls[i]] for i, p in enumerate(pts)]
    metric_ru = "евклидовым" if metric == "euclidean" else "манхэттенским"
    return Variant(
        prompt=(
            f"Обучающая выборка из {len(pts)} точек. Какой класс kNN с k = {k} и {metric_ru} "
            f"расстоянием присвоит новой точке ({q[0]}, {q[1]})? Голоса соседей равноправны. "
            "Ответ — название класса."
        ),
        key=(answer,),
        code=table(["№", "x1", "x2", "класс"], rows),
        extra={"answer_type": "text", "max_length": 20},
        explanation=f"Голоса: {votes}",
    )


KNN_PREDICT = ItemTemplate(
    id="data_ml.knn_predict",
    specialization="data_ml",
    topic="classic_ml",
    target_grade="junior",
    format=ItemFormat.SHORT_TEXT,
    generator=_gen_knn,
    a=1.2,
    b=-0.6,
    title="Предсказание kNN вручную",
    time_limit_s=240,
)

# --------------------------------------------------------------------------- критерий разбиения


def gini(counts: list[int]) -> float:
    n = sum(counts)
    return 1 - sum((c / n) ** 2 for c in counts)


def entropy(counts: list[int]) -> float:
    n = sum(counts)
    return -sum(c / n * math.log2(c / n) for c in counts if c)


def _gen_gini(rng: random.Random) -> Variant:
    n_cls = rng.choice((2, 2, 3))
    while True:
        left = [rng.randint(0, 30) for _ in range(n_cls)]
        right = [rng.randint(0, 30) for _ in range(n_cls)]
        parent = [a + b for a, b in zip(left, right, strict=True)]
        if min(sum(left), sum(right)) < 4 or min(parent) == 0:
            continue
        if gini(left) == 0 and gini(right) == 0:
            continue
        break
    q = rng.choice(("parent_gini", "split_gini", "gini_gain", "info_gain"))
    nl, nr, n = sum(left), sum(right), sum(parent)
    weighted_gini = nl / n * gini(left) + nr / n * gini(right)
    if q == "parent_gini":
        value, ask = gini(parent), "индекс Джини в исходном узле"
    elif q == "split_gini":
        value, ask = weighted_gini, "взвешенный индекс Джини после разбиения (по долям объектов)"
    elif q == "gini_gain":
        value, ask = gini(parent) - weighted_gini, "уменьшение индекса Джини после разбиения"
    else:
        we = nl / n * entropy(left) + nr / n * entropy(right)
        value, ask = entropy(parent) - we, "прирост информации (information gain, энтропия по log₂)"
    names = rng.choice((("0", "1", "2"), ("A", "B", "C"), ("кошка", "собака", "лиса")))[:n_cls]
    if n_cls == 2 and rng.random() < 0.3:
        names = ("нет", "да")
    rows = [
        ["левый узел", *map(str, left)],
        ["правый узел", *map(str, right)],
    ]
    feat = rng.choice(("age <= 30", "income <= 50000", "visits <= 3", "tenure <= 12"))
    return Variant(
        prompt=(
            f"Дерево решений разбивает узел по условию {feat}. Число объектов каждого класса "
            f"в дочерних узлах дано в таблице. Посчитайте {ask}. "
            "Ответ округлите до трёх знаков после запятой."
        ),
        key=dec_key(value, 3),
        code=table(["узел", *[f"класс {c}" for c in names]], rows),
        extra={"answer_type": "decimal", "decimals": 3},
        explanation=f"{q} = {value:.5f}",
    )


GINI_SPLIT = ItemTemplate(
    id="data_ml.gini_split",
    specialization="data_ml",
    topic="classic_ml",
    target_grade="middle",
    format=ItemFormat.NUMERIC,
    generator=_gen_gini,
    a=1.4,
    b=0.5,
    title="Индекс Джини и прирост информации",
    time_limit_s=240,
)

# --------------------------------------------------------------------------- регуляризация


def _gen_regularization(rng: random.Random) -> Variant:
    model = rng.choice(("ridge", "lasso", "logreg_l2", "logreg_l1"))
    stronger = rng.random() < 0.5
    small, big = rng.choice(((0.01, 1.0), (0.1, 10.0), (0.5, 5.0), (1.0, 100.0)))
    if model in ("ridge", "lasso"):
        cls = "Ridge" if model == "ridge" else "Lasso"
        a1, a2 = (small, big) if stronger else (big, small)
        change = f"{cls}: параметр alpha изменили с {a1} на {a2}"
    else:
        pen = "l2" if model == "logreg_l2" else "l1"
        solver = ", solver='liblinear'" if pen == "l1" else ""
        c1, c2 = (big, small) if stronger else (small, big)  # C — обратная сила
        change = f"LogisticRegression(penalty='{pen}'{solver}): параметр C изменили с {c1} на {c2}"
    sparse = model in ("lasso", "logreg_l1")
    if stronger:
        true_pool = [
            "Регуляризация стала сильнее",
            "Коэффициенты модели в среднем уменьшатся по модулю",
            "Функция потерь на обучающей выборке (без штрафа) не уменьшится",
        ]
        false_pool = [
            "Регуляризация стала слабее",
            "Модель станет склоннее к переобучению",
            "Функция потерь на обучающей выборке (без штрафа) обязательно уменьшится",
        ]
        if sparse:
            true_pool.append("Больше коэффициентов может стать ровно нулём")
        else:
            false_pool.append("Многие коэффициенты станут ровно нулём — так работает этот штраф")
    else:
        true_pool = [
            "Регуляризация стала слабее",
            "Коэффициенты модели могут вырасти по модулю",
            "Риск переобучения вырос",
        ]
        false_pool = [
            "Регуляризация стала сильнее",
            "Модель станет проще, а дисперсия предсказаний снизится",
            "Функция потерь на обучающей выборке (без штрафа) вырастет",
        ]
    true_pool.append("Перед обучением признаки стоит стандартизировать: штраф зависит от масштаба")
    false_pool.append("Масштаб признаков не важен: штраф одинаково действует на любые признаки")
    correct = rng.sample(true_pool, rng.randint(2, 3))
    wrong = rng.sample(false_pool, rng.randint(2, 3))
    return make_multi_choice(
        rng,
        f"{change}. Остальное не меняли. Отметьте все верные утверждения.",
        correct,
        wrong,
        extra={"min_choices": 1},
        explanation=f"Регуляризация {'сильнее' if stronger else 'слабее'}.",
    )


REGULARIZATION = ItemTemplate(
    id="data_ml.regularization_effects",
    specialization="data_ml",
    topic="classic_ml",
    target_grade="middle",
    format=ItemFormat.MULTI_CHOICE,
    generator=_gen_regularization,
    a=1.3,
    b=0.3,
    title="Как параметр регуляризации меняет модель",
    time_limit_s=150,
)

TEMPLATES = [KNN_PREDICT, GINI_SPLIT, REGULARIZATION]
