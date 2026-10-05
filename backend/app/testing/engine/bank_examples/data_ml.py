"""Data Science / ML: метрики классификации (numeric), диагноз переобучения (multi_choice)."""

from __future__ import annotations

import random

from ..templates import ItemFormat, ItemTemplate, NumericKey, Variant, make_multi_choice

# --------------------------------------------------------------------------- метрики классификации

_DOMAINS = (
    ("Модель антифрода", "мошенническая операция"),
    ("Модель оттока клиентов", "клиент уйдёт"),
    ("Скрининговая модель", "есть заболевание"),
    ("Спам-фильтр", "спам"),
    ("Модель кредитного скоринга", "дефолт"),
    ("Модель модерации отзывов", "токсичный отзыв"),
)

_METRICS = {
    "precision": "precision (точность)",
    "recall": "recall (полнота)",
    "f1": "F1-меру",
    "accuracy": "accuracy (долю верных ответов)",
    "specificity": "specificity (долю верно найденных отрицательных)",
}


def _gen_metrics(rng: random.Random) -> Variant:
    model, positive = rng.choice(_DOMAINS)
    tp = rng.randint(10, 90)
    fp = rng.randint(2, 45)
    fn = rng.randint(2, 45)
    tn = rng.randint(20, 300)
    metric = rng.choice(tuple(_METRICS))
    precision = tp / (tp + fp)
    recall = tp / (tp + fn)
    values = {
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall),
        "accuracy": (tp + tn) / (tp + fp + fn + tn),
        "specificity": tn / (tn + fp),
    }
    value = round(values[metric], 2)
    head = f"Факт: да ({positive})"
    width = max(len(head), len("Факт: нет")) + 2
    table = "\n".join(
        [
            " " * width + "Предсказано: да | Предсказано: нет",
            head.ljust(width) + f"{tp:>15} | {fn:>16}",
            "Факт: нет".ljust(width) + f"{fp:>15} | {tn:>16}",
        ]
    )
    return Variant(
        prompt=(
            f"{model} (положительный класс — «{positive}») дала на тесте такую матрицу ошибок. "
            f"Посчитайте {_METRICS[metric]}. Ответ округлите до двух знаков после запятой."
        ),
        key=NumericKey(value, 0.006),
        code=table,
        extra={"answer_type": "decimal", "decimals": 2},
        explanation=f"{metric} = {values[metric]:.4f}",
    )


CLASSIFICATION_METRICS = ItemTemplate(
    id="data_ml.classification_metrics",
    specialization="data_ml",
    topic="metrics",
    target_grade="junior",
    format=ItemFormat.NUMERIC,
    generator=_gen_metrics,
    a=1.5,
    b=-0.4,
    title="Метрика по матрице ошибок",
    time_limit_s=180,
)

# --------------------------------------------------------------------------- переобучение

_MODELS = {
    "градиентный бустинг": (
        "ограничить max_depth и добавить subsample",
        "уменьшить число деревьев",
    ),
    "случайный лес": ("увеличить min_samples_leaf", "ограничить max_depth деревьев"),
    "нейросеть": ("добавить dropout или weight decay", "уменьшить число слоёв и нейронов"),
    "логистическая регрессия на полиномиальных признаках": (
        "усилить L2-регуляризацию (уменьшить C)",
        "убрать полиномиальные признаки высоких степеней",
    ),
}
_METRIC_NAMES = ("accuracy", "ROC-AUC", "F1")


def _gen_fit(rng: random.Random) -> Variant:
    model = rng.choice(tuple(_MODELS))
    reg, simplify = _MODELS[model]
    metric = rng.choice(_METRIC_NAMES)
    case = rng.choice(("overfit", "overfit", "underfit", "good"))
    if case == "overfit":
        tr = round(rng.uniform(0.95, 0.999), 3)
        va = round(tr - rng.uniform(0.12, 0.25), 3)
        true_pool = [
            "Модель переобучилась: она запоминает обучающую выборку",
            f"Поможет регуляризация: {reg}",
            "Поможет увеличение объёма обучающих данных",
            f"Стоит упростить модель: {simplify}",
        ]
        false_pool = [
            "Модель недообучена, её нужно усложнить",
            "Нужно обучать дольше и убрать регуляризацию",
            "Разрыв между train и validation нормален и не требует внимания",
            "Валидацию можно убрать и учить модель на всех данных — это решит проблему",
        ]
    elif case == "underfit":
        tr = round(rng.uniform(0.58, 0.70), 3)
        va = round(tr - rng.uniform(-0.01, 0.03), 3)
        true_pool = [
            "Модель недообучена: она слишком простая для этих данных",
            "Стоит усложнить модель или добавить информативные признаки",
            "Если регуляризация сильная, её стоит ослабить",
        ]
        false_pool = [
            "Модель переобучилась",
            f"Поможет усилить регуляризацию: {reg}",
            "Главная проблема — разрыв между train и validation",
            "Нужно уменьшить объём обучающих данных",
        ]
    else:
        tr = round(rng.uniform(0.86, 0.93), 3)
        va = round(tr - rng.uniform(0.005, 0.03), 3)
        true_pool = [
            "Явных признаков переобучения нет",
            "Качество на train и validation согласовано",
        ]
        false_pool = [
            "Модель сильно переобучена",
            "Модель недообучена: метрика на train намного ниже, чем на validation",
            f"Нужно срочно {simplify}, иначе модель не обобщает",
        ]
    n_true = rng.randint(2, min(3, len(true_pool)))
    n_false = rng.randint(2, min(3, len(false_pool)))
    correct = rng.sample(true_pool, n_true)
    wrong = rng.sample(false_pool, n_false)
    return make_multi_choice(
        rng,
        f"Модель: {model}. {metric} на обучающей выборке — {tr:.3f}, "
        f"на валидационной — {va:.3f}. Отметьте все верные утверждения.",
        correct,
        wrong,
        extra={"min_choices": 1},
        explanation=f"Случай: {case}.",
    )


FIT_DIAGNOSIS = ItemTemplate(
    id="data_ml.fit_diagnosis",
    specialization="data_ml",
    topic="model_validation",
    target_grade="middle",
    format=ItemFormat.MULTI_CHOICE,
    generator=_gen_fit,
    a=1.2,
    b=0.5,
    title="Переобучение или недообучение",
    time_limit_s=150,
)

TEMPLATES = [CLASSIFICATION_METRICS, FIT_DIAGNOSIS]
