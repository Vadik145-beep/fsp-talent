"""QA — тестирование API: пагинация, идемпотентность, curl, контракт ответа, rate limit."""

from __future__ import annotations

import json
import math
import random
from typing import Any

from ...templates import ItemFormat, ItemTemplate, NumericKey, Variant, make_multi_choice
from ._common import table

_RES = ("orders", "users", "products", "tickets", "invoices", "reviews")

# --------------------------------------------------------------------------- пагинация


def _gen_pagination(rng: random.Random) -> Variant:
    res = rng.choice(_RES)
    limit = rng.choice((10, 20, 25, 50, 100))
    total = rng.randint(limit + 1, limit * 30)
    if rng.random() < 0.2:
        total = limit * rng.randint(2, 30)  # делится нацело — ловушка «последняя страница»
    pages = math.ceil(total / limit)
    q = rng.choice(("pages", "last", "offset", "page_items"))
    head = (
        f"GET /api/{res}?page=<номер>&limit={limit} возвращает записи постранично, "
        f"страницы нумеруются с 1. Всего в базе {total} записей."
    )
    if q == "pages":
        value, ask = pages, "Сколько страниц с данными вернёт API?"
    elif q == "last":
        value = total - (pages - 1) * limit
        ask = "Сколько записей будет на последней непустой странице?"
    elif q == "offset":
        p = rng.randint(2, pages)
        value = (p - 1) * limit
        ask = (
            f"Тот же список есть в варианте с offset: GET /api/{res}?offset=<n>&limit={limit}. "
            f"Какой offset передать, чтобы получить те же записи, что на странице {p}?"
        )
    else:
        p = rng.choice((pages, pages + 1, rng.randint(1, pages)))
        value = max(0, min(limit, total - (p - 1) * limit))
        ask = f"Сколько записей должно прийти в ответ на запрос страницы {p}?"
    return Variant(
        prompt=f"{head} {ask}",
        key=NumericKey(value, 0),
        extra={"answer_type": "integer"},
        explanation=f"Страниц {pages}; ответ {value}.",
    )


PAGINATION = ItemTemplate(
    id="qa.pagination_check",
    specialization="qa",
    topic="api_testing",
    target_grade="intern",
    format=ItemFormat.NUMERIC,
    generator=_gen_pagination,
    a=1.1,
    b=-1.3,
    title="Пагинация: ожидаемое число записей",
    time_limit_s=120,
)

# --------------------------------------------------------------------------- идемпотентность


def _gen_idempotent(rng: random.Random) -> Variant:
    res = rng.choice(_RES)
    rid = rng.randint(10, 99999)
    reqs = {
        "GET": (f"GET /api/{res}/{rid}", True, True),
        "HEAD": (f"HEAD /api/{res}/{rid}", True, True),
        "OPTIONS": (f"OPTIONS /api/{res}", True, True),
        "PUT": (f"PUT /api/{res}/{rid} с полным новым представлением объекта", True, False),
        "DELETE": (f"DELETE /api/{res}/{rid}", True, False),
        "POST": (f"POST /api/{res} с телом нового объекта", False, False),
        "PATCH": (
            f'PATCH /api/{res}/{rid} с телом {{"op": "increment", "field": "views"}}',
            False,
            False,
        ),
    }
    mode = rng.choice(("idempotent", "safe"))
    if mode == "idempotent":
        ask = (
            "Клиент не дождался ответа из-за таймаута и повторил запрос. Какие запросы по "
            "семантике HTTP идемпотентны, то есть повтор даёт то же состояние сервера, "
            "что и один вызов? Отметьте все."
        )
        good = [v[0] for v in reqs.values() if v[1]]
        bad = [v[0] for v in reqs.values() if not v[1]]
    else:
        ask = (
            "Какие запросы по семантике HTTP безопасные (safe), то есть не должны менять "
            "состояние на сервере? Отметьте все."
        )
        good = [v[0] for v in reqs.values() if v[2]]
        bad = [v[0] for v in reqs.values() if not v[2]]
    correct = rng.sample(good, rng.randint(2, min(4, len(good))))
    wrong = rng.sample(bad, rng.randint(2, min(3, len(bad))))
    return make_multi_choice(
        rng,
        ask,
        correct,
        wrong,
        extra={"min_choices": 1},
        explanation=f"Режим {mode}: верные — {', '.join(correct)}.",
    )


IDEMPOTENT = ItemTemplate(
    id="qa.idempotent_methods",
    specialization="qa",
    topic="api_testing",
    target_grade="junior",
    format=ItemFormat.MULTI_CHOICE,
    generator=_gen_idempotent,
    a=1.3,
    b=-0.4,
    title="Идемпотентные и безопасные методы",
    time_limit_s=120,
)

# --------------------------------------------------------------------------- метод curl


def curl_scenarios(rng: random.Random, url: str) -> list[tuple[str, str]]:
    v = rng.choice(("anna", "test", "qa42", "boris"))
    f = rng.choice(("report.pdf", "photo.png", "data.csv"))
    return [
        (f"curl {url}", "GET"),
        (f"curl -d 'name={v}' {url}", "POST"),
        (f"curl -I {url}", "HEAD"),
        (
            f"curl -X PUT -H 'Content-Type: application/json' -d '{{\"name\": \"{v}\"}}' {url}",
            "PUT",
        ),
        (f"curl -F 'file=@{f}' {url}", "POST"),
        (f"curl -G -d 'q={v}' {url}", "GET"),
        (f"curl -X DELETE {url}", "DELETE"),
        (f"curl --data-urlencode 'comment={v} ok' {url}", "POST"),
        (f"curl -T {f} {url}", "PUT"),
        (f"curl -X PATCH -d 'status=done' {url}", "PATCH"),
        (f"curl -s -o /dev/null -w '%{{http_code}}' {url}", "GET"),
    ]


def _gen_curl(rng: random.Random) -> Variant:
    res = rng.choice(_RES)
    host = rng.choice(("api.example.ru", "staging.shop.local", "test-api.internal"))
    url = f"https://{host}/v1/{res}/{rng.randint(1, 9999)}"
    cmd, method = rng.choice(curl_scenarios(rng, url))
    return Variant(
        prompt=(
            "Какой HTTP-метод отправит эта команда curl? Ответ — название метода "
            f"латиницей, например OPTIONS.\n{cmd}"
        ),
        key=(method,),
        extra={"answer_type": "text", "max_length": 10},
        explanation=f"Метод: {method}.",
    )


CURL_METHOD = ItemTemplate(
    id="qa.curl_method",
    specialization="qa",
    topic="api_testing",
    target_grade="junior",
    format=ItemFormat.SHORT_TEXT,
    generator=_gen_curl,
    a=1.2,
    b=-0.3,
    title="Какой метод отправит curl",
    time_limit_s=90,
)

# --------------------------------------------------------------------------- контракт ответа

_CONTRACTS = (
    (
        "GET /api/users/{id}",
        {
            "id": "int",
            "email": "str",
            "status": ("enum", ("active", "blocked", "pending")),
            "age": "nonneg",
            "created_at": "datetime",
            "tags": "str_list",
            "bio": "nullable",
            "is_verified": "bool",
        },
    ),
    (
        "GET /api/orders/{id}",
        {
            "order_id": "int",
            "customer_email": "str",
            "state": ("enum", ("new", "paid", "shipped", "delivered")),
            "quantity": "nonneg",
            "paid_at": "datetime",
            "labels": "str_list",
            "comment": "nullable",
            "is_gift": "bool",
        },
    ),
)

_KIND_TEXT = {
    "int": ("integer", "да", "—"),
    "str": ("string", "да", "непустая строка"),
    "nonneg": ("integer", "да", "≥ 0"),
    "datetime": ("string", "да", "ISO 8601: YYYY-MM-DDTHH:MM:SSZ"),
    "str_list": ("array of string", "да", "—"),
    "nullable": ("string или null", "нет", "—"),
    "bool": ("boolean", "да", "—"),
}


def _valid_value(rng: random.Random, kind: Any, name: str) -> Any:
    if isinstance(kind, tuple):
        return rng.choice(kind[1])
    return {
        "int": rng.randint(1, 99999),
        "str": f"{rng.choice(('anna', 'boris', 'kira'))}{rng.randint(1, 99)}@example.ru",
        "nonneg": rng.randint(0, 90),
        "datetime": f"2026-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}T"
        f"{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}:00Z",
        "str_list": rng.sample(["new", "vip", "promo", "b2b", "test"], rng.randint(1, 3)),
        "nullable": rng.choice((None, "Привет!")),
        "bool": rng.choice((True, False)),
    }[kind]


def _invalid_value(rng: random.Random, kind: Any, valid: Any) -> tuple[bool, Any]:
    """(удалить поле?, неверное значение)."""
    if isinstance(kind, tuple):
        return False, rng.choice(("deleted", "archived", "ACTIVE", "unknown"))
    if kind == "int":
        return False, str(valid)
    if kind == "str":
        return rng.random() < 0.5, ""
    if kind == "nonneg":
        return False, -rng.randint(1, 9)
    if kind == "datetime":
        return False, rng.choice(("12.03.2026 10:00", "2026/03/12", "вчера"))
    if kind == "str_list":
        return False, [*valid, rng.randint(1, 9)]
    if kind == "bool":
        return False, rng.choice(("true", "yes", 1))
    raise ValueError(kind)


def _gen_contract(rng: random.Random) -> Variant:
    endpoint, fields = rng.choice(_CONTRACTS)
    names = list(fields)
    breakable = [n for n in names if fields[n] != "nullable"]
    broken = set(rng.sample(breakable, rng.randint(1, 3)))
    body: dict[str, Any] = {}
    for n in names:
        valid = _valid_value(rng, fields[n], n)
        if n in broken:
            drop, bad = _invalid_value(rng, fields[n], valid)
            if not drop:
                body[n] = bad
        else:
            body[n] = valid
    extra_field = rng.choice(("nickname", "source", "version"))
    with_extra = rng.random() < 0.6
    if with_extra:
        body[extra_field] = rng.choice(("web", "v2", "ann"))
    rows = []
    for n in names:
        kind = fields[n]
        if isinstance(kind, tuple):
            rows.append([n, "string", "да", "одно из: " + ", ".join(kind[1])])
        else:
            rows.append([n, *_KIND_TEXT[str(kind)]])
    contract = table(["поле", "тип", "обязательное", "ограничения"], rows)
    shown = rng.sample([n for n in names if n not in broken], rng.randint(1, 3))
    wrong_opts = [f"«{n}»" for n in shown]
    if with_extra:
        wrong_opts.append(f"«{extra_field}» (поля нет в контракте)")
    resp = json.dumps(body, ensure_ascii=False, indent=2)
    return make_multi_choice(
        rng,
        f"Контракт ответа {endpoint}: лишние поля допустимы, необязательные поля можно не "
        "передавать. Сравните ответ с контрактом и отметьте все поля, которые его нарушают.",
        [f"«{n}»" for n in sorted(broken)],
        wrong_opts,
        code=f"{contract}\n\nОтвет:\n{resp}",
        extra={"min_choices": 1, "language": "json"},
        explanation="Нарушения: " + ", ".join(sorted(broken)),
    )


JSON_CONTRACT = ItemTemplate(
    id="qa.json_contract",
    specialization="qa",
    topic="api_testing",
    target_grade="middle",
    format=ItemFormat.MULTI_CHOICE,
    generator=_gen_contract,
    a=1.4,
    b=0.4,
    title="Ответ API против контракта",
    time_limit_s=240,
)

# --------------------------------------------------------------------------- rate limit


def bucket_rejections(times10: list[int], capacity: int, refill: int) -> int:
    tokens, last_sec, rejected = capacity, 0, 0
    for t in times10:
        sec = t // 10
        if sec > last_sec:
            tokens = min(capacity, tokens + refill * (sec - last_sec))
            last_sec = sec
        if tokens >= 1:
            tokens -= 1
        else:
            rejected += 1
    return rejected


def window_rejections(times10: list[int], limit: int, window: int) -> int:
    accepted: list[int] = []
    rejected = 0
    for t in times10:
        recent = [a for a in accepted if a > t - window * 10]
        if len(recent) < limit:
            accepted.append(t)
        else:
            rejected += 1
    return rejected


def _gen_rate_limit(rng: random.Random) -> Variant:
    mode = rng.choice(("bucket", "window"))
    while True:
        n = rng.randint(8, 13)
        times10 = sorted(rng.sample(range(1, rng.randint(40, 90)), n))
        if mode == "bucket":
            cap, refill = rng.randint(3, 5), rng.randint(1, 2)
            ans = bucket_rejections(times10, cap, refill)
            rule = (
                f"Token bucket: ёмкость {cap} токенов, в начале ведро полное. В моменты "
                f"t = 1, 2, 3, … с добавляется {refill} ток. (но не больше ёмкости), запрос "
                "в тот же момент уже видит пополнение. Каждый запрос тратит 1 токен; "
                "нет токена — ответ 429."
            )
        else:
            limit, window = rng.randint(3, 5), rng.choice((2, 3, 5))
            accepted: list[int] = []
            ties = False
            for t in times10:
                if any(a == t - window * 10 for a in accepted):
                    ties = True
                if len([a for a in accepted if a > t - window * 10]) < limit:
                    accepted.append(t)
            if ties:
                continue
            ans = window_rejections(times10, limit, window)
            rule = (
                f"Скользящее окно: запрос принимается, если за последние {window} с до него "
                f"принято меньше {limit} запросов; отклонённые (429) не считаются."
            )
        if 1 <= ans <= n - 2:
            break
    stamps = ", ".join(f"{t / 10:.1f}" for t in times10)
    return Variant(
        prompt=(
            f"Нагрузочный скрипт проверяет ограничение частоты запросов API. {rule} "
            f"Запросы приходят в моменты (секунды): {stamps}. Сколько запросов получат 429?"
        ),
        key=NumericKey(ans, 0),
        extra={"answer_type": "integer"},
        explanation=f"{mode}: отклонено {ans}.",
    )


RATE_LIMIT = ItemTemplate(
    id="qa.rate_limit",
    specialization="qa",
    topic="api_testing",
    target_grade="senior",
    format=ItemFormat.NUMERIC,
    generator=_gen_rate_limit,
    a=1.4,
    b=1.3,
    title="Сколько запросов получат 429",
    time_limit_s=300,
)

TEMPLATES = [PAGINATION, IDEMPOTENT, CURL_METHOD, JSON_CONTRACT, RATE_LIMIT]
