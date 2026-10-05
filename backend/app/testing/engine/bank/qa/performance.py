"""QA — нагрузочное тестирование: виды тестов, перцентили, закон Литтла, узкое место."""

from __future__ import annotations

import math
import random

from ...templates import ItemFormat, ItemTemplate, NumericKey, Variant, make_single_choice
from ._common import dec_key, fmt_num, table

# --------------------------------------------------------------------------- виды тестов

_TYPES = {
    "load": "Нагрузочный тест (load) на ожидаемой нагрузке",
    "stress": "Стресс-тест (stress): нагрузка выше расчётной до отказа",
    "spike": "Тест резкого всплеска (spike)",
    "soak": "Тест стабильности (soak / endurance) — длительная нагрузка",
    "volume": "Объёмный тест (volume) — большие объёмы данных",
}


def _gen_load_types(rng: random.Random) -> Variant:
    rps = rng.choice((200, 500, 800, 1500))
    hours = rng.choice((8, 12, 24, 48))
    rows = rng.choice((50, 100, 300))
    scenarios = [
        (
            f"Убедиться, что сервис держит прогнозируемые на «чёрную пятницу» {rps} RPS "
            "с p95 не больше 300 мс.",
            "load",
        ),
        (
            f"Плавно поднимать нагрузку выше {rps} RPS, пока сервис не начнёт отвечать ошибками, "
            "и посмотреть, как он восстанавливается.",
            "stress",
        ),
        (
            f"За 10 секунд поднять нагрузку с {rps // 10} до {rps * 3} RPS — так бывает "
            "после push-рассылки — и сразу вернуть обратно.",
            "spike",
        ),
        (
            f"Держать обычную нагрузку {hours} ч подряд и следить за утечками памяти и ростом "
            "времени ответа.",
            "soak",
        ),
        (
            f"Наполнить базу {rows} млн заказов и проверить скорость поиска и отчётов.",
            "volume",
        ),
    ]
    text, correct = rng.choice(scenarios)
    return make_single_choice(
        rng,
        f"Цель теста: {text}\nКакой это вид теста производительности?",
        _TYPES[correct],
        [v for k, v in _TYPES.items() if k != correct],
        explanation=f"Верно: {_TYPES[correct]}.",
    )


LOAD_TYPES = ItemTemplate(
    id="qa.load_test_types",
    specialization="qa",
    topic="performance",
    target_grade="junior",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_load_types,
    a=1.1,
    b=-0.6,
    title="Виды тестов производительности",
    time_limit_s=90,
)

# --------------------------------------------------------------------------- перцентили


def nearest_rank(values: list[int], p: int) -> int:
    s = sorted(values)
    return s[math.ceil(p * len(s) / 100) - 1]


def _gen_percentile(rng: random.Random) -> Variant:
    n = rng.choice((10, 12, 15, 16, 20))
    values = rng.sample(range(80, 600), n - 2) + rng.sample(range(900, 3000), 2)
    rng.shuffle(values)
    q = rng.choice(("p", "p", "sla"))
    if q == "p":
        p = rng.choice((50, 75, 90, 95))
        value = nearest_rank(values, p)
        ask = (
            f"Посчитайте p{p} времени ответа методом nearest-rank: значение с номером "
            f"⌈{p}·n/100⌉ в списке, отсортированном по возрастанию."
        )
    else:
        sla = rng.choice(range(200, 600, 50))
        value = sum(1 for v in values if v > sla)
        ask = f"Сколько запросов не уложились в SLA {sla} мс (строго медленнее)?"
    return Variant(
        prompt=f"Нагрузочный тест: время ответа {n} запросов, мс. {ask}",
        key=NumericKey(value, 0),
        code=", ".join(map(str, values)),
        extra={"answer_type": "integer"},
        explanation=f"Отсортировано: {sorted(values)}; ответ {value}.",
    )


PERCENTILE = ItemTemplate(
    id="qa.response_percentile",
    specialization="qa",
    topic="performance",
    target_grade="middle",
    format=ItemFormat.NUMERIC,
    generator=_gen_percentile,
    a=1.2,
    b=0.1,
    title="Перцентили времени ответа",
    time_limit_s=180,
)

# --------------------------------------------------------------------------- закон Литтла


def _gen_little(rng: random.Random) -> Variant:
    r = rng.choice((0.2, 0.3, 0.5, 0.8, 1.0, 1.5, 2.0))
    z = rng.choice((1, 2, 3, 4, 5, 8, 10))
    q = rng.choice(("users", "throughput", "response"))
    head = (
        "Нагрузочный тест по закрытой модели: каждый виртуальный пользователь в цикле "
        "отправляет запрос, ждёт ответ и делает паузу (think time). Система в установившемся "
        "режиме."
    )
    if q == "users":
        x = rng.choice((20, 50, 100, 150, 200, 300))
        value: float = round(x * (r + z))
        text = (
            f"Время ответа {fmt_num(r)} с, пауза {z} с. Сколько виртуальных пользователей нужно, "
            f"чтобы получить {x} запросов в секунду?"
        )
        key = NumericKey(value, 0)
    elif q == "throughput":
        n = rng.choice((50, 100, 200, 300, 500, 1000))
        value = n / (r + z)
        text = (
            f"Пользователей {n}, время ответа {fmt_num(r)} с, пауза {z} с. Какую пропускную "
            "способность (запросов в секунду) покажет тест? Округлите до десятых."
        )
        key = dec_key(value, 1)
    else:
        x = rng.choice((20, 25, 40, 50, 100))
        n = round(x * (r + z))
        value = n / x - z
        text = (
            f"Пользователей {n}, пауза {z} с, тест показал {x} запросов в секунду. Каково "
            "среднее время ответа в секундах? Округлите до десятых."
        )
        key = dec_key(value, 1)
    return Variant(
        prompt=f"{head} {text}",
        key=key,
        extra={"answer_type": "decimal"},
        explanation=f"N = X · (R + Z); ответ {value:.3f}",
    )


LITTLE = ItemTemplate(
    id="qa.littles_law",
    specialization="qa",
    topic="performance",
    target_grade="senior",
    format=ItemFormat.NUMERIC,
    generator=_gen_little,
    a=1.3,
    b=1.2,
    title="Закон Литтла в нагрузочном тесте",
    time_limit_s=180,
)

# --------------------------------------------------------------------------- узкое место

_BOTTLENECKS = {
    "pool": "Исчерпан пул соединений приложения к базе данных",
    "app_cpu": "Не хватает CPU на серверах приложения",
    "db_cpu": "Узкое место — сама база данных (CPU БД)",
    "gc": "Нехватка памяти: частые долгие паузы сборщика мусора",
    "generator": "Упёрся генератор нагрузки, а не тестируемая система",
    "network": "Насыщен сетевой канал",
}


def _gen_bottleneck(rng: random.Random) -> Variant:
    kind = rng.choice(tuple(_BOTTLENECKS))
    pool = rng.choice((20, 30, 50))

    def r(a: int, b: int) -> str:
        return f"{rng.randint(a, b)}%"

    m = {
        "app_cpu": r(25, 55),
        "db_cpu": r(20, 50),
        "pool": f"{rng.randint(3, pool // 2)}/{pool}",
        "gc": f"{rng.randint(10, 60)} мс",
        "gen_cpu": r(20, 50),
        "net": f"{rng.randint(80, 300)} Мбит/с из 1000",
    }
    if kind == "pool":
        m["pool"] = f"{pool}/{pool}, потоки ждут соединение"
    elif kind == "app_cpu":
        m["app_cpu"] = r(95, 100)
    elif kind == "db_cpu":
        m["db_cpu"] = r(95, 100)
    elif kind == "gc":
        m["gc"] = f"{rng.randint(800, 2500)} мс, heap {rng.randint(95, 99)}%"
    elif kind == "generator":
        m["gen_cpu"] = r(98, 100)
    else:
        m["net"] = f"{rng.randint(940, 990)} Мбит/с из 1000"
    rps = rng.choice((400, 700, 1200, 2000))
    rows = [
        ["RPS", f"растёт до {rps} и дальше не растёт"],
        ["p95 времени ответа", f"{rng.randint(2, 9)}× от нормы"],
        ["CPU приложения", m["app_cpu"]],
        ["CPU базы данных", m["db_cpu"]],
        ["Пул соединений к БД (занято/всего)", m["pool"]],
        ["Паузы GC (макс.)", m["gc"]],
        ["CPU машины генератора нагрузки", m["gen_cpu"]],
        ["Сеть приложения", m["net"]],
    ]
    if kind == "generator":
        rows[1] = ["p95 времени ответа", "в норме"]
    return make_single_choice(
        rng,
        "При росте нагрузки RPS перестал расти. Метрики в этот момент — ниже. "
        "Что вероятнее всего ограничивает производительность?",
        _BOTTLENECKS[kind],
        [v for k, v in _BOTTLENECKS.items() if k != kind],
        code=table(["метрика", "значение"], rows),
        explanation=f"Узкое место: {kind}.",
    )


BOTTLENECK = ItemTemplate(
    id="qa.load_bottleneck",
    specialization="qa",
    topic="performance",
    target_grade="senior",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_bottleneck,
    a=1.3,
    b=1.1,
    title="Найти узкое место по метрикам",
    time_limit_s=180,
)

TEMPLATES = [LOAD_TYPES, PERCENTILE, LITTLE, BOTTLENECK]
