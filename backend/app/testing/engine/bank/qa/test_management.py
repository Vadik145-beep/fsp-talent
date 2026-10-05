"""QA — управление тестированием: статистика прогона, критерии выхода, метрики, регресс."""

from __future__ import annotations

import random

from ...templates import (
    ItemFormat,
    ItemTemplate,
    NumericKey,
    Variant,
    make_multi_choice,
    make_single_choice,
)
from ._common import dec_key

# --------------------------------------------------------------------------- статистика прогона


def _gen_run_stats(rng: random.Random) -> Variant:
    passed = rng.randint(40, 400)
    failed = rng.randint(1, 40)
    blocked = rng.randint(0, 25)
    skipped = rng.randint(0, 20)
    not_run = rng.randint(0, 30)
    total = passed + failed + blocked + skipped + not_run
    q = rng.choice(("pass_rate", "executed_share", "not_executed"))
    if q == "pass_rate":
        value = passed / (passed + failed) * 100
        ask = "Какой процент выполненных тестов прошёл? Округлите до десятых."
        key = dec_key(value, 1)
    elif q == "executed_share":
        value = (passed + failed) / total * 100
        ask = "Какой процент запланированных тестов выполнен? Округлите до десятых."
        key = dec_key(value, 1)
    else:
        value = blocked + skipped + not_run
        ask = "Сколько запланированных тестов не было выполнено?"
        key = NumericKey(value, 0)
    return Variant(
        prompt=(
            f"Итог регрессионного прогона: запланировано {total} тестов; прошли {passed}, "
            f"упали {failed}, заблокированы {blocked}, пропущены (skipped) {skipped}, "
            f"не запускались {not_run}. Выполненными считаются только прошедшие и упавшие. "
            f"{ask}"
        ),
        key=key,
        extra={"answer_type": "decimal" if q != "not_executed" else "integer"},
        explanation=f"{q} = {value:.3f}",
    )


RUN_STATS = ItemTemplate(
    id="qa.test_run_stats",
    specialization="qa",
    topic="test_management",
    target_grade="intern",
    format=ItemFormat.NUMERIC,
    generator=_gen_run_stats,
    a=1.0,
    b=-1.3,
    title="Статистика тестового прогона",
    time_limit_s=120,
)

# --------------------------------------------------------------------------- критерии выхода


def _gen_release(rng: random.Random) -> Variant:
    need_pass = rng.choice((90, 95, 98))
    max_crit = rng.choice((0, 1, 2, 3))
    need_cov = rng.choice((80, 85, 90, 95))
    fail_which = rng.choice((None, None, "pass", "blockers", "critical", "coverage"))
    executed = rng.randint(200, 900)
    if fail_which == "pass":
        passed = int(executed * (need_pass - rng.uniform(0.5, 4)) / 100)
    else:
        passed = min(
            executed, int(executed * (need_pass + rng.uniform(0.2, 100 - need_pass)) / 100) + 1
        )
    blockers = rng.randint(1, 2) if fail_which == "blockers" else 0
    critical = (
        max_crit + rng.randint(1, 3) if fail_which == "critical" else rng.randint(0, max_crit)
    )
    reqs = rng.randint(40, 160)
    if fail_which == "coverage":
        covered = int(reqs * (need_cov - rng.uniform(1, 8)) / 100)
    else:
        covered = min(reqs, int(reqs * need_cov / 100) + rng.randint(1, 5))
    status = {
        "pass": passed / executed * 100 >= need_pass,
        "blockers": blockers == 0,
        "critical": critical <= max_crit,
        "coverage": covered / reqs * 100 >= need_cov,
    }
    failing = [k for k, ok in status.items() if not ok]
    texts = {
        "pass": f"Не выполнен критерий: доля пройденных тестов ≥ {need_pass}%",
        "blockers": "Не выполнен критерий: нет открытых блокирующих дефектов",
        "critical": f"Не выполнен критерий: открытых критических дефектов не больше {max_crit}",
        "coverage": f"Не выполнен критерий: покрытие требований тестами ≥ {need_cov}%",
    }
    ok_text = "Все критерии выполнены — можно выпускать"
    correct = texts[failing[0]] if failing else ok_text
    criteria = "\n".join(
        [
            f"1. Пройдено не меньше {need_pass}% выполненных тестов.",
            "2. Нет открытых блокирующих (blocker) дефектов.",
            f"3. Открытых критических (critical) дефектов — не больше {max_crit}.",
            f"4. Тестами покрыто не меньше {need_cov}% требований.",
            "",
            f"Факт: выполнено {executed} тестов, пройдено {passed}; открыто blocker — "
            f"{blockers}, critical — {critical}; покрыто требований {covered} из {reqs}.",
        ]
    )
    return make_single_choice(
        rng,
        "Критерии выхода из тестирования релиза и фактическое состояние — ниже. "
        "Какое решение верное?",
        correct,
        [ok_text, *texts.values()],
        code=criteria,
        explanation=f"Не выполнены: {failing or 'нет'}.",
    )


RELEASE = ItemTemplate(
    id="qa.release_readiness",
    specialization="qa",
    topic="test_management",
    target_grade="middle",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_release,
    a=1.1,
    b=0.2,
    title="Критерии выхода: можно ли выпускать",
    time_limit_s=180,
)

# --------------------------------------------------------------------------- метрики дефектов


def _gen_defect_metrics(rng: random.Random) -> Variant:
    q = rng.choice(("dre", "density", "reopen", "leakage"))
    before = rng.randint(30, 300)
    after = rng.randint(1, 40)
    if q == "dre":
        value = before / (before + after) * 100
        text = (
            f"До релиза команда нашла {before} дефектов, после релиза пользователи сообщили "
            f"ещё о {after}. Посчитайте эффективность устранения дефектов (DRE), в процентах."
        )
        decimals = 1
    elif q == "leakage":
        value = after / (before + after) * 100
        text = (
            f"До релиза найдено {before} дефектов, после релиза — {after}. Какая доля всех "
            "дефектов «утекла» в прод (defect leakage), в процентах?"
        )
        decimals = 1
    elif q == "density":
        loc = rng.choice(range(8_000, 160_001, 2_000))
        value = before / (loc / 1000)
        text = (
            f"В модуле {loc // 1000} тыс. строк кода, за цикл тестирования в нём найдено "
            f"{before} дефектов. Какова плотность дефектов на 1000 строк (KLOC)?"
        )
        decimals = 2
    else:
        fixed = rng.randint(40, 300)
        reopened = rng.randint(1, max(2, fixed // 5))
        value = reopened / fixed * 100
        text = (
            f"За спринт разработчики закрыли как исправленные {fixed} дефектов, из них "
            f"{reopened} тестировщики переоткрыли после проверки. Какая доля переоткрытых "
            "дефектов (reopen rate), в процентах?"
        )
        decimals = 1
    word = "десятых" if decimals == 1 else "сотых"
    return Variant(
        prompt=f"{text} Округлите до {word}.",
        key=dec_key(value, decimals),
        extra={"answer_type": "decimal", "decimals": decimals},
        explanation=f"{q} = {value:.4f}",
    )


DEFECT_METRICS = ItemTemplate(
    id="qa.defect_metrics",
    specialization="qa",
    topic="test_management",
    target_grade="middle",
    format=ItemFormat.NUMERIC,
    generator=_gen_defect_metrics,
    a=1.1,
    b=0.0,
    title="Метрики дефектов: DRE, плотность, переоткрытия",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- объём регресса

_MODULES = (
    "Каталог",
    "Цены",
    "Склад",
    "Корзина",
    "Платежи",
    "Заказы",
    "Доставка",
    "Уведомления",
    "Отчёты",
    "Профиль",
)


def affected_modules(deps: dict[str, list[str]], changed: str) -> set[str]:
    """Модуль и все, кто от него зависит (прямо или через другие модули)."""
    out = {changed}
    grew = True
    while grew:
        grew = False
        for m, uses in deps.items():
            if m not in out and any(u in out for u in uses):
                out.add(m)
                grew = True
    return out


def _gen_regression(rng: random.Random) -> Variant:
    while True:
        mods = rng.sample(_MODULES, rng.randint(6, 7))
        deps: dict[str, list[str]] = {}
        for i, m in enumerate(mods):
            earlier = mods[:i]
            k = rng.randint(0, min(2, len(earlier)))
            deps[m] = rng.sample(earlier, k)
        changed = rng.choice(mods[:4])
        hit = affected_modules(deps, changed)
        if 3 <= len(hit) <= len(mods) - 2:
            break
    lines = [f"«{m}» использует: " + (", ".join(f"«{u}»" for u in deps[m]) or "—") for m in mods]
    suites = {m: f"Набор тестов модуля «{m}»" for m in mods}
    return make_multi_choice(
        rng,
        f"В релизе изменили только модуль «{changed}». Зависимости модулей — ниже "
        "(«A использует B» значит, что изменение B может сломать A). Отметьте все наборы "
        "тестов, которые нужно прогнать в регрессе.",
        [suites[m] for m in mods if m in hit],
        [suites[m] for m in mods if m not in hit],
        code="\n".join(lines),
        extra={"min_choices": 1},
        explanation="Затронуты: " + ", ".join(sorted(hit)),
    )


REGRESSION_SCOPE = ItemTemplate(
    id="qa.regression_scope",
    specialization="qa",
    topic="test_management",
    target_grade="senior",
    format=ItemFormat.MULTI_CHOICE,
    generator=_gen_regression,
    a=1.2,
    b=1.0,
    title="Объём регресса по зависимостям",
    time_limit_s=210,
)

TEMPLATES = [RUN_STATS, RELEASE, DEFECT_METRICS, REGRESSION_SCOPE]
