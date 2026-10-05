"""Data Science / ML — статистика: p-value, z-тест для долей, множественные сравнения."""

from __future__ import annotations

import math
import random

from ...templates import ItemFormat, ItemTemplate, NumericKey, Variant, make_multi_choice
from ._common import dec_key

# --------------------------------------------------------------------------- интерпретация p-value


def _gen_pvalue(rng: random.Random) -> Variant:
    alpha = rng.choice((0.05, 0.05, 0.01, 0.1))
    c1 = round(rng.uniform(2.0, 12.0), 1)
    c2 = round(c1 + rng.choice((-1, 1)) * rng.uniform(0.2, 1.5), 1)
    significant = rng.random() < 0.5
    if significant:
        p = round(rng.uniform(0.001, alpha * 0.8), 3)
    else:
        p = round(rng.uniform(alpha * 1.3, min(0.6, alpha * 8)), 3)
    p = max(p, 0.001)
    common_true = (
        f"Если бы на самом деле разницы не было, такое же или ещё большее различие получилось "
        f"бы с вероятностью около {p}"
    )
    common_false = [
        f"Вероятность того, что нулевая гипотеза верна, равна {p}",
        f"Вероятность того, что новый вариант лучше, равна {round(1 - p, 3)}",
    ]
    if significant:
        true_pool = [
            common_true,
            f"Различие статистически значимо на уровне α = {alpha}",
            "Нулевую гипотезу о равенстве конверсий отвергаем",
        ]
        false_pool = [
            *common_false,
            "Раз различие значимо, эффект обязательно большой и важен для бизнеса",
            f"На уровне α = {alpha} отвергнуть нулевую гипотезу нельзя",
        ]
    else:
        true_pool = [
            common_true,
            f"На уровне α = {alpha} отвергнуть нулевую гипотезу нельзя",
            "Это не доказывает равенство конверсий: эффект может быть, но тесту не хватило "
            "данных (мощности)",
        ]
        false_pool = [
            *common_false,
            "Тест доказал, что варианты не отличаются",
            f"Различие статистически значимо на уровне α = {alpha}",
            "Стоит продолжать тест и проверять p-value каждый день, пока оно не станет "
            f"меньше {alpha}, а затем остановить",
        ]
    correct = rng.sample(true_pool, rng.randint(2, 3))
    wrong = rng.sample(false_pool, rng.randint(2, 3))
    return make_multi_choice(
        rng,
        f"A/B-тест: конверсия в контроле {c1}%, в тестовой группе {c2}%. Двусторонний тест "
        f"дал p-value = {p}, уровень значимости α = {alpha}. Отметьте все верные утверждения.",
        correct,
        wrong,
        extra={"min_choices": 1},
        explanation=f"p {'<' if significant else '≥'} α.",
    )


PVALUE = ItemTemplate(
    id="data_ml.pvalue_interpretation",
    specialization="data_ml",
    topic="statistics",
    target_grade="junior",
    format=ItemFormat.MULTI_CHOICE,
    generator=_gen_pvalue,
    a=1.3,
    b=-0.3,
    title="Как читать p-value",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- z-тест для двух долей


def two_proportion_z(x1: int, n1: int, x2: int, n2: int) -> float:
    p1, p2 = x1 / n1, x2 / n2
    pooled = (x1 + x2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    return (p2 - p1) / se


def _gen_ztest(rng: random.Random) -> Variant:
    while True:
        n1 = rng.choice(range(1000, 20001, 500))
        n2 = rng.choice(range(1000, 20001, 500))
        base = rng.uniform(0.02, 0.15)
        x1 = round(n1 * base)
        x2 = round(n2 * base * rng.uniform(0.85, 1.25))
        z = two_proportion_z(x1, n1, x2, n2)
        if 0.3 < abs(z) < 6:
            break
    product = rng.choice(("лендинга", "кнопки «Купить»", "формы регистрации", "письма"))
    return Variant(
        prompt=(
            f"A/B-тест нового варианта {product}. Группа A: {n1} пользователей, {x1} конверсий. "
            f"Группа B: {n2} пользователей, {x2} конверсий. Посчитайте z-статистику "
            "двухвыборочного z-теста для долей (B минус A, стандартная ошибка "
            "по объединённой доле). "
            "Ответ округлите до двух знаков после запятой."
        ),
        key=dec_key(z, 2),
        extra={"answer_type": "decimal", "decimals": 2},
        explanation=f"z = {z:.4f}",
    )


ZTEST = ItemTemplate(
    id="data_ml.ab_ztest",
    specialization="data_ml",
    topic="statistics",
    target_grade="middle",
    format=ItemFormat.NUMERIC,
    generator=_gen_ztest,
    a=1.4,
    b=0.7,
    title="z-тест для конверсий",
    time_limit_s=240,
)

# --------------------------------------------------------------------------- множественные проверки

_METHODS = {
    "bonferroni": "поправку Бонферрони",
    "holm": "метод Холма (Holm–Bonferroni)",
    "bh": "процедуру Бенджамини–Хохберга (контроль FDR)",
}


def rejections(method: str, pvals: list[float], alpha: float) -> int:
    m = len(pvals)
    ps = sorted(pvals)
    if method == "bonferroni":
        return sum(1 for p in ps if p <= alpha / m)
    if method == "holm":
        k = 0
        for i, p in enumerate(ps):
            if p <= alpha / (m - i):
                k += 1
            else:
                break
        return k
    best = 0
    for i, p in enumerate(ps, start=1):
        if p <= alpha * i / m:
            best = i
    return best


def _gen_multiple(rng: random.Random) -> Variant:
    alpha = rng.choice((0.05, 0.05, 0.1))
    method = rng.choice(tuple(_METHODS))
    while True:
        m = rng.randint(5, 8)
        pvals = []
        for _ in range(m):
            if rng.random() < 0.55:
                pvals.append(round(rng.uniform(0.0005, alpha * 0.5), 4))
            else:
                pvals.append(round(rng.uniform(alpha * 0.5, alpha * 4), 3))
        thresholds = {alpha / m, *(alpha / (m - i) for i in range(m))}
        thresholds |= {alpha * i / m for i in range(1, m + 1)}
        if len(set(pvals)) < m or any(abs(p - t) < 2e-4 for p in pvals for t in thresholds):
            continue
        k = rejections(method, pvals, alpha)
        naive = sum(1 for p in pvals if p <= alpha)
        if k != naive and k > 0:
            break
    names = rng.sample(
        [
            "конверсия",
            "выручка",
            "ARPU",
            "удержание D7",
            "время в приложении",
            "CTR",
            "средний чек",
            "число сессий",
            "доля возвратов",
            "NPS",
        ],
        m,
    )
    listing = "\n".join(f"{nm}: p = {p}" for nm, p in zip(names, pvals, strict=True))
    return Variant(
        prompt=(
            f"В A/B-тесте проверили {m} метрик. Чтобы контролировать ошибки при множественных "
            f"сравнениях, применили {_METHODS[method]} на уровне α = {alpha}. "
            "Сколько нулевых гипотез будет отвергнуто?"
        ),
        key=NumericKey(k, 0),
        code=listing,
        extra={"answer_type": "integer"},
        explanation=f"{method}: отвергнуто {k} (без поправки было бы {naive}).",
    )


MULTIPLE_TESTING = ItemTemplate(
    id="data_ml.multiple_testing",
    specialization="data_ml",
    topic="statistics",
    target_grade="senior",
    format=ItemFormat.NUMERIC,
    generator=_gen_multiple,
    a=1.5,
    b=1.5,
    title="Поправки на множественные сравнения",
    time_limit_s=240,
)

TEMPLATES = [PVALUE, ZTEST, MULTIPLE_TESTING]
