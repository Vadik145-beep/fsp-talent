"""DevOps — мониторинг и SLO: бюджет ошибок, PromQL, скорость сжигания бюджета."""

from __future__ import annotations

import random

from ...templates import ItemFormat, ItemTemplate, NumericKey, Variant, make_single_choice
from ._common import dec_key, fmt_num

# --------------------------------------------------------------------------- бюджет ошибок


def _gen_budget(rng: random.Random) -> Variant:
    slo = rng.choice((99.0, 99.5, 99.9, 99.95, 99.99))
    days = rng.choice((7, 28, 30))
    q = rng.choice(("downtime", "remaining", "requests"))
    budget_min = days * 24 * 60 * (100 - slo) / 100
    if q == "downtime":
        value = budget_min
        ask = (
            f"SLO доступности сервиса — {fmt_num(slo)}% за скользящие {days} дней. Сколько минут "
            "полного простоя допускает бюджет ошибок за этот период? Округлите до десятых."
        )
        key = dec_key(value, 1)
    elif q == "remaining":
        spent = round(budget_min * rng.uniform(0.1, 0.9), 1)
        value = (budget_min - spent) / budget_min * 100
        ask = (
            f"SLO доступности — {fmt_num(slo)}% за {days} дней. За период уже было "
            f"{fmt_num(spent)} мин полного простоя. "
            "Какая доля бюджета ошибок осталась, в процентах? "
            "Округлите до десятых."
        )
        key = dec_key(value, 1)
    else:
        total = rng.choice((2, 5, 12, 40, 150)) * 1_000_000
        value = total * (100 - slo) / 100
        ask = (
            f"SLO: {fmt_num(slo)}% запросов за {days} дней обрабатываются успешно. Ожидается "
            f"{total:,} запросов за период. Сколько неуспешных запросов допускает бюджет ошибок?"
        ).replace(",", " ")
        key = NumericKey(round(value), 0.5)
    return Variant(
        prompt=ask,
        key=key,
        extra={"answer_type": "decimal"},
        explanation=f"Бюджет = (1 − SLO) · период; ответ {value:.3f}",
    )


ERROR_BUDGET = ItemTemplate(
    id="devops.error_budget",
    specialization="devops",
    topic="monitoring",
    target_grade="middle",
    format=ItemFormat.NUMERIC,
    generator=_gen_budget,
    a=1.3,
    b=0.2,
    title="Бюджет ошибок по SLO",
    time_limit_s=180,
)

# --------------------------------------------------------------------------- PromQL


def _gen_promql(rng: random.Random) -> Variant:
    job = rng.choice(("api", "checkout", "auth", "gateway"))
    w = rng.choice(("1m", "5m", "10m"))
    qn = rng.choice(("0.95", "0.99", "0.9"))
    total = f'http_requests_total{{job="{job}"}}'
    err = f'http_requests_total{{job="{job}", code=~"5.."}}'
    bucket = f'http_request_duration_seconds_bucket{{job="{job}"}}'
    tasks = [
        (
            f"Сколько запросов в секунду в среднем обрабатывает сервис {job} (по всем подам)?",
            f"sum(rate({total}[{w}]))",
            [f"sum({total})", f"rate(sum({total}))", f"avg({total}[{w}])"],
        ),
        (
            f"Какая доля запросов к {job} завершается ошибкой 5xx?",
            f"sum(rate({err}[{w}])) / sum(rate({total}[{w}]))",
            [
                f"sum({err}) / sum({total})",
                f"sum(rate({err}[{w}]))",
                f"count({err}) / count({total})",
            ],
        ),
        (
            f"Каков {qn}-квантиль времени ответа {job} по всем подам (гистограмма)?",
            f"histogram_quantile({qn}, sum by (le) (rate({bucket}[{w}])))",
            [
                f"histogram_quantile({qn}, rate({bucket}[{w}]))",
                f"quantile({qn}, rate({bucket}[{w}]))",
                f"avg(histogram_quantile({qn}, sum by (pod) (rate({bucket}[{w}]))))",
            ],
        ),
        (
            f"Сколько раз за последний час перезапускались контейнеры в namespace {job}?",
            f'sum(increase(kube_pod_container_status_restarts_total{{namespace="{job}"}}[1h]))',
            [
                f'sum(kube_pod_container_status_restarts_total{{namespace="{job}"}})',
                f'sum(rate(kube_pod_container_status_restarts_total{{namespace="{job}"}}[1h]))',
                f'count(kube_pod_container_status_restarts_total{{namespace="{job}"}} > 0)',
            ],
        ),
    ]
    task, correct, wrong = rng.choice(tasks)
    return make_single_choice(
        rng,
        f"Счётчики Prometheus монотонно растут. Какой запрос PromQL отвечает на вопрос: {task}",
        correct,
        wrong,
        extra={"language": "promql"},
        explanation=f"Верно: {correct}",
    )


PROMQL = ItemTemplate(
    id="devops.promql_query",
    specialization="devops",
    topic="monitoring",
    target_grade="middle",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_promql,
    a=1.4,
    b=0.6,
    title="Запрос PromQL под вопрос",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- burn rate


def _gen_burn(rng: random.Random) -> Variant:
    slo = rng.choice((99.0, 99.5, 99.9))
    days = 30
    err = rng.choice((0.2, 0.5, 1.0, 1.44, 2.0, 3.0, 5.0, 7.2))
    while err >= (100 - slo) * 50 or err <= (100 - slo):
        err = rng.choice((0.2, 0.5, 1.0, 1.44, 2.0, 3.0, 5.0, 7.2, 10.0, 14.4))
    burn = err / (100 - slo)
    q = rng.choice(("burn", "hours", "spent"))
    head = (
        f"SLO: {fmt_num(slo)}% успешных запросов за {days} дней. За последний час доля ошибок — "
        f"{fmt_num(err)}%."
    )
    if q == "burn":
        value, ask = burn, "Какова скорость сжигания бюджета ошибок (burn rate)?"
    elif q == "hours":
        value = days * 24 / burn
        ask = (
            "За сколько часов при такой доле ошибок сгорит весь бюджет ошибок периода, "
            "если он был полный?"
        )
    else:
        value = burn / (days * 24) * 100
        ask = "Какой процент месячного бюджета ошибок сгорел за этот час?"
    return Variant(
        prompt=f"{head} {ask} Округлите до десятых.",
        key=dec_key(value, 1),
        extra={"answer_type": "decimal", "decimals": 1},
        explanation=f"burn = {fmt_num(err)} / {fmt_num(100 - slo)} = {burn:.3f}; ответ {value:.3f}",
    )


BURN_RATE = ItemTemplate(
    id="devops.burn_rate",
    specialization="devops",
    topic="monitoring",
    target_grade="senior",
    format=ItemFormat.NUMERIC,
    generator=_gen_burn,
    a=1.4,
    b=1.4,
    title="Скорость сжигания бюджета ошибок",
    time_limit_s=210,
)

TEMPLATES = [ERROR_BUDGET, PROMQL, BURN_RATE]
