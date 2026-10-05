"""Backend · HTTP и проектирование API: коды ответа, повтор запросов, условные запросы,
кэширование, пагинация."""

from __future__ import annotations

import random
from typing import Any

from ...templates import (
    ItemFormat,
    ItemTemplate,
    NumericKey,
    Variant,
    make_multi_choice,
    make_single_choice,
)

# ------------------------------------------------------------ код ответа обработчика

_RESOURCES = (
    ("article", "articles", "title"),
    ("post", "posts", "text"),
    ("project", "projects", "name"),
    ("invoice", "invoices", "amount"),
    ("comment", "comments", "body"),
)


def _make_handler_status(rng: random.Random) -> tuple[Variant, dict[str, Any]]:
    res, coll, field = rng.choice(_RESOURCES)
    validation_code = rng.choice((400, 422))
    checks = ["auth", "load", "perm", "validate"]
    while True:
        rng.shuffle(checks)
        if checks.index("perm") > max(checks.index("auth"), checks.index("load")):
            break
    blocks = {
        "auth": [
            "    user = find_user(request.token)  # None, если токена нет или он неверный",
            "    if user is None:",
            "        return 401",
        ],
        "load": [
            f"    {res} = {coll}.get({res}_id)  # None, если записи нет",
            f"    if {res} is None:",
            "        return 404",
        ],
        "perm": [
            f"    if {res}.author_id != user.id and not user.is_admin:",
            "        return 403",
        ],
        "validate": [
            f'    if not request.body.get("{field}"):',
            f"        return {validation_code}",
        ],
    }
    lines = [f"def update_{res}(request, {res}_id):"]
    for c in checks:
        lines += blocks[c]
    lines += [f'    {res}.{field} = request.body["{field}"]', "    return 200"]

    # сценарий запроса: обычно проваливаются хотя бы две проверки
    while True:
        token_ok = rng.random() < 0.6
        exists = rng.random() < 0.6
        role = rng.choice(("author", "admin", "other"))
        has_field = rng.random() < 0.4
        failing = {
            "auth": not token_ok,
            "load": not exists,
            "perm": role == "other",
            "validate": not has_field,
        }
        if sum(failing.values()) >= 1 and (sum(failing.values()) >= 2 or rng.random() < 0.25):
            break
    codes = {"auth": 401, "load": 404, "perm": 403, "validate": validation_code}
    answer = 200
    for c in checks:
        # проверка прав выполняется только если код до неё дошёл (user и запись есть)
        if failing[c]:
            answer = codes[c]
            break
    uid = rng.randint(2, 40)
    rid = rng.randint(100, 999)
    author = uid if role == "author" else rng.choice([x for x in range(2, 41) if x != uid])
    parts = []
    if token_ok:
        who = "администратор" if role == "admin" else "не администратор"
        parts.append(f"токен действителен (пользователь id = {uid}, {who})")
    else:
        parts.append("токен просрочен (find_user вернёт None)")
    if exists:
        parts.append(f"запись {res} id = {rid} существует, её автор — пользователь {author}")
    else:
        parts.append(f"записи {res} id = {rid} нет")
    parts.append(f"в теле есть поле {field}" if has_field else f"в теле нет поля {field}")
    prompt = (
        f"Обработчик PATCH /{coll}/{{id}} обновляет запись (код ниже). "
        f"Пришёл запрос PATCH /{coll}/{rid}: " + "; ".join(parts) + ". "
        "Какой код ответа вернёт обработчик?"
    )
    variant = make_single_choice(
        rng,
        prompt,
        str(answer),
        [str(c) for c in (200, 401, 403, 404, validation_code)],
        code="\n".join(lines),
        extra={"language": "python"},
        explanation="Срабатывает первая по порядку проверка, которая не прошла.",
    )
    data = {
        "res": res,
        "coll": coll,
        "field": field,
        "token_ok": token_ok,
        "exists": exists,
        "is_admin": role == "admin",
        "uid": uid,
        "author": author,
        "rid": rid,
        "has_field": has_field,
        "answer": answer,
    }
    return variant, data


HANDLER_STATUS = ItemTemplate(
    id="backend.handler_status",
    specialization="backend",
    topic="http_api",
    target_grade="intern",
    format=ItemFormat.SINGLE_CHOICE,
    generator=lambda rng: _make_handler_status(rng)[0],
    a=1.0,
    b=-1.3,
    title="Какой код вернёт обработчик",
    time_limit_s=150,
)

# ------------------------------------------------------------ безопасный повтор запроса


def _gen_retry_safe(rng: random.Random) -> Variant:
    i = rng.randint(10, 999)
    j = rng.randint(10, 999)
    n = rng.choice((100, 250, 500, 1000))
    safe = [
        f"GET /orders/{i}",
        f'PUT /users/{j}/email  {{"email": "u{j}@mail.ru"}}',
        f"DELETE /cart/items/{i}",
        f"HEAD /files/{j}",
        f'PUT /settings/{i}  {{"theme": "dark", "lang": "ru"}}',
        f"GET /reports?from=2026-0{rng.randint(1, 9)}-01",
    ]
    unsafe = [
        f'POST /orders  {{"product_id": {j}, "qty": 2}}',
        f'POST /payments  {{"order_id": {i}, "amount": {n}}}',
        f'PATCH /accounts/{j}  {{"balance_delta": {n}}}',
        f'POST /chats/{i}/messages  {{"text": "Привет"}}',
        f"POST /counters/{j}/increment",
    ]
    correct = rng.sample(safe, rng.randint(2, 3))
    wrong = rng.sample(unsafe, rng.randint(2, 3))
    return make_multi_choice(
        rng,
        "Клиент отправил запрос, не дождался ответа (таймаут) и не знает, выполнил ли его "
        "сервер. Сервер реализует методы строго по семантике HTTP, идемпотентных ключей нет. "
        "Какие запросы можно просто отправить ещё раз, не рискуя получить другое итоговое "
        "состояние данных, чем при одном успешном запросе? Отметьте все такие.",
        correct,
        wrong,
        extra={"topic_hint": "idempotency"},
        explanation="GET/HEAD/PUT/DELETE идемпотентны; POST и PATCH с приращением — нет.",
    )


HTTP_RETRY_SAFE = ItemTemplate(
    id="backend.http_retry_safe",
    specialization="backend",
    topic="http_api",
    target_grade="junior",
    format=ItemFormat.MULTI_CHOICE,
    generator=_gen_retry_safe,
    a=1.2,
    b=-0.6,
    title="Какие запросы можно безопасно повторить",
    time_limit_s=150,
)

# ------------------------------------------------------------ условные запросы (ETag)

_REASONS = {200: "OK", 201: "Created", 304: "Not Modified", 412: "Precondition Failed"}
_DATES = (
    "Mon, 03 Mar 2025 10:00:00 GMT",
    "Tue, 04 Mar 2025 08:30:00 GMT",
    "Wed, 05 Mar 2025 12:15:00 GMT",
    "Thu, 06 Mar 2025 18:45:00 GMT",
)


def _make_conditional(rng: random.Random) -> tuple[Variant, dict[str, Any]]:
    tag = rng.choice(("v", "r", "e")) + str(rng.randint(10, 99))
    other = tag[0] + str(int(tag[1:]) + rng.choice((-3, -1, 1, 2, 5)))
    lm_idx = rng.randint(1, 2)
    lm = _DATES[lm_idx]
    before, after = _DATES[lm_idx - 1], _DATES[lm_idx + 1]
    path = rng.choice(("/api/products/", "/api/profiles/", "/api/docs/")) + str(rng.randint(1, 500))
    case = rng.choice(
        (
            "inm_match",
            "inm_other",
            "inm_list",
            "ims_newer",
            "ims_older",
            "inm_over_ims",
            "inm_weak",
            "im_match",
            "im_other",
            "im_weak",
            "ius_older",
            "inm_star_exists",
            "inm_star_missing",
            "delete_im_other",
        )
    )
    exists = case != "inm_star_missing"
    method, headers, answer = "GET", [], 200
    if case == "inm_match":
        headers, answer = [f'If-None-Match: "{tag}"'], 304
    elif case == "inm_other":
        headers, answer = [f'If-None-Match: "{other}"'], 200
    elif case == "inm_list":
        headers, answer = [f'If-None-Match: "{other}", "{tag}"'], 304
    elif case == "ims_newer":
        headers, answer = [f"If-Modified-Since: {rng.choice((lm, after))}"], 304
    elif case == "ims_older":
        headers, answer = [f"If-Modified-Since: {before}"], 200
    elif case == "inm_over_ims":
        headers = [f'If-None-Match: "{other}"', f"If-Modified-Since: {after}"]
        answer = 200
    elif case == "inm_weak":
        headers, answer = [f'If-None-Match: W/"{tag}"'], 304
    elif case == "im_match":
        method, headers, answer = "PUT", [f'If-Match: "{tag}"'], 200
    elif case == "im_other":
        method, headers, answer = "PUT", [f'If-Match: "{other}"'], 412
    elif case == "im_weak":
        method, headers, answer = "PUT", [f'If-Match: W/"{tag}"'], 412
    elif case == "ius_older":
        method, headers, answer = "PUT", [f"If-Unmodified-Since: {before}"], 412
    elif case == "inm_star_exists":
        method, headers, answer = "PUT", ["If-None-Match: *"], 412
    elif case == "inm_star_missing":
        method, headers, answer = "PUT", ["If-None-Match: *"], 201
    else:
        method, headers, answer = "DELETE", [f'If-Match: "{other}"'], 412
    req = [f"{method} {path} HTTP/1.1", "Host: shop.example", *headers]
    if method == "PUT":
        req += ["Content-Type: application/json", "", '{"title": "Новое название"}']
    state = (
        f'ресурс существует, его текущий ETag: "{tag}" (сильный), Last-Modified: {lm}'
        if exists
        else "ресурса по этому адресу пока нет"
    )
    prompt = (
        "Сервер корректно реализует условные запросы по RFC 9110. Успешный GET отвечает 200, "
        "успешное обновление через PUT — 200, создание нового ресурса через PUT — 201. "
        f"Состояние на сервере: {state}. Какой код ответа вернёт сервер на этот запрос? "
        "Ответ — трёхзначный код."
    )
    variant = Variant(
        prompt=prompt,
        key=(str(answer), f"{answer} {_REASONS[answer]}"),
        code="\n".join(req),
        extra={"language": "http"},
        explanation=f"Случай {case}: {answer}.",
    )
    return variant, {"case": case, "answer": answer}


HTTP_CONDITIONAL = ItemTemplate(
    id="backend.http_conditional",
    specialization="backend",
    topic="http_api",
    target_grade="middle",
    format=ItemFormat.SHORT_TEXT,
    generator=lambda rng: _make_conditional(rng)[0],
    a=1.3,
    b=0.3,
    title="Условные запросы: ETag и If-*",
    time_limit_s=180,
)

# ------------------------------------------------------------ Cache-Control

_OUT_FRESH = "fresh"
_OUT_COND = "conditional"
_OUT_FULL = "full"
_OUT_SWR = "swr"


def cache_outcome(subject: str, directive: dict[str, Any], has_etag: bool, t: int) -> str:
    """Что сделает кэш через t секунд после получения ответа (RFC 9111, RFC 5861)."""
    if directive.get("no-store"):
        return _OUT_FULL
    if subject == "cdn" and directive.get("private"):
        return _OUT_FULL  # общий кэш не хранит private-ответы
    stale = _OUT_COND if has_etag else _OUT_FULL
    if directive.get("no-cache"):
        return stale
    lifetime = directive.get("max-age", 0)
    if subject == "cdn" and "s-maxage" in directive:
        lifetime = directive["s-maxage"]
    if t < lifetime:
        return _OUT_FRESH
    swr = directive.get("stale-while-revalidate")
    if swr is not None and t < lifetime + swr:
        return _OUT_SWR
    return stale


def _make_cache_control(rng: random.Random) -> tuple[Variant, dict[str, Any]]:
    subject = rng.choice(("browser", "cdn"))
    kind = rng.choice(("max_age", "no_cache", "no_store", "swr", "private", "s_maxage", "max0"))
    n = rng.choice((60, 120, 300, 600, 3600))
    if kind == "max_age":
        d, text = {"max-age": n}, f"max-age={n}"
    elif kind == "no_cache":
        d, text = {"no-cache": True}, "no-cache"
    elif kind == "no_store":
        d, text = {"no-store": True}, "no-store"
    elif kind == "swr":
        s = rng.choice((30, 60, 300))
        d = {"max-age": n, "stale-while-revalidate": s}
        text = f"max-age={n}, stale-while-revalidate={s}"
    elif kind == "private":
        d, text = {"private": True, "max-age": n}, f"private, max-age={n}"
    elif kind == "s_maxage":
        m = n * rng.choice((2, 5, 10))
        d, text = {"max-age": n, "s-maxage": m}, f"public, max-age={n}, s-maxage={m}"
    else:
        d, text = {"max-age": 0, "must-revalidate": True}, "max-age=0, must-revalidate"
    has_etag = rng.random() < 0.7
    lifetime = d.get("max-age", 0)
    if subject == "cdn" and "s-maxage" in d:
        lifetime = d["s-maxage"]
    if kind == "s_maxage":
        # самое интересное — момент между max-age и s-maxage
        t = rng.choice((n + n // 2, d["s-maxage"] + 10, n // 2))
    else:
        swr = d.get("stale-while-revalidate", 0)
        t = rng.choice(
            [x for x in (lifetime // 2, lifetime + max(1, swr // 2), lifetime + swr + 30) if x > 0]
        )
    answer = cache_outcome(subject, d, has_etag, t)
    subj = "Браузер" if subject == "browser" else "CDN"
    texts = {
        _OUT_FRESH: f"{subj} отдаст ответ из своего кэша, не обращаясь к серверу",
        _OUT_COND: f"{subj} отправит серверу условный запрос (If-None-Match) "
        "и при ответе 304 использует копию из кэша",
        _OUT_FULL: f"{subj} отправит серверу обычный запрос и получит ответ целиком",
        _OUT_SWR: f"{subj} сразу отдаст устаревшую копию из кэша и в фоне обновит её у сервера",
    }
    headers = ["HTTP/1.1 200 OK", "Content-Type: application/json", f"Cache-Control: {text}"]
    if has_etag:
        headers.append(f'ETag: "{rng.choice(("a", "b", "c"))}{rng.randint(100, 999)}"')
    who = (
        "Браузер пользователя (его собственный кэш)"
        if subject == "browser"
        else "CDN (общий кэш между пользователями и сервером)"
    )
    prompt = (
        f"{who} получил ответ сервера с такими заголовками. Через {t} с тот же URL "
        "запрашивают снова. Кэш полностью соблюдает RFC 9111 и RFC 5861. Что произойдёт?"
    )
    correct = texts[answer]
    variant = make_single_choice(
        rng,
        prompt,
        correct,
        [v for k, v in texts.items() if k != answer],
        code="\n".join(headers),
        extra={"language": "http"},
        explanation=f"Исход: {answer}.",
    )
    return variant, {"subject": subject, "directive": d, "etag": has_etag, "t": t}


HTTP_CACHE_CONTROL = ItemTemplate(
    id="backend.http_cache_control",
    specialization="backend",
    topic="http_api",
    target_grade="middle",
    format=ItemFormat.SINGLE_CHOICE,
    generator=lambda rng: _make_cache_control(rng)[0],
    a=1.3,
    b=0.8,
    title="Cache-Control: что сделает кэш",
    time_limit_s=180,
)

# ------------------------------------------------------------ offset-пагинация


def pagination_effect(method: str, k: int, inserted: int, deleted: int) -> tuple[int, int]:
    """(дубли на 2-й странице, пропущенные старые записи) для ленты «новые сверху».

    inserted — новые записи сверху после загрузки 1-й страницы, deleted — удалено записей
    с 1-й страницы. Для курсорной пагинации (WHERE created_at < последнего) — (0, 0).
    """
    if method == "cursor":
        return 0, 0
    shift = inserted - deleted
    return (min(shift, k), 0) if shift >= 0 else (0, min(-shift, k))


def _make_pagination(rng: random.Random) -> tuple[Variant, dict[str, Any]]:
    table, ru = rng.choice(
        (("posts", "постов"), ("news", "новостей"), ("orders", "заказов"), ("events", "событий"))
    )
    k = rng.choice((10, 20, 25, 50))
    method = rng.choice(("offset", "offset", "offset", "cursor"))
    change = rng.choice(("insert", "delete", "both"))
    inserted = rng.randint(1, k - 1) if change in ("insert", "both") else 0
    deleted = rng.randint(1, k - 1) if change in ("delete", "both") else 0
    ask = rng.choice(("dup", "skip"))
    if change == "insert":
        ask = "dup" if rng.random() < 0.8 else "skip"
    elif change == "delete":
        ask = "skip" if rng.random() < 0.8 else "dup"
    dup, skip = pagination_effect(method, k, inserted, deleted)
    answer = dup if ask == "dup" else skip
    if method == "offset":
        sql = f"SELECT * FROM {table}\nORDER BY created_at DESC\nLIMIT {k} OFFSET {{offset}};"
        how = f"страница 1 — OFFSET 0, страница 2 — OFFSET {k}"
    else:
        sql = (
            f"SELECT * FROM {table}\nWHERE created_at < :last_created_at\n"
            f"ORDER BY created_at DESC\nLIMIT {k};"
        )
        how = (
            "страница 1 — без условия WHERE, страница 2 — с created_at последней записи страницы 1"
        )
    events = []
    if inserted:
        events.append(f"добавили {inserted} новых {ru} (они самые свежие)")
    if deleted:
        events.append(f"удалили {deleted} {ru}, которые были на первой странице")
    question = (
        "Сколько записей второй страницы клиент уже видел на первой?"
        if ask == "dup"
        else "Сколько записей, которые были в ленте ещё до загрузки первой страницы, клиент "
        "не увидит ни на первой, ни на второй странице?"
    )
    prompt = (
        f"Лента {ru} отдаётся страницами по {k} записей ({how}); created_at у всех записей "
        f"разный, всего в ленте больше {3 * k} записей. Клиент загрузил первую страницу, "
        f"после этого {' и '.join(events)}. Затем клиент загрузил вторую страницу. {question}"
    )
    variant = Variant(
        prompt=prompt,
        key=NumericKey(answer, 0),
        code=sql,
        extra={"language": "sql", "answer_type": "integer"},
        explanation=f"Сдвиг окна OFFSET: дубли {dup}, пропуски {skip}.",
    )
    data = {"method": method, "k": k, "inserted": inserted, "deleted": deleted, "ask": ask}
    return variant, data


PAGINATION = ItemTemplate(
    id="backend.pagination_offset",
    specialization="backend",
    topic="http_api",
    target_grade="middle",
    format=ItemFormat.NUMERIC,
    generator=lambda rng: _make_pagination(rng)[0],
    a=1.2,
    b=0.5,
    title="Пагинация: дубли и пропуски при OFFSET",
    time_limit_s=180,
)

TEMPLATES = [HANDLER_STATUS, HTTP_RETRY_SAFE, HTTP_CONDITIONAL, HTTP_CACHE_CONTROL, PAGINATION]
