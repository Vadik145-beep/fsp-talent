"""QA: граничные значения (multi_choice), ожидаемый HTTP-код (short_text)."""

from __future__ import annotations

import random

from ..templates import ItemFormat, ItemTemplate, Variant, make_multi_choice

# --------------------------------------------------------------------------- граничные значения

_FIELDS = (
    ("Возраст клиента", "лет", (14, 21), (60, 80)),
    ("Количество товаров в корзине", "шт.", (1, 5), (20, 99)),
    ("Длина пароля", "символов", (6, 12), (20, 64)),
    ("Сумма перевода в рублях (целое)", "₽", (10, 500), (5000, 150000)),
    ("Число гостей в бронировании", "чел.", (1, 2), (8, 30)),
    ("Срок кредита", "мес.", (3, 12), (36, 120)),
)


def _gen_boundaries(rng: random.Random) -> Variant:
    name, unit, lo_range, hi_range = rng.choice(_FIELDS)
    lo = rng.randint(*lo_range)
    hi = rng.randint(max(hi_range[0], lo + 6), max(hi_range[1], lo + 10))
    three = rng.random() < 0.4
    mid = (lo + hi) // 2
    if three:
        correct = [lo - 1, lo, lo + 1, hi - 1, hi, hi + 1]
        wrong_pool = [lo - 2, lo + 2, mid, hi - 2, hi + 2]
        n_wrong = rng.randint(2, 3)
        method = "трёхточечным методом (значение на границе и по одному с каждой стороны)"
    else:
        correct = [lo - 1, lo, hi, hi + 1]
        wrong_pool = [lo - 2, lo + 1, mid, hi - 1, hi + 2]
        n_wrong = rng.randint(2, 4)
        method = "двухточечным методом (значение на границе и ближайшее за ней)"
    wrong = [w for w in rng.sample(wrong_pool, n_wrong) if w not in correct]
    # порядок случайный: позиции верных ответов не повторяются от варианта к варианту
    return make_multi_choice(
        rng,
        f"Поле «{name}» принимает целые значения от {lo} до {hi} {unit} включительно. "
        f"Отметьте все значения, которые нужно проверить {method}.",
        [str(v) for v in correct],
        [str(v) for v in dict.fromkeys(wrong)],
        explanation="Граничные значения: " + ", ".join(map(str, correct)),
    )


BOUNDARY_VALUES = ItemTemplate(
    id="qa.boundary_values",
    specialization="qa",
    topic="test_design",
    target_grade="junior",
    format=ItemFormat.MULTI_CHOICE,
    generator=_gen_boundaries,
    a=1.3,
    b=-0.8,
    title="Анализ граничных значений",
    time_limit_s=120,
)

# --------------------------------------------------------------------------- HTTP-коды

_RESOURCES = (
    ("заказ", "заказа", "orders"),
    ("пользователь", "пользователя", "users"),
    ("товар", "товара", "products"),
    ("платёж", "платежа", "payments"),
    ("отзыв", "отзыва", "reviews"),
    ("тикет", "тикета", "tickets"),
    ("счёт", "счёта", "invoices"),
)
_ROLES = ("viewer", "guest", "support", "analyst")
_FIELDS_REQ = ("email", "title", "amount", "phone", "quantity")


def _gen_http(rng: random.Random) -> Variant:
    nom, gen, path = rng.choice(_RESOURCES)
    rid = rng.randint(10, 99999)
    scenarios: list[tuple[str, tuple[str, ...]]] = [
        (f"GET /api/{path}/{rid} — {gen} с id={rid} нет в базе.", ("404", "404 not found")),
        (f"POST /api/{path} — новый {nom} успешно создан.", ("201", "201 created")),
        (
            f"GET /api/{path} отправлен без заголовка Authorization.",
            ("401", "401 unauthorized"),
        ),
        (
            f"DELETE /api/{path}/{rid} от пользователя с ролью «{rng.choice(_ROLES)}», "
            "у которой нет права удалять. Пользователь аутентифицирован.",
            ("403", "403 forbidden"),
        ),
        (
            f"DELETE /api/{path}/{rid} выполнен успешно, тело ответа пустое.",
            ("204", "204 no content"),
        ),
        (
            f"Клиент отправил {rng.choice((61, 120, 300))} запросов к /api/{path} за минуту "
            "при лимите 60.",
            ("429", "429 too many requests"),
        ),
        (
            f"PUT /api/{path}/{rid} — версия {gen} на сервере изменилась, пока клиент "
            "редактировал (конфликт версий).",
            ("409", "409 conflict"),
        ),
        (
            f"Эндпоинт /api/{path} поддерживает только GET и POST, а клиент прислал PATCH.",
            ("405", "405 method not allowed"),
        ),
        (
            f"POST /api/{path} — в JSON нет обязательного поля «{rng.choice(_FIELDS_REQ)}».",
            ("400", "400 bad request", "422", "422 unprocessable entity"),
        ),
        (
            f"GET /api/{path}/{rid} — сервис упал с необработанным исключением.",
            ("500", "500 internal server error"),
        ),
    ]
    situation, accepted = rng.choice(scenarios)
    return Variant(
        prompt=(
            "Вы тестируете REST API. Какой HTTP-код ответа правильный в этой ситуации? "
            f"Ответ — трёхзначное число.\n{situation}"
        ),
        key=accepted,
        extra={"answer_type": "text", "max_length": 40},
        explanation=f"Ожидается {accepted[0]}.",
    )


HTTP_STATUS = ItemTemplate(
    id="qa.http_status",
    specialization="qa",
    topic="api_testing",
    target_grade="intern",
    format=ItemFormat.SHORT_TEXT,
    generator=_gen_http,
    a=1.1,
    b=-1.4,
    title="Ожидаемый HTTP-код",
    time_limit_s=90,
)

TEMPLATES = [BOUNDARY_VALUES, HTTP_STATUS]
