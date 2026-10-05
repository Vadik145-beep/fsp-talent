"""Data Science / ML — метрики: дисбаланс, регрессия, ROC-AUC, выбор метрики под задачу."""

from __future__ import annotations

import math
import random

from ...templates import (
    ItemFormat,
    ItemTemplate,
    NumericKey,
    Variant,
    make_multi_choice,
    make_single_choice,
)
from ._common import dec_key, table

# --------------------------------------------------------------------------- парадокс accuracy

_RARE = (
    ("транзакций", "мошеннические", "мошенничество", "не мошенничество"),
    ("писем", "спам", "спам", "не спам"),
    ("пациентов", "с заболеванием", "болен", "здоров"),
    ("клиентов", "ушедшие в отток", "уйдёт", "останется"),
    ("заявок на кредит", "с дефолтом", "дефолт", "без дефолта"),
    ("деталей", "бракованные", "брак", "норма"),
)


def _gen_accuracy_paradox(rng: random.Random) -> Variant:
    objects, rare_adj, rare_label, common_label = rng.choice(_RARE)
    while True:
        n = rng.choice((800, 1000, 1200, 2000, 2500, 4000, 5000, 8000, 10000, 20000))
        share = rng.choice((0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 12, 15))
        if (n * share * 10) % 1000 == 0:  # доля даёт целое число объектов
            break
    k = round(n * share / 100)
    question = rng.choice(("accuracy", "errors", "error_rate"))
    given = f"из них {k} — {rare_adj}"
    if question == "accuracy":
        value = (n - k) / n * 100
        ask = "Какую accuracy (в процентах) покажет такая модель? Округлите до десятых."
        key = dec_key(value, 1)
        extra = {"answer_type": "decimal", "decimals": 1, "unit": "%"}
    elif question == "errors":
        value = k
        given = f"доля объектов «{rare_label}» — {share}%"
        ask = "Сколько объектов такая модель классифицирует неверно?"
        key = NumericKey(k, 0)
        extra = {"answer_type": "integer"}
    else:
        value = k / n * 100
        ask = "Какую долю ошибок (error rate, в процентах) даст такая модель? Округлите до десятых."
        key = dec_key(value, 1)
        extra = {"answer_type": "decimal", "decimals": 1, "unit": "%"}
    return Variant(
        prompt=(
            f"В тестовой выборке {n} {objects}, {given}. "
            f"«Модель» всегда отвечает «{common_label}», не глядя на признаки. {ask}"
        ),
        key=key,
        extra=extra,
        explanation=f"Константная модель ошибается ровно на {k} объектах из {n}: {value:.3f}.",
    )


ACCURACY_PARADOX = ItemTemplate(
    id="data_ml.accuracy_paradox",
    specialization="data_ml",
    topic="metrics",
    target_grade="intern",
    format=ItemFormat.NUMERIC,
    generator=_gen_accuracy_paradox,
    a=1.1,
    b=-1.6,
    title="Accuracy при дисбалансе классов",
    time_limit_s=120,
)

# --------------------------------------------------------------------------- регрессионные метрики

_REG_DOMAINS = (
    ("Прогноз дневных продаж магазина", "шт.", (40, 160)),
    ("Прогноз времени доставки", "мин", (20, 90)),
    ("Прогноз цены квартиры", "млн ₽", (4, 30)),
    ("Прогноз температуры на завтра", "°C", (5, 30)),
    ("Прогноз числа заявок в колл-центр", "заявок", (50, 300)),
)
_REG_METRICS = {
    "mae": "MAE",
    "mse": "MSE",
    "rmse": "RMSE",
    "mape": "MAPE (в процентах)",
    "r2": "коэффициент детерминации R²",
}


def regression_metric(metric: str, y: list[int], p: list[int]) -> float:
    n = len(y)
    errs = [pi - yi for yi, pi in zip(y, p, strict=True)]
    if metric == "mae":
        return sum(abs(e) for e in errs) / n
    if metric == "mse":
        return sum(e * e for e in errs) / n
    if metric == "rmse":
        return math.sqrt(sum(e * e for e in errs) / n)
    if metric == "mape":
        return 100 * sum(abs(e) / abs(yi) for e, yi in zip(errs, y, strict=True)) / n
    mean = sum(y) / n
    ss_tot = sum((yi - mean) ** 2 for yi in y)
    return 1 - sum(e * e for e in errs) / ss_tot


def _gen_regression(rng: random.Random) -> Variant:
    title, unit, (lo, hi) = rng.choice(_REG_DOMAINS)
    n = rng.randint(4, 6)
    while True:
        y = [rng.randint(lo, hi) for _ in range(n)]
        if len(set(y)) > 1:
            break
    spread = max(2, (hi - lo) // 6)
    p = [max(1, yi + rng.randint(-spread, spread)) for yi in y]
    if p == y:
        p[0] += 1
    metric = rng.choice(tuple(_REG_METRICS))
    value = regression_metric(metric, y, p)
    code = table(
        ["№", f"факт, {unit}", f"прогноз, {unit}"],
        [[str(i + 1), str(a), str(b)] for i, (a, b) in enumerate(zip(y, p, strict=True))],
    )
    return Variant(
        prompt=(
            f"{title}: факт и прогноз модели на {n} объектах. Посчитайте {_REG_METRICS[metric]}. "
            "Ответ округлите до двух знаков после запятой."
        ),
        key=dec_key(value, 2),
        code=code,
        extra={"answer_type": "decimal", "decimals": 2},
        explanation=f"{metric} = {value:.4f}",
    )


REGRESSION_METRICS = ItemTemplate(
    id="data_ml.regression_metrics",
    specialization="data_ml",
    topic="metrics",
    target_grade="junior",
    format=ItemFormat.NUMERIC,
    generator=_gen_regression,
    a=1.3,
    b=-0.6,
    title="Метрики регрессии: MAE, RMSE, MAPE, R²",
    time_limit_s=240,
)

# --------------------------------------------------------------------------- ROC-AUC по парам


def roc_auc_pairs(labels: list[int], scores: list[float]) -> float:
    pos = [s for s, lab in zip(scores, labels, strict=True) if lab == 1]
    neg = [s for s, lab in zip(scores, labels, strict=True) if lab == 0]
    good = sum(1.0 if p > q else 0.5 if p == q else 0.0 for p in pos for q in neg)
    return good / (len(pos) * len(neg))


def _gen_roc_auc(rng: random.Random) -> Variant:
    n_pos = rng.randint(2, 4)
    n_neg = rng.randint(3, 5)
    while True:
        grid = [round(0.05 * i, 2) for i in range(1, 20)]
        scores = [rng.choice(grid) for _ in range(n_pos + n_neg)]
        labels = [1] * n_pos + [0] * n_neg
        auc = roc_auc_pairs(labels, scores)
        # не тривиально: не 1.0 и не 0.0, а ничьи встречаются не всегда
        ties = any(
            scores[i] == scores[j] for i in range(n_pos) for j in range(n_pos, n_pos + n_neg)
        )
        if 0.5 < auc < 1.0 and (not ties or rng.random() < 0.5):
            break
    order = list(range(n_pos + n_neg))
    rng.shuffle(order)
    ids = [chr(ord("A") + i) for i in range(len(order))]
    rows = [[ids[k], str(labels[i]), f"{scores[i]:.2f}"] for k, i in enumerate(order)]
    return Variant(
        prompt=(
            "Модель выдала вероятности положительного класса для объектов тестовой выборки "
            "(класс 1 — положительный). Посчитайте ROC-AUC. Если оценки положительного "
            "и отрицательного объектов равны, пара считается за половину. "
            "Ответ округлите до двух знаков после запятой."
        ),
        key=dec_key(auc, 2),
        code=table(["объект", "класс", "оценка"], rows),
        extra={"answer_type": "decimal", "decimals": 2},
        explanation=f"Доля верно упорядоченных пар (положительный выше): {auc:.4f}",
    )


ROC_AUC = ItemTemplate(
    id="data_ml.roc_auc_pairs",
    specialization="data_ml",
    topic="metrics",
    target_grade="middle",
    format=ItemFormat.NUMERIC,
    generator=_gen_roc_auc,
    a=1.5,
    b=0.6,
    title="ROC-AUC вручную",
    time_limit_s=240,
)

# --------------------------------------------------------------------------- метрика под бизнес

_M = {
    "acc": "Accuracy",
    "roc": "ROC-AUC",
    "pr": "PR-AUC (площадь под precision-recall кривой)",
    "patk": "Precision@K — точность среди K объектов с наибольшим скором",
    "recall": "Recall (полнота) при ограничении на precision",
    "precision": "Precision (точность)",
    "rmse": "RMSE",
    "mae": "MAE",
    "mape": "MAPE",
    "wape": "WAPE: сумма |ошибок| / сумма фактических значений",
    "r2": "R²",
    "logloss": "Log loss (или Brier score) — качество самих вероятностей",
    "ndcg": "NDCG@k",
    "pinball": "Квантильная (pinball) функция потерь",
    "f1": "F1 при пороге 0.5",
}


def _business_scenarios(rng: random.Random) -> list[tuple[str, str, list[str]]]:
    k = rng.choice((50, 100, 200, 300, 500))
    share = rng.choice((0.1, 0.2, 0.3, 0.5))
    miss = rng.choice((20, 50, 100))
    zeros = rng.choice((30, 40, 55, 60))
    top = rng.choice((5, 10, 20))
    late = rng.choice((3, 4, 5))
    return [
        (
            f"Антифрод: мошеннических операций {share}%. Служба безопасности успевает вручную "
            f"проверить только {k} операций в день — самые подозрительные по скору модели.",
            "patk",
            ["acc", "roc", "rmse", "r2", "f1"],
        ),
        (
            f"Скрининг онкологии: пропуск больного обходится в {miss} раз дороже, чем лишнее "
            "направление на дообследование, но клиника не может отправлять на дообследование всех.",
            "recall",
            ["acc", "precision", "rmse", "mape", "ndcg"],
        ),
        (
            f"Прогноз спроса по магазинам: в {zeros}% дней у товара нулевые продажи. Нужна одна "
            "метрика ошибки в процентах для отчёта руководству.",
            "wape",
            ["mape", "r2", "acc", "roc", "ndcg"],
        ),
        (
            "Выдача поиска интернет-магазина: у товаров градации релевантности (0–3), "
            f"пользователь почти всегда смотрит только первые {top} позиций.",
            "ndcg",
            ["acc", "rmse", "mape", "r2", "recall"],
        ),
        (
            "Страховая компания умножает предсказанную вероятность страхового случая на сумму "
            "выплаты и так считает цену полиса. Важно, чтобы вероятность 0.1 означала 10% случаев.",
            "logloss",
            ["acc", "roc", "f1", "ndcg", "mape"],
        ),
        (
            f"Модель оттока, ушедших клиентов {rng.choice((1, 2, 3))}%. Нужно сравнить несколько "
            "моделей по качеству ранжирования на редком положительном классе, "
            "порог пока не выбран.",
            "pr",
            ["acc", "rmse", "mape", "r2", "f1"],
        ),
        (
            "Прогноз времени прибытия курьера: опоздание раздражает клиентов в "
            f"{late} раза сильнее, чем такой же ранний приезд, поэтому прогноз должен быть "
            "несимметричным.",
            "pinball",
            ["acc", "roc", "r2", "ndcg", "f1"],
        ),
        (
            "Прогноз стоимости ремонта по фото: редкие большие промахи (на сотни тысяч рублей) "
            "для бизнеса намного хуже множества мелких, их нужно штрафовать сильнее.",
            "rmse",
            ["acc", "roc", "mape", "ndcg", "f1"],
        ),
    ]


def _gen_metric_choice(rng: random.Random) -> Variant:
    text, correct, wrong = rng.choice(_business_scenarios(rng))
    return make_single_choice(
        rng,
        f"{text}\nКакую метрику разумнее всего выбрать основной для оценки модели?",
        _M[correct],
        [_M[w] for w in wrong],
        explanation=f"Верно: {_M[correct]}.",
    )


METRIC_CHOICE = ItemTemplate(
    id="data_ml.metric_choice_business",
    specialization="data_ml",
    topic="metrics",
    target_grade="senior",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_metric_choice,
    a=1.2,
    b=1.3,
    title="Метрика под бизнес-задачу",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- сильный дисбаланс


def _thousands(x: int) -> str:
    return f"{x:,}".replace(",", " ")


def _gen_imbalance(rng: random.Random) -> Variant:
    domain = rng.choice(
        ("мошеннических платежей", "дефолтов по кредитам", "отказов оборудования", "кликов")
    )
    n = rng.choice((200_000, 500_000, 1_000_000, 2_000_000))
    p = rng.choice((0.1, 0.2, 0.5, 1.0))
    pos = round(n * p / 100)
    folds = rng.choice((5, 10))
    acc = 100 - p
    true_pool = [
        f"ROC-AUC может оставаться высоким при низкой precision, поэтому при {p}% "
        "положительных полезно смотреть ещё и на PR-AUC",
        "Oversampling (например, SMOTE) применяют только к обучающей части внутри каждого фолда, "
        "а не ко всему датасету до разбиения",
        "После undersampling отрицательного класса вероятности модели завышены: перед "
        "использованием как вероятностей их нужно откалибровать или пересчитать",
        "Порог классификации стоит подбирать по стоимости ошибок, а не оставлять 0.5",
        f"Фолды кросс-валидации нужно стратифицировать: в каждом из {folds} фолдов должно быть "
        f"примерно {pos // folds} положительных",
    ]
    false_pool = [
        f"Accuracy {acc}% у модели, которая всегда отвечает «нет», говорит о хорошем качестве",
        "SMOTE удобно применить ко всему датасету до train_test_split — тогда и в тесте будет "
        "больше положительных",
        "class_weight='balanced' меняет состав тестовой выборки, поэтому метрики на тесте "
        "становятся несравнимыми",
        "Undersampling не влияет на вероятности модели, их можно сразу использовать для расчёта "
        "ожидаемых потерь",
        "При дисбалансе нужно оптимизировать accuracy и всегда использовать порог 0.5",
    ]
    correct = rng.sample(true_pool, rng.randint(2, 3))
    wrong = rng.sample(false_pool, rng.randint(2, 3))
    return make_multi_choice(
        rng,
        f"Датасет: {_thousands(n)} объектов, доля {domain} — {p}% "
        f"({_thousands(pos)} положительных). Отметьте все верные утверждения.",
        correct,
        wrong,
        extra={"min_choices": 1},
        explanation="Верные: " + "; ".join(correct),
    )


IMBALANCE = ItemTemplate(
    id="data_ml.imbalance_strategies",
    specialization="data_ml",
    topic="metrics",
    target_grade="senior",
    format=ItemFormat.MULTI_CHOICE,
    generator=_gen_imbalance,
    a=1.3,
    b=1.4,
    title="Работа с сильным дисбалансом классов",
    time_limit_s=180,
)

TEMPLATES = [ACCURACY_PARADOX, REGRESSION_METRICS, ROC_AUC, METRIC_CHOICE, IMBALANCE]
