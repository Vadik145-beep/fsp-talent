"""Backend · кэши и очереди: промахи LRU/FIFO, повторная доставка сообщений."""

from __future__ import annotations

import random
from collections import OrderedDict
from typing import Any

from ...templates import ItemFormat, ItemTemplate, NumericKey, Variant, make_single_choice

# ------------------------------------------------------------ промахи кэша


def cache_misses(policy: str, capacity: int, requests: list[str]) -> int:
    """Число промахов кэша LRU или FIFO заданной ёмкости (изначально пуст)."""
    cache: OrderedDict[str, None] = OrderedDict()
    misses = 0
    for key in requests:
        if key in cache:
            if policy == "LRU":
                cache.move_to_end(key)
            continue
        misses += 1
        if len(cache) >= capacity:
            cache.popitem(last=False)
        cache[key] = None
    return misses


def _make_lru(rng: random.Random) -> tuple[Variant, dict[str, Any]]:
    policy = rng.choice(("LRU", "LRU", "FIFO"))
    capacity = rng.randint(2, 4)
    keys = rng.sample(list("ABCDEFGHKM") if rng.random() < 0.5 else list("123456789"), capacity + 2)
    n = rng.randint(10, 13)
    requests = [rng.choice(keys[: capacity + rng.randint(0, 2)]) for _ in range(n)]
    ask = rng.choice(("misses", "hits"))
    misses = cache_misses(policy, capacity, requests)
    answer = misses if ask == "misses" else n - misses
    rule = (
        "при переполнении вытесняется ключ, к которому дольше всего не обращались"
        if policy == "LRU"
        else "при переполнении вытесняется ключ, который был добавлен раньше всех "
        "(попадание порядок не меняет)"
    )
    what = "промахов (cache miss)" if ask == "misses" else "попаданий (cache hit)"
    variant = Variant(
        prompt=(
            f"Кэш {policy} ёмкостью {capacity} ключа, изначально пуст; {rule}. "
            f"Запросы ключей идут в таком порядке: {' '.join(requests)}. "
            f"Сколько будет {what}?"
        ),
        key=NumericKey(answer, 0),
        extra={"answer_type": "integer"},
        explanation=f"Промахов {misses} из {n}.",
    )
    return variant, {"policy": policy, "capacity": capacity, "requests": requests, "ask": ask}


LRU_MISSES = ItemTemplate(
    id="backend.lru_misses",
    specialization="backend",
    topic="caching_queues",
    target_grade="junior",
    format=ItemFormat.NUMERIC,
    generator=lambda rng: _make_lru(rng)[0],
    a=1.2,
    b=-0.6,
    title="Промахи кэша LRU и FIFO",
    time_limit_s=180,
)

# ------------------------------------------------------------ повторная доставка сообщений

_ZERO = "Ни разу: сообщение потеряно"
_ONE = "Ровно один раз"
_TWO = "Два раза: после перезапуска сообщение обработают повторно"


def redelivery_charges(mode: str, crash_after: str) -> int:
    """Сколько раз выполнится списание по сообщению при падении потребителя.

    mode: process_then_commit / commit_then_process / dedup_then_commit;
    crash_after: first — упал после первого шага обработки (до второго), end — после обоих.
    """
    if crash_after == "end":
        return 1
    if mode == "commit_then_process":
        return 0 if crash_after == "first" else 1
    if mode == "process_then_commit":
        return 2 if crash_after == "first" else 1
    return 1  # дедупликация в той же транзакции БД, что и списание


def _make_redelivery(rng: random.Random) -> tuple[Variant, dict[str, Any]]:
    mode = rng.choice(("process_then_commit", "commit_then_process", "dedup_then_commit"))
    crash_after = rng.choice(("first", "first", "end"))
    entity, field = rng.choice(
        (("order", "order_id"), ("invoice", "invoice_id"), ("booking", "booking_id"))
    )
    broker = rng.choice(("Kafka", "RabbitMQ"))
    ack = "consumer.commit(msg)" if broker == "Kafka" else "channel.basic_ack(msg.delivery_tag)"
    log_line = rng.choice((None, 'log.info("got %s", msg.id)', "metrics.inc('messages')"))
    body: list[str] = []
    if log_line:
        body.append(f"    {log_line}")
    if mode == "process_then_commit":
        charge = f"payments.charge(msg.{field}, msg.amount)"
        body += [f"    {charge}", f"    {ack}"]
        steps = (charge, ack)
    elif mode == "commit_then_process":
        body += [f"    {ack}", f"    payments.charge(msg.{field}, msg.amount)"]
        steps = (ack, f"payments.charge(msg.{field}, msg.amount)")
    else:
        body += [
            "    with db.transaction():",
            "        if not db.processed_messages.exists(msg.id):",
            f"            db.accounts.debit(msg.{field}, msg.amount)",
            "            db.processed_messages.add(msg.id)",
            f"    {ack}",
        ]
        steps = ("блок with db.transaction() (транзакция закоммичена)", ack)
    code = "\n".join(["for msg in consumer:", *body])
    answer = redelivery_charges(mode, crash_after)
    done = steps[0] if crash_after == "first" else steps[1]
    crash = f"сразу после того, как завершился шаг {done}"
    text = {0: _ZERO, 1: _ONE, 2: _TWO}
    charge_desc = (
        "payments.charge — вызов внешнего платёжного API, его нельзя откатить"
        if mode != "dedup_then_commit"
        else "db.accounts.debit и db.processed_messages пишут в одну БД, в одной транзакции"
    )
    variant = make_single_choice(
        rng,
        f"Потребитель {broker} обрабатывает сообщения о списании денег ({charge_desc}). "
        "Брокер повторно доставляет каждое неподтверждённое сообщение (at-least-once). "
        f"При обработке сообщения по {entity} #{rng.randint(100, 999)} процесс упал {crash}, "
        "затем перезапустился. Сколько раз в итоге выполнится списание по этому сообщению?",
        text[answer],
        [v for k, v in text.items() if k != answer],
        code=code,
        extra={"language": "python"},
        explanation=f"Режим {mode}, падение после {crash_after}: {answer}.",
    )
    return variant, {"mode": mode, "crash_after": crash_after, "answer": answer}


QUEUE_REDELIVERY = ItemTemplate(
    id="backend.queue_redelivery",
    specialization="backend",
    topic="caching_queues",
    target_grade="senior",
    format=ItemFormat.SINGLE_CHOICE,
    generator=lambda rng: _make_redelivery(rng)[0],
    a=1.3,
    b=1.0,
    title="Повторная доставка: сколько раз спишут деньги",
    time_limit_s=180,
)

TEMPLATES = [LRU_MISSES, QUEUE_REDELIVERY]
