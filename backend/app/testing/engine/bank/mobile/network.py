"""Mobile / сеть и офлайн: повторы с экспоненциальной задержкой, HTTP-кэш (max-age, ETag, 304)."""

from __future__ import annotations

import random

from ...templates import ItemFormat, ItemTemplate, NumericKey, Variant

# --------------------------------------------------------------------------- retry с backoff


def backoff_delays(times: int, initial: int, max_delay: int, factor: float) -> list[int]:
    """Задержки между попытками в функции retry (как в коде задачи)."""
    delays: list[int] = []
    current = initial
    for _ in range(times - 1):
        delays.append(current)
        current = min(int(current * factor), max_delay)
    return delays


def _gen_backoff(rng: random.Random) -> Variant:
    while True:
        times = rng.randint(3, 6)
        initial = rng.choice((100, 200, 250, 300, 400, 500))
        factor = rng.choice((1.5, 2.0, 2.0, 2.5, 3.0))
        max_delay = rng.choice((800, 1000, 1500, 2000, 3000, 5000))
        delays = backoff_delays(times, initial, max_delay, factor)
        ask = rng.choice(("total", "total", "nth"))
        capped = any(d == max_delay for d in delays)
        if not capped and rng.random() < 0.6:
            continue  # чаще берём варианты, где срабатывает потолок
        if ask == "total":
            value = sum(delays)
            question = (
                "Сервер всё время отвечает ошибкой (block() каждый раз бросает IOException). "
                "Сколько миллисекунд суммарно корутина проведёт в delay, прежде чем retry "
                "выбросит исключение? Время самих запросов не учитывайте."
            )
        else:
            k = rng.randint(2, times - 1)
            value = delays[k - 1]
            question = (
                "Сервер всё время отвечает ошибкой. Какой будет задержка (в мс) "
                f"после {k}-й неудачной попытки перед попыткой {k + 1}?"
            )
        break
    fs = f"{factor:.1f}"
    code = "\n".join(
        [
            "suspend fun <T> retry(",
            f"    times: Int = {times},",
            f"    initialDelay: Long = {initial},",
            f"    maxDelay: Long = {max_delay},",
            f"    factor: Double = {fs},",
            "    block: suspend () -> T,",
            "): T {",
            "    var currentDelay = initialDelay",
            "    repeat(times - 1) {",
            "        try {",
            "            return block()",
            "        } catch (e: IOException) {",
            "            // запишем в лог и попробуем ещё раз",
            "        }",
            "        delay(currentDelay)",
            "        currentDelay = (currentDelay * factor).toLong().coerceAtMost(maxDelay)",
            "    }",
            "    return block() // последняя попытка",
            "}",
        ]
    )
    return Variant(
        prompt=f"Функция повтора запроса (Kotlin, корутины) вызвана с параметрами по умолчанию. "
        f"{question} Ответ — целое число.",
        key=NumericKey(value),
        code=code,
        extra={"language": "kotlin", "delays": delays},
        explanation="Задержки: " + ", ".join(map(str, delays)) + " (toLong() отбрасывает дробь).",
    )


RETRY_BACKOFF = ItemTemplate(
    id="mobile.retry_backoff",
    specialization="mobile",
    topic="networking_offline",
    target_grade="junior",
    format=ItemFormat.NUMERIC,
    generator=_gen_backoff,
    a=1.0,
    b=-0.7,
    title="Повторы запроса с экспоненциальной задержкой",
    time_limit_s=180,
)

# --------------------------------------------------------------------------- HTTP-кэш


def simulate_http_cache(
    times: list[int], max_age: int | None, change_at: int | None, no_store: bool = False
) -> dict[str, int]:
    """Клиент с HTTP-кэшем (OkHttp Cache / URLCache) и сервер с ETag.

    max_age=None означает Cache-Control: no-cache (всегда ревалидировать).
    Ресурс на сервере меняется в момент change_at (между запросами).
    """
    stats = {"network": 0, "full": 0, "not_modified": 0, "cache": 0}
    stored_at: int | None = None
    stored_version = -1
    for t in times:
        version = 1 if change_at is not None and t > change_at else 0
        if no_store or stored_at is None:
            stats["network"] += 1
            stats["full"] += 1
            if not no_store:
                stored_at, stored_version = t, version
            continue
        fresh = max_age is not None and t - stored_at < max_age
        if fresh:
            stats["cache"] += 1
            continue
        stats["network"] += 1
        if version == stored_version:
            stats["not_modified"] += 1
        else:
            stats["full"] += 1
            stored_version = version
        stored_at = t
    return stats


def _gen_http_cache(rng: random.Random) -> Variant:
    path = rng.choice(("/api/catalog", "/api/profile", "/api/feed", "/api/tariffs", "/api/news"))
    while True:
        mode = rng.choice(("max_age", "max_age", "max_age", "no_cache"))
        max_age = rng.choice((30, 60, 120, 300)) if mode == "max_age" else None
        n = rng.randint(5, 7)
        gaps = [rng.choice((5, 10, 20, 25, 40, 50, 70, 90, 130, 200)) for _ in range(n - 1)]
        times = [0]
        for g in gaps:
            times.append(times[-1] + g)
        # ни один запрос не попадает ровно на границу свежести
        if max_age is not None and any(b - a == max_age for a in times for b in times if b > a):
            continue
        change_at = None
        if rng.random() < 0.7:
            i = rng.randrange(1, n - 1)
            change_at = times[i] + 1
        stats = simulate_http_cache(times, max_age, change_at)
        what = rng.choice(("network", "network", "not_modified", "full"))
        value = stats[what]
        if 0 < value < n:
            break
    cc = f"max-age={max_age}" if max_age is not None else "no-cache"
    change_text = (
        f"Ресурс на сервере меняется один раз — через {change_at} с после первого запроса "
        "(ETag становится другим)."
        if change_at is not None
        else "Ресурс на сервере за это время не меняется."
    )
    question = {
        "network": "Сколько запросов уйдёт в сеть (включая условные запросы с If-None-Match)?",
        "not_modified": "Сколько ответов 304 Not Modified получит клиент?",
        "full": "Сколько раз клиент получит ответ 200 с полным телом (включая первый запрос)?",
    }[what]
    moments = ", ".join(str(t) for t in times)
    return Variant(
        prompt=(
            f"Android-приложение (OkHttp 4 с настроенным Cache) запрашивает GET {path} "
            f"в моменты {moments} (секунды от первого запроса). Сервер на каждый ответ, "
            f"включая 304, присылает Cache-Control: {cc} и ETag; заголовки запроса "
            "приложение не меняет, задержкой сети пренебречь. Ответ свеж, пока его возраст "
            f"строго меньше max-age. {change_text}\n{question}"
        ),
        key=NumericKey(value),
        extra={"platform": "android", "stats": stats},
        explanation=f"Итог по запросам: {stats}. 304 обновляет время ответа в кэше, "
        "и ответ снова свеж на max-age секунд.",
    )


HTTP_CACHE = ItemTemplate(
    id="mobile.http_cache_revalidation",
    specialization="mobile",
    topic="networking_offline",
    target_grade="senior",
    format=ItemFormat.NUMERIC,
    generator=_gen_http_cache,
    a=1.3,
    b=1.4,
    title="HTTP-кэш: max-age, ETag и 304",
    time_limit_s=240,
)

TEMPLATES = (RETRY_BACKOFF, HTTP_CACHE)
