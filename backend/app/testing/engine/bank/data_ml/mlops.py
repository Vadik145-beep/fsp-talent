"""Data Science / ML — жизненный цикл моделей: этапы проекта, дрейф, PSI, безопасный выпуск."""

from __future__ import annotations

import math
import random

from ...templates import ItemFormat, ItemTemplate, Variant, make_ordering, make_single_choice
from ._common import dec_key, table

# --------------------------------------------------------------------------- этапы CRISP-DM

_PROJECTS = (
    ("снизить отток клиентов на {x}%", "история договоров и обращений в поддержку", "оттока"),
    ("сократить потери от мошенничества на {x}%", "журнал платежей и чарджбэков", "мошенничества"),
    ("уменьшить списания продуктов на {x}%", "продажи и остатки по магазинам", "спроса"),
    ("поднять конверсию рассылок на {x}%", "логи открытий и кликов по письмам", "отклика"),
)


def _gen_crisp(rng: random.Random) -> Variant:
    goal, data, what = rng.choice(_PROJECTS)
    goal = goal.format(x=rng.choice((5, 10, 15, 20)))
    metric = rng.choice(("ROC-AUC", "PR-AUC", "MAE", "F1"))
    steps = [
        f"Согласовать с заказчиком цель — {goal} — и критерий успеха",
        f"Изучить доступные данные ({data}): объём, пропуски, распределения",
        "Очистить данные, собрать признаки и обучающую выборку",
        f"Обучить несколько моделей {what} и подобрать гиперпараметры",
        f"Оценить модели на отложенных данных ({metric}) и проверить, достигается ли цель",
        "Внедрить модель в рабочий процесс и передать в эксплуатацию",
    ]
    if rng.random() < 0.4:
        steps.append("Наблюдать за качеством модели в работе и переобучать при деградации")
    return make_ordering(
        rng,
        "Расставьте этапы ML-проекта в правильном порядке (по методологии CRISP-DM).",
        steps,
        explanation="Business → Data understanding → Preparation → Modeling → Evaluation → "
        "Deployment.",
    )


CRISP_DM = ItemTemplate(
    id="data_ml.crisp_dm_order",
    specialization="data_ml",
    topic="mlops",
    target_grade="junior",
    format=ItemFormat.ORDERING,
    generator=_gen_crisp,
    a=1.0,
    b=-0.7,
    title="Этапы ML-проекта",
    time_limit_s=120,
)

# --------------------------------------------------------------------------- PSI


def psi(expected: list[float], actual: list[float]) -> float:
    return sum((a - e) * math.log(a / e) for e, a in zip(expected, actual, strict=True))


def _random_shares(rng: random.Random, k: int) -> list[int]:
    while True:
        cuts = sorted(rng.sample(range(1, 100), k - 1))
        parts = [b - a for a, b in zip([0, *cuts], [*cuts, 100], strict=True)]
        if min(parts) >= 4:
            return parts


def _gen_psi(rng: random.Random) -> Variant:
    k = rng.choice((4, 5))
    feature, bins = rng.choice(
        (
            ("возраст клиента", ["18–25", "26–35", "36–45", "46–60", "60+"]),
            ("сумма заказа, ₽", ["<500", "500–1500", "1500–3000", "3000–7000", "7000+"]),
            ("скор кредитного бюро", ["<500", "500–600", "600–700", "700–800", "800+"]),
            ("число визитов за месяц", ["0", "1–2", "3–5", "6–10", "11+"]),
        )
    )
    bins = bins if k == 5 else [*bins[:3], bins[3].split("–")[0] + "+"]
    while True:
        exp = _random_shares(rng, k)
        act = _random_shares(rng, k)
        value = psi([e / 100 for e in exp], [a / 100 for a in act])
        if 0.02 < value < 0.6:
            break
    rows = [[b, f"{e}%", f"{a}%"] for b, e, a in zip(bins, exp, act, strict=True)]
    return Variant(
        prompt=(
            f"Мониторинг дрейфа признака «{feature}»: доли объектов по бинам на обучении "
            "и в проде за последнюю неделю. Посчитайте PSI (population stability index, "
            "натуральный логарифм). Ответ округлите до трёх знаков после запятой."
        ),
        key=dec_key(value, 3),
        code=table(["бин", "обучение", "прод"], rows),
        extra={"answer_type": "decimal", "decimals": 3},
        explanation=f"PSI = Σ (a − e)·ln(a/e) = {value:.5f}",
    )


DRIFT_PSI = ItemTemplate(
    id="data_ml.drift_psi",
    specialization="data_ml",
    topic="mlops",
    target_grade="senior",
    format=ItemFormat.NUMERIC,
    generator=_gen_psi,
    a=1.3,
    b=1.3,
    title="PSI: стабильность распределения признака",
    time_limit_s=240,
)

# --------------------------------------------------------------------------- тип дрейфа

_DRIFT = {
    "covariate": "Сдвиг признаков (covariate shift): P(x) изменилось, связь x→y та же",
    "prior": "Сдвиг долей классов (prior / label shift): P(y) изменилось, P(x|y) прежнее",
    "concept": "Дрейф концепции (concept drift): та же картина признаков теперь означает другое y",
    "skew": "Расхождение обучения и прода (training-serving skew): признак считают по-разному",
    "pipeline": "Поломка данных в пайплайне: признак приходит испорченным",
}


def _gen_drift(rng: random.Random) -> Variant:
    region = rng.choice(("Казани", "Новосибирска", "Екатеринбурга", "Краснодара"))
    p1 = rng.choice((1, 2, 3))
    p2 = p1 * rng.choice((3, 4, 5))
    days = rng.choice((7, 14, 30))
    scenarios = [
        (
            f"Сервис запустили в {region}: средний возраст новых пользователей на "
            f"{rng.randint(8, 15)} лет моложе, чем в обучающей выборке. Для каждой возрастной "
            "группы связь признаков с откликом, судя по разметке, не изменилась.",
            "covariate",
        ),
        (
            f"Доля мошеннических операций выросла с {p1}% до {p2}% из-за атаки, но сами "
            "мошеннические и честные операции по признакам выглядят так же, как раньше.",
            "prior",
        ),
        (
            "Банк изменил правила кешбэка: клиенты с тем же поведением, которое раньше "
            "предвещало отток, теперь в основном остаются. Распределения признаков прежние.",
            "concept",
        ),
        (
            f"В обучении признак «средний чек» считали за {days * 2} дней в офлайн-витрине, "
            f"а онлайн-сервис считает его за последние {days} дней. Качество в проде сразу "
            "после запуска ниже, чем на валидации.",
            "skew",
        ),
        (
            f"После релиза соседней команды признак «{rng.choice(('доход', 'стаж', 'регион'))}» "
            f"в {rng.randint(30, 90)}% запросов приходит пустым (NaN), хотя пользователи "
            "его заполняют. Скоры модели резко сместились в один день.",
            "pipeline",
        ),
    ]
    text, correct = rng.choice(scenarios)
    return make_single_choice(
        rng,
        f"{text}\nКак точнее всего назвать то, что произошло?",
        _DRIFT[correct],
        [v for k, v in _DRIFT.items() if k != correct],
        explanation=f"Верно: {correct}.",
    )


DRIFT_TYPE = ItemTemplate(
    id="data_ml.drift_type",
    specialization="data_ml",
    topic="mlops",
    target_grade="senior",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_drift,
    a=1.2,
    b=1.2,
    title="Какой это дрейф",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- выпуск модели


def _gen_rollout(rng: random.Random) -> Variant:
    metric = rng.choice(("PR-AUC", "ROC-AUC", "MAE", "NDCG@10"))
    biz = rng.choice(("выручку на пользователя", "долю одобренных заявок", "конверсию в покупку"))
    pct = rng.choice((1, 5, 10))
    ms = rng.choice((50, 100, 200))
    days = rng.choice((3, 7))
    steps = [
        f"Сравнить новую модель с текущей офлайн на свежей отложенной выборке по {metric}",
        "Запустить в теневом режиме: модель считает предсказания на реальном трафике, "
        "но они не используются",
        f"По логам теневого режима сверить предсказания с текущей моделью и задержку "
        f"(p99 < {ms} мс)",
        f"Включить новую модель на {pct}% трафика (канарейка / A/B-тест)",
        f"Через {days} дн. проверить {biz} и статистическую значимость разницы",
        "Раскатить на 100% трафика, сохранив старую версию для быстрого отката",
    ]
    return make_ordering(
        rng,
        "Команда выпускает новую версию модели в прод. Расставьте шаги безопасного выпуска "
        "в правильном порядке.",
        steps,
        explanation="Офлайн → shadow → сверка → канарейка → решение по A/B → полная раскатка.",
    )


ROLLOUT = ItemTemplate(
    id="data_ml.model_rollout_order",
    specialization="data_ml",
    topic="mlops",
    target_grade="senior",
    format=ItemFormat.ORDERING,
    generator=_gen_rollout,
    a=1.1,
    b=1.0,
    title="Безопасный выпуск модели",
    time_limit_s=150,
)

TEMPLATES = [CRISP_DM, DRIFT_PSI, DRIFT_TYPE, ROLLOUT]
