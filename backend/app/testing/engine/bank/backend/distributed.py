"""Backend · распределённые системы: ретраи с backoff, идемпотентные ключи, outbox,
саги, кворум Raft при разделении сети."""

from __future__ import annotations

import random
from typing import Any

from ...templates import (
    ItemFormat,
    ItemTemplate,
    NumericKey,
    Variant,
    make_ordering,
    make_single_choice,
)
from ._common import fmt_num

# ------------------------------------------------------------ ретраи с экспоненциальной паузой


def retry_timeline(style: str, params: dict[str, float]) -> tuple[float, int]:
    """(через сколько секунд вылетит исключение, сколько раз вызовут request) при вечных
    таймаутах."""
    timeout = params["timeout"]
    if style == "for":
        attempts = int(params["attempts"])
        sleeps = [min(params["cap"], params["base"] * 2**i) for i in range(attempts - 1)]
    else:
        attempts = int(params["retries"]) + 1
        delay = params["delay"]
        sleeps = []
        for _ in range(attempts - 1):
            sleeps.append(delay)
            delay = min(params["cap"], delay * 2)
    return attempts * timeout + sum(sleeps), attempts


def _make_retry(rng: random.Random) -> tuple[Variant, dict[str, Any]]:
    style = rng.choice(("for", "while"))
    fn = rng.choice(("fetch_rates", "load_profile", "send_invoice", "get_quote"))
    if style == "for":
        defaults = {"attempts": 5, "base": 0.5, "cap": 4.0, "timeout": 2.0}
        values = {
            "attempts": rng.choice((3, 4, 5, 6)),
            "base": rng.choice((0.1, 0.2, 0.25, 0.5, 1.0)),
            "cap": rng.choice((1.0, 2.0, 3.0, 5.0)),
            "timeout": rng.choice((0.5, 1.0, 1.5, 2.0, 3.0)),
        }
        sig = "request, attempts=5, base=0.5, cap=4.0, timeout=2.0"
        body = [
            "    for attempt in range(attempts):",
            "        try:",
            "            return request(timeout=timeout)",
            "        except TimeoutError:",
            "            if attempt == attempts - 1:",
            "                raise",
            "            time.sleep(min(cap, base * 2 ** attempt))",
        ]
    else:
        defaults = {"retries": 3, "delay": 1.0, "cap": 8.0, "timeout": 2.0}
        values = {
            "retries": rng.choice((2, 3, 4, 5)),
            "delay": rng.choice((0.2, 0.5, 1.0, 1.5)),
            "cap": rng.choice((1.0, 2.0, 3.0, 4.0)),
            "timeout": rng.choice((0.5, 1.0, 2.0, 2.5)),
        }
        sig = "request, retries=3, delay=1.0, cap=8.0, timeout=2.0"
        body = [
            "    while True:",
            "        try:",
            "            return request(timeout=timeout)",
            "        except TimeoutError:",
            "            if retries == 0:",
            "                raise",
            "            retries -= 1",
            "            time.sleep(delay)",
            "            delay = min(cap, delay * 2)",
        ]
    # часть аргументов передаётся явно, остальные — по умолчанию
    explicit = [k for k in values if rng.random() < 0.7]
    params = {k: (values[k] if k in explicit else defaults[k]) for k in defaults}
    args = ", ".join(f"{k}={fmt_num(values[k])}" for k in explicit)
    call = f"call_with_retry({fn}" + (f", {args})" if args else ")")
    code = "\n".join(["import time", "", "", f"def call_with_retry({sig}):", *body, "", "", call])
    total, calls = retry_timeline(style, params)
    ask = rng.choice(("time", "time", "calls"))
    if ask == "time":
        question = (
            "Через сколько секунд после вызова исключение дойдёт до вызывающего кода? "
            "Ответ — число секунд (можно дробное)."
        )
        answer, tol = total, 0.01
    else:
        question = f"Сколько раз будет вызвана функция {fn}?"
        answer, tol = float(calls), 0.0
    prompt = (
        f"Сервис, который вызывает {fn}, лежит: каждый вызов ждёт ровно timeout секунд и "
        "бросает TimeoutError. Временем на всё, кроме ожидания и time.sleep, пренебречь. "
        + question
    )
    variant = Variant(
        prompt=prompt,
        key=NumericKey(answer, tol),
        code=code,
        extra={"language": "python", "answer_type": "number" if ask == "time" else "integer"},
        explanation=f"Попыток {calls}, всего {fmt_num(total)} с.",
    )
    return variant, {"style": style, "params": params, "ask": ask}


RETRY_BACKOFF = ItemTemplate(
    id="backend.retry_backoff_time",
    specialization="backend",
    topic="distributed_systems",
    target_grade="middle",
    format=ItemFormat.NUMERIC,
    generator=lambda rng: _make_retry(rng)[0],
    a=1.2,
    b=0.6,
    title="Ретраи с экспоненциальной паузой",
    time_limit_s=240,
)

# ------------------------------------------------------------ идемпотентные ключи

_SERVERS: dict[str, list[str]] = {
    "none": [
        '@app.post("/payments")',
        "def create_payment(req):",
        "    payment = gateway.charge(req.card, req.amount)",
        '    return {"id": payment.id}',
    ],
    "check_then_set": [
        '@app.post("/payments")',
        "def create_payment(req, idempotency_key: str):",
        '    saved = redis.get(f"idem:{idempotency_key}")',
        "    if saved:",
        "        return json.loads(saved)",
        "    payment = gateway.charge(req.card, req.amount)",
        '    result = {"id": payment.id}',
        '    redis.set(f"idem:{idempotency_key}", json.dumps(result), ex=86400)',
        "    return result",
    ],
    "unique_first": [
        '@app.post("/payments")',
        "def create_payment(req, idempotency_key: str):",
        "    # INSERT ... ON CONFLICT DO NOTHING по уникальному ключу; ключ хранится 24 часа",
        "    if not db.try_insert_key(idempotency_key):",
        "        return db.wait_saved_response(idempotency_key)",
        "    payment = gateway.charge(req.card, req.amount)",
        '    db.save_response(idempotency_key, {"id": payment.id})',
        '    return {"id": payment.id}',
    ],
}

# событие клиента: (код, описание)
_EVENTS = {
    "retry_same": "клиент повторил запрос с тем же ключом K1 через 5 секунд",
    "new_key": "пользователь снова нажал «Оплатить», и клиент отправил запрос с новым ключом K2",
    "double_click": "из-за двойного клика два запроса с одним новым ключом K3 пришли на сервер "
    "одновременно",
    "lost_retry": "запрос с ключом K4 не дошёл до сервера (обрыв сети), клиент повторил его "
    "с тем же ключом K4",
    "late_retry": "через трое суток клиент повторил запрос с ключом K1",
}


def idempotency_charges(server: str, events: list[str]) -> int:
    """Сколько списаний в худшем случае. Первое событие всегда: запрос с ключом K1
    выполнен сервером, ответ потерян."""
    total = 1
    for e in events:
        if e == "retry_same":
            total += 1 if server == "none" else 0
        elif e == "double_click":
            total += 1 if server == "unique_first" else 2
        else:  # new_key, lost_retry, late_retry (ключи живут 24 часа)
            total += 1
    return total


def _make_idempotency(rng: random.Random) -> tuple[Variant, dict[str, Any]]:
    server = rng.choice(tuple(_SERVERS))
    events = rng.sample(list(_EVENTS), rng.randint(2, 3))
    order = {e: i for i, e in enumerate(_EVENTS)}
    events.sort(key=lambda e: order[e])
    amount = rng.choice((490, 990, 1500, 2990, 4990))
    lines = [
        f"1) запрос на оплату {amount} ₽ с ключом K1 сервер выполнил, но ответ до клиента "
        "не дошёл (таймаут);"
    ]
    lines += [f"{i + 2}) {_EVENTS[e]};" for i, e in enumerate(events)]
    answer = idempotency_charges(server, events)
    note = (
        "Клиент передаёт ключ в заголовке Idempotency-Key, но сервер его не использует."
        if server == "none"
        else "Клиент передаёт ключ в заголовке Idempotency-Key."
    )
    prompt = (
        f"Сервис платежей (код обработчика ниже). {note} Все запросы — одна и та же покупка "
        "одного пользователя. События по порядку:\n"
        + "\n".join(lines)
        + "\nСколько раз в худшем случае с карты спишут деньги?"
    )
    variant = Variant(
        prompt=prompt,
        key=NumericKey(answer, 0),
        code="\n".join(_SERVERS[server]),
        extra={"language": "python", "answer_type": "integer"},
        explanation=f"Сервер {server}: {answer} списаний.",
    )
    return variant, {"server": server, "events": events, "answer": answer}


IDEMPOTENCY = ItemTemplate(
    id="backend.idempotency_charges",
    specialization="backend",
    topic="distributed_systems",
    target_grade="senior",
    format=ItemFormat.NUMERIC,
    generator=lambda rng: _make_idempotency(rng)[0],
    a=1.4,
    b=1.5,
    title="Идемпотентные ключи: сколько будет списаний",
    time_limit_s=240,
)

# ------------------------------------------------------------ transactional outbox

O_NONE = "Нет ни записи в БД, ни события"
O_LOST = "Запись в БД сохранена, а событие не отправлено и само уже не отправится"
O_GHOST = "Событие отправлено, а записи в БД нет"
O_EVENTUAL = "Запись в БД сохранена, событие чуть позже отправит relay"
O_DUP = "Запись в БД сохранена, событие будет отправлено повторно (потребители получат дубль)"
O_OK = "Запись в БД сохранена, событие отправлено ровно один раз"
_OUTCOMES = (O_NONE, O_LOST, O_GHOST, O_EVENTUAL, O_DUP, O_OK)


def _outbox_code(
    style: str, ent: str, event: str, filler: str | None
) -> tuple[list[str], list[tuple[str, str]]]:
    """Код и шаги, после которых может случиться падение: (подпись шага, исход)."""
    head = [f"def create_{ent}(data):"]
    if filler:
        head.append(f"    {filler}")
    insert = f"{ent} = db.insert_{ent}(data)"
    if style == "commit_then_publish":
        body = [insert, "db.commit()", f'broker.publish("{event}", {ent}.id)', f"return {ent}"]
        steps = [
            (f"db.insert_{ent}(data)", O_NONE),
            ("db.commit()", O_LOST),
            ("broker.publish(...)", O_OK),
        ]
        return head + [f"    {b}" for b in body], steps
    if style == "publish_then_commit":
        body = [insert, f'broker.publish("{event}", {ent}.id)', "db.commit()", f"return {ent}"]
        steps = [
            (f"db.insert_{ent}(data)", O_NONE),
            ("broker.publish(...)", O_GHOST),
            ("db.commit()", O_OK),
        ]
        return head + [f"    {b}" for b in body], steps
    body = [insert, f'db.insert_outbox("{event}", {ent}.id)', "db.commit()", f"return {ent}"]
    relay = [
        "",
        "",
        "def relay():  # отдельный процесс, запускается раз в секунду",
        "    for event in db.fetch_unsent_outbox():",
        "        broker.publish(event.type, event.payload)",
        "        db.mark_sent(event.id)",
        "        db.commit()",
    ]
    steps = [
        (f"db.insert_outbox(...) в create_{ent}", O_NONE),
        (f"db.commit() в create_{ent}", O_EVENTUAL),
        ("broker.publish(...) в relay (create уже завершилась)", O_DUP),
        ("db.mark_sent(...) в relay (create уже завершилась)", O_DUP),
        ("db.commit() в relay (create уже завершилась)", O_OK),
    ]
    return head + [f"    {b}" for b in body] + relay, steps


def _gen_outbox(rng: random.Random) -> Variant:
    style = rng.choice(("commit_then_publish", "publish_then_commit", "outbox", "outbox"))
    ent, event = rng.choice(
        (
            ("order", "order_created"),
            ("payment", "payment_received"),
            ("user", "user_registered"),
            ("refund", "refund_requested"),
        )
    )
    filler = rng.choice((None, "validate(data)", 'log.info("create %s", data)'))
    lines, steps = _outbox_code(style, ent, event, filler)
    label, correct = rng.choice(steps)
    distractors = [o for o in _OUTCOMES if o != correct]
    return make_single_choice(
        rng,
        f"Процесс упал сразу после того, как выполнился вызов {label}; следующая строка не "
        "выполнилась. Незакоммиченные изменения БД при падении откатываются, после "
        "перезапуска процессы работают как обычно, брокер не теряет принятые сообщения. "
        "Каким будет итог?",
        correct,
        distractors,
        code="\n".join(lines),
        extra={"language": "python"},
        explanation="Запись и событие атомарны только при outbox; relay даёт at-least-once.",
    )


OUTBOX = ItemTemplate(
    id="backend.outbox_crash",
    specialization="backend",
    topic="distributed_systems",
    target_grade="senior",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_outbox,
    a=1.4,
    b=1.7,
    title="Падение между записью в БД и отправкой события",
    time_limit_s=240,
)

# ------------------------------------------------------------ сага с компенсациями

_SAGAS = (
    (
        "бронирование поездки",
        [
            ("Забронировать отель", "Отменить бронь отеля"),
            ("Забронировать авиабилет", "Отменить авиабилет"),
            ("Арендовать автомобиль", "Отменить аренду автомобиля"),
            ("Списать оплату", "Вернуть оплату"),
            ("Выписать документы", "Аннулировать документы"),
        ],
    ),
    (
        "оформление заказа",
        [
            ("Зарезервировать товар на складе", "Снять резерв товара"),
            ("Списать деньги с карты", "Вернуть деньги на карту"),
            ("Создать заявку на доставку", "Отменить заявку на доставку"),
            ("Начислить бонусные баллы", "Списать начисленные баллы"),
            ("Создать чек в ОФД", "Создать чек возврата"),
        ],
    ),
    (
        "подключение тарифа",
        [
            ("Создать договор", "Расторгнуть договор"),
            ("Списать абонентскую плату", "Вернуть абонентскую плату"),
            ("Выделить номер", "Освободить номер"),
            ("Активировать SIM-карту", "Деактивировать SIM-карту"),
            ("Включить услуги", "Отключить услуги"),
        ],
    ),
)


def _gen_saga(rng: random.Random) -> Variant:
    title, all_steps = rng.choice(_SAGAS)
    n = rng.randint(4, 5)
    steps = all_steps[:n]
    k = rng.randint(3, n)  # номер шага, на котором ошибка (с 1)
    done = steps[: k - 1]
    failed = steps[k - 1][0]
    order = [s for s, _ in done]
    order.append(f"{failed}: ошибка")
    order += [comp for _, comp in reversed(done)]
    listing = "; ".join(f"{i + 1}) {s}" for i, (s, _) in enumerate(steps))
    return make_ordering(
        rng,
        f"Сага «{title}» (оркестрация, у каждого шага своя локальная транзакция). Шаги по "
        f"порядку: {listing}. Шаг {k} завершился ошибкой; его локальная транзакция "
        "откатилась сама. Расставьте все действия саги в порядке выполнения.",
        order,
        explanation="Компенсации выполняются для уже завершённых шагов в обратном порядке; "
        "упавший шаг не компенсируется.",
    )


SAGA = ItemTemplate(
    id="backend.saga_compensation",
    specialization="backend",
    topic="distributed_systems",
    target_grade="middle",
    format=ItemFormat.ORDERING,
    generator=_gen_saga,
    a=1.2,
    b=0.7,
    title="Компенсации в саге",
    time_limit_s=180,
)

# ------------------------------------------------------------ Raft при разделении сети

W_OK = "Запись подтвердится (если нужно — после выборов нового лидера в этой части)"
W_FAIL = "Запись не подтвердится, пока связь не восстановится: в этой части нет большинства"
W_LOCAL = "Узел сразу подтвердит запись сам и разошлёт её остальным после восстановления связи"
W_LWW = "Запись подтвердят в обеих частях, после восстановления останется более поздняя"
R_OK = "Чтение выполнится и вернёт последние подтверждённые данные"
R_FAIL = "Чтение не выполнится, пока связь не восстановится: нет кворума"
R_STALE = "Узел сразу ответит своими локальными данными; они могут быть устаревшими"
R_OLD_LEADER = "Чтение всегда обслужит старый лидер, в какой бы части он ни был"


def raft_outcome(n: int, client_side: int, query: str) -> str:
    """Исход операции клиента, подключённого к части из client_side узлов кластера из n."""
    if query == "serializable":
        return R_STALE
    majority = client_side > n // 2
    if query == "write":
        return W_OK if majority else W_FAIL
    return R_OK if majority else R_FAIL


def _nodes(k: int) -> str:
    return f"{k} узел" if k == 1 else (f"{k} узла" if k <= 4 else f"{k} узлов")


def _gen_raft(rng: random.Random) -> Variant:
    n = rng.choice((3, 4, 5, 5, 6, 7))
    a = rng.randint(1, n - 1)
    b = n - a
    leader_in_a = rng.random() < 0.5
    client_in_a = rng.random() < 0.5
    query = rng.choice(("write", "write", "linearizable", "serializable"))
    client_side = a if client_in_a else b
    answer = raft_outcome(n, client_side, query)
    side_a, side_b = _nodes(a), _nodes(b)
    leader_txt = "в первой" if leader_in_a else "во второй"
    client_txt = "первой" if client_in_a else "второй"
    if query == "write":
        what = "запись ключа (put)"
        options = [W_OK, W_FAIL, W_LOCAL, W_LWW]
    elif query == "linearizable":
        what = "чтение ключа с настройками по умолчанию (линеаризуемое, --consistency=l)"
        options = [R_OK, R_FAIL, R_STALE, R_OLD_LEADER]
    else:
        what = "чтение ключа с --consistency=s (serializable)"
        options = [R_OK, R_FAIL, R_STALE, R_OLD_LEADER]
    return make_single_choice(
        rng,
        f"Кластер etcd из {n} узлов (Raft). Сеть разделилась на две части: в первой "
        f"{side_a}, во второй {side_b}; до разделения лидер был {leader_txt} части. Клиент "
        f"подключён к узлу из {client_txt} части и выполняет {what}. Что произойдёт, "
        "пока сеть разделена?",
        answer,
        [o for o in options if o != answer],
        extra={"topic_hint": "raft"},
        explanation="Коммит в Raft требует подтверждения большинства (больше n/2) узлов.",
    )


RAFT_PARTITION = ItemTemplate(
    id="backend.raft_partition",
    specialization="backend",
    topic="distributed_systems",
    target_grade="senior",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_raft,
    a=1.4,
    b=1.8,
    title="Raft при разделении сети",
    time_limit_s=180,
)

TEMPLATES = [RETRY_BACKOFF, IDEMPOTENCY, OUTBOX, SAGA, RAFT_PARTITION]
