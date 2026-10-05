"""Frontend / браузер и сеть: HTTP-кэш, CORS preflight, порядок выполнения скриптов,
расчёт layout shift (CLS)."""

from __future__ import annotations

import random
from dataclasses import dataclass
from itertools import pairwise

from ...templates import (
    ItemFormat,
    ItemTemplate,
    NumericKey,
    Variant,
    make_multi_choice,
    make_ordering,
)

_HOSTS = ("shop.example", "app.example", "news.example", "bank.example", "media.example")
_API_HOSTS = ("api.example.net", "data.example.org", "backend.example.io", "svc.example.com")

# --------------------------------------------------------------------------- HTTP-кэш


def _hex(rng: random.Random, n: int) -> str:
    return "".join(rng.choice("0123456789abcdef") for _ in range(n))


def _gen_http_cache(rng: random.Random) -> Variant:
    host = rng.choice(_HOSTS)
    file = rng.choice(("app", "main", "vendor", "styles", "logo", "catalog"))
    etag = _hex(rng, rng.choice((6, 8, 10)))
    day = rng.randint(1, 28)
    month = rng.choice(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Sep", "Oct"))
    date = (
        f"{day:02d} {month} 2026 {rng.randint(0, 23):02d}:{rng.choice(('00', '15', '30'))}:00 GMT"
    )
    path = f"/static/{file}.{_hex(rng, 6)}.js"
    hours = rng.choice((1, 2, 6, 12, 24))
    scenario = rng.randrange(10)
    resp = ["HTTP/1.1 200 OK", "Content-Type: application/javascript"]
    if scenario == 0:
        resp += [f'ETag: "{etag}"', "Cache-Control: no-cache"]
        q = (
            "Через минуту браузер снова запрашивает этот файл. Какой заголовок запроса со "
            f'значением "{etag}" он добавит, чтобы сервер мог ответить «не изменилось»?'
        )
        ans: tuple[str, ...] = ("If-None-Match",)
    elif scenario == 1:
        resp += [f"Last-Modified: Mon, {date}", "Cache-Control: no-cache"]
        q = (
            "ETag сервер не отдаёт. Какой заголовок запроса с этой датой добавит браузер при "
            "повторном запросе, чтобы проверить, изменился ли файл?"
        )
        ans = ("If-Modified-Since",)
    elif scenario == 2:
        resp += [f'ETag: "{etag}"', "Cache-Control: no-cache"]
        q = (
            f'Браузер прислал повторный запрос с If-None-Match: "{etag}", файл не менялся. '
            "Какой код статуса вернёт сервер (ответ без тела)?"
        )
        ans = ("304", "304 Not Modified")
    elif scenario == 3:
        resp += ["Cache-Control: ____"]
        q = (
            "Ответ содержит персональные банковские данные: его нельзя сохранять ни в каком "
            "кэше (ни в браузере, ни на прокси). Какую директиву Cache-Control вписать?"
        )
        ans = ("no-store",)
    elif scenario == 4:
        resp += [f'ETag: "{etag}"', "Cache-Control: ____"]
        q = (
            "Файл можно хранить в кэше, но перед каждым использованием браузер обязан "
            "перепроверить его у сервера. Какую директиву Cache-Control вписать (одно слово)?"
        )
        ans = ("no-cache",)
    elif scenario == 5:
        resp += [f"Cache-Control: ____, max-age={hours * 3600}"]
        q = (
            "Ответ с данными конкретного пользователя можно кэшировать в его браузере, но не "
            "в общих кэшах (CDN, прокси). Какую директиву вписать вместо ____?"
        )
        ans = ("private",)
    elif scenario == 6:
        resp += [f"Cache-Control: public, max-age=60, ____={hours * 3600}"]
        q = (
            f"Браузер должен держать файл 60 секунд, а CDN — {hours} ч. Какую директиву "
            "вписать вместо ____?"
        )
        ans = ("s-maxage",)
    elif scenario == 7:
        resp += ["Cache-Control: public, max-age=31536000, ____"]
        q = (
            "Имя файла содержит хэш содержимого, файл никогда не меняется. Какая директива "
            "запретит браузеру перепроверять его даже при обновлении страницы (F5)?"
        )
        ans = ("immutable",)
    elif scenario == 8:
        resp += [
            "Content-Encoding: gzip",
            "Cache-Control: public, max-age=600",
            "____: Accept-Encoding",
        ]
        q = (
            "Сервер отдаёт gzip или несжатый вариант в зависимости от Accept-Encoding. Какой "
            "заголовок ответа сообщает кэшам, что от этого заголовка запроса зависит ответ?"
        )
        ans = ("Vary",)
    else:
        resp += ["Cache-Control: public, max-age=____"]
        q = (
            f"Файл должен считаться свежим ровно {hours} ч без запросов к серверу. Какое "
            "число вписать вместо ____?"
        )
        ans = (str(hours * 3600), f"max-age={hours * 3600}")
    code = f"GET {path} HTTP/1.1\nHost: {host}\n\n" + "\n".join(resp)
    return Variant(
        prompt=q + " Ответ — точное значение, без пояснений.",
        key=ans,
        code=code,
        extra={"language": "http"},
        explanation=f"Ответ: {ans[0]}.",
    )


HTTP_CACHE = ItemTemplate(
    id="frontend.http_cache_headers",
    specialization="frontend",
    topic="browser_network",
    target_grade="junior",
    format=ItemFormat.SHORT_TEXT,
    generator=_gen_http_cache,
    a=1.1,
    b=-0.8,
    title="HTTP-кэширование: заголовки и директивы",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- CORS preflight

_SAFE_CT = ("application/x-www-form-urlencoded", "multipart/form-data", "text/plain")


@dataclass(frozen=True)
class _Req:
    path: str
    method: str
    headers: tuple[tuple[str, str], ...]
    body: str | None  # json_str | form | params | text | None
    same_origin: bool = False


def _needs_preflight(r: _Req) -> bool:
    if r.same_origin:
        return False
    if r.method not in ("GET", "HEAD", "POST"):
        return True
    for name, value in r.headers:
        low = name.lower()
        if low in ("accept", "accept-language", "content-language"):
            continue
        if low == "content-type" and value.split(";")[0].strip().lower() in _SAFE_CT:
            continue
        return True
    return False


def _req_js(r: _Req) -> str:
    url = f"'{r.path}'" if r.same_origin else f"API + '{r.path}'"
    opts = []
    if r.method != "GET":
        opts.append(f"method: '{r.method}'")
    if r.headers:
        hs = ", ".join(
            f"'{k}': {v}" if k == "Authorization" else f"'{k}': '{v}'" for k, v in r.headers
        )
        opts.append(f"headers: {{ {hs} }}")
    body_js = {
        "json_str": "JSON.stringify(data)",
        "form": "new FormData(form)",
        "params": "new URLSearchParams({ q: 'x' })",
        "text": "'ping'",
    }
    if r.body:
        opts.append(f"body: {body_js[r.body]}")
    return f"fetch({url}, {{ {', '.join(opts)} }})" if opts else f"fetch({url})"


def _random_req(rng: random.Random) -> _Req:
    path = rng.choice(("/orders", "/items", "/cart", "/profile", "/search", "/stats", "/events"))
    r = rng.random()
    if r < 0.1:
        return _Req(path, rng.choice(("PUT", "DELETE", "POST")), (), None, same_origin=True)
    method = rng.choice(("GET", "GET", "HEAD", "POST", "POST", "POST", "PUT", "DELETE", "PATCH"))
    headers: list[tuple[str, str]] = []
    body = None
    if method in ("POST", "PUT", "PATCH"):
        body = rng.choice(("json_str", "form", "params", "text"))
        if rng.random() < 0.5:
            ct = rng.choice(("application/json", "text/plain", "application/x-www-form-urlencoded"))
            if body in ("json_str", "text") or ct != "application/json":
                headers.append(("Content-Type", ct))
    extra = rng.random()
    if extra < 0.15:
        headers.append(("Authorization", "'Bearer ' + token"))
    elif extra < 0.3:
        headers.append((rng.choice(("X-Request-Id", "X-Api-Key", "X-Requested-With")), "1"))
    elif extra < 0.5:
        headers.append(
            rng.choice(
                (
                    ("Accept", "application/json"),
                    ("Accept-Language", "ru"),
                    ("Content-Language", "ru"),
                )
            )
        )
    return _Req(path, method, tuple(headers), body)


def _gen_cors(rng: random.Random) -> Variant:
    page = rng.choice(_HOSTS)
    api = rng.choice(_API_HOSTS)
    while True:
        reqs: dict[str, _Req] = {}
        while len(reqs) < 6:
            req = _random_req(rng)
            reqs.setdefault(_req_js(req), req)
        yes = [js for js, r in reqs.items() if _needs_preflight(r)]
        if 2 <= len(yes) <= 4:
            break
    no = [js for js in reqs if js not in yes]
    return make_multi_choice(
        rng,
        f"Страница открыта на https://{page}, константа API = 'https://{api}'. Переменные data, "
        "form, token уже определены. Какие запросы браузер предварит запросом OPTIONS "
        "(CORS preflight)? Отметьте все подходящие.",
        yes,
        no,
        extra={"language": "javascript"},
        explanation=(
            "Preflight нужен для кросс-доменного запроса с методом кроме GET/HEAD/POST, "
            "с заголовками вне списка Accept, Accept-Language, Content-Language, Content-Type, "
            "или с Content-Type кроме text/plain, multipart/form-data, "
            "application/x-www-form-urlencoded. JSON.stringify без заголовка уходит как "
            "text/plain; запрос на свой origin CORS не касается."
        ),
    )


CORS_PREFLIGHT = ItemTemplate(
    id="frontend.cors_preflight",
    specialization="frontend",
    topic="browser_network",
    target_grade="middle",
    format=ItemFormat.MULTI_CHOICE,
    generator=_gen_cors,
    a=1.3,
    b=0.2,
    title="Какие запросы вызовут CORS preflight",
    time_limit_s=240,
)

# --------------------------------------------------------------------------- порядок скриптов

_SCRIPT_KINDS = (
    "inline",
    "inline_defer",
    "inline_async",
    "ext",
    "defer",
    "defer",
    "module",
    "inline_module",
    "async_slow",
)
_SCRIPT_NAMES = ("alpha", "beta", "gamma", "delta", "omega", "sigma", "kappa", "zeta", "theta")


def _script_order(scripts: list[tuple[str, str]]) -> list[str]:
    sync = [n for k, n in scripts if k in ("inline", "inline_defer", "inline_async", "ext")]
    deferred = [n for k, n in scripts if k in ("defer", "module", "inline_module")]
    slow = [n for k, n in scripts if k == "async_slow"]
    return [*sync, *deferred, "DOMContentLoaded", *slow, "load"]


def _script_tag(kind: str, name: str) -> str:
    log = f"console.log('{name}')"
    return {
        "inline": f"<script>{log}</script>",
        "inline_defer": f"<script defer>{log}</script>",
        "inline_async": f"<script async>{log}</script>",
        "ext": f'<script src="{name}.js"></script>',
        "defer": f'<script defer src="{name}.js"></script>',
        "module": f'<script type="module" src="{name}.js"></script>',
        "inline_module": f'<script type="module">{log}</script>',
        "async_slow": f'<script async src="{name}.js"></script>',
    }[kind]


def _gen_scripts(rng: random.Random) -> Variant:
    while True:
        n = rng.randint(4, 6)
        names = rng.sample(_SCRIPT_NAMES, n)
        kinds = [rng.choice(_SCRIPT_KINDS) for _ in range(n)]
        if kinds.count("async_slow") > 1:
            continue
        scripts = list(zip(kinds, names, strict=True))
        order = _script_order(scripts)
        doc_order = [*names, "DOMContentLoaded", "load"]
        sync_n = sum(k in ("inline", "inline_defer", "inline_async", "ext") for k in kinds)
        if order != doc_order and 0 < sync_n < n:
            break
    split = rng.randint(1, n)
    head = [_script_tag(k, nm) for k, nm in scripts[:split]]
    body = [_script_tag(k, nm) for k, nm in scripts[split:]]
    listeners = (
        "<script>\n"
        "  document.addEventListener('DOMContentLoaded', () => console.log('DOMContentLoaded'));\n"
        "  window.addEventListener('load', () => console.log('load'));\n"
        "</script>"
    )
    html = [
        "<!doctype html>",
        "<html>",
        "<head>",
        *(f"  {x}" for x in listeners.split("\n")),
        *(f"  {x}" for x in head),
        "</head>",
        "<body>",
        "  <h1>Каталог</h1>",
        *(f"  {x}" for x in body),
        "</body>",
        "</html>",
    ]
    slow = [nm for k, nm in scripts if k == "async_slow"]
    slow_note = (
        f" Файл {slow[0]}.js загружается дольше, чем разбирается страница и выполняются "
        "остальные скрипты; остальные файлы загружаются мгновенно."
        if slow
        else " Все файлы загружаются мгновенно."
    )
    return make_ordering(
        rng,
        "Каждый внешний файл NAME.js содержит одну строку console.log('NAME')."
        + slow_note
        + " Расставьте сообщения в порядке их появления в консоли браузера.",
        order,
        code="\n".join(html),
        extra={"language": "html"},
        explanation=(
            "Обычные скрипты выполняются при разборе по порядку (defer и async у встроенных "
            "скриптов игнорируются); defer и type=module выполняются после разбора в порядке "
            "документа и до DOMContentLoaded; async — когда загрузится, но до load."
        ),
    )


SCRIPT_ORDER = ItemTemplate(
    id="frontend.script_loading_order",
    specialization="frontend",
    topic="browser_network",
    target_grade="senior",
    format=ItemFormat.ORDERING,
    generator=_gen_scripts,
    a=1.4,
    b=1.3,
    title="Порядок выполнения скриптов: defer, async, module",
    time_limit_s=240,
)

# --------------------------------------------------------------------------- CLS


@dataclass(frozen=True)
class ClsCase:
    viewport: tuple[int, int]  # ширина, высота
    # прямоугольники до сдвига: (x, y, ширина, высота) и смещение (dx, dy)
    elements: tuple[tuple[int, int, int, int, int, int], ...]
    after_input: bool


def _clip(x: int, y: int, w: int, h: int, vw: int, vh: int) -> tuple[int, int, int, int] | None:
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, vw), min(y + h, vh)
    if x0 >= x1 or y0 >= y1:
        return None
    return x0, y0, x1, y1


def _union_area(rects: list[tuple[int, int, int, int]]) -> int:
    xs = sorted({r[0] for r in rects} | {r[2] for r in rects})
    area = 0
    for xa, xb in pairwise(xs):
        spans = sorted((r[1], r[3]) for r in rects if r[0] <= xa and r[2] >= xb)
        covered, cur_end = 0, None
        cur_start = 0
        for y0, y1 in spans:
            if cur_end is None or y0 > cur_end:
                if cur_end is not None:
                    covered += cur_end - cur_start
                cur_start, cur_end = y0, y1
            else:
                cur_end = max(cur_end, y1)
        if cur_end is not None:
            covered += cur_end - cur_start
        area += covered * (xb - xa)
    return area


def cls_score(case: ClsCase) -> float:
    if case.after_input:
        return 0.0
    vw, vh = case.viewport
    rects = []
    dist = 0
    for x, y, w, h, dx, dy in case.elements:
        for r in (_clip(x, y, w, h, vw, vh), _clip(x + dx, y + dy, w, h, vw, vh)):
            if r:
                rects.append(r)
        dist = max(dist, abs(dx), abs(dy))
    impact = _union_area(rects) / (vw * vh)
    return impact * dist / max(vw, vh)


def _cls_case(rng: random.Random) -> ClsCase:
    vw, vh = rng.choice(((400, 800), (360, 720), (1200, 800), (1000, 600), (500, 1000)))
    n = rng.choice((1, 1, 2))
    elements = []
    y = rng.choice((0, 50, 100, 200))
    dy = rng.choice((40, 50, 80, 100, 120, 150, 200))
    for _ in range(n):
        h = rng.choice((100, 150, 200, 250, 300))
        w = vw if rng.random() < 0.6 else rng.choice((vw // 2, vw // 4 * 3))
        x = 0 if w == vw else rng.choice((0, vw - w))
        dx = 0 if rng.random() < 0.85 else rng.choice((-40, 40))
        elements.append((x, y, w, h, dx, dy))
        y += h + rng.choice((0, 20, 40))
    return ClsCase((vw, vh), tuple(elements), rng.random() < 0.12)


def _gen_cls(rng: random.Random) -> Variant:
    case = _cls_case(rng)
    vw, vh = case.viewport
    parts = []
    for i, (x, y, w, h, dx, dy) in enumerate(case.elements, 1):
        move = f"смещается вниз на {dy}px" + (
            f" и {'вправо' if dx > 0 else 'влево'} на {abs(dx)}px" if dx else ""
        )
        parts.append(f"блок {i}: x={x}, y={y}, ширина {w}px, высота {h}px — {move}")
    cause = (
        "Сдвиг произошёл через 200 мс после того, как пользователь нажал кнопку «Показать ещё»."
        if case.after_input
        else "Сдвиг вызван баннером, который подгрузился без участия пользователя."
    )
    score = cls_score(case)
    return Variant(
        prompt=(
            f"Окно просмотра {vw}×{vh}px, страница не прокручена. В одном кадре сдвигаются: "
            + "; ".join(parts)
            + f". {cause} Какой вклад (layout shift score) этот сдвиг внесёт в CLS? Координаты — "
            "левый верхний угол блока до сдвига. Округлите до тысячных."
        ),
        key=NumericKey(round(score, 6), tolerance=0.001),
        extra={"unit": "score"},
        explanation=(
            "score = impact fraction × distance fraction: доля окна, которую занимают блоки "
            "до и после сдвига (объединение), умножить на наибольшее смещение, делённое на "
            "больший размер окна. Сдвиги в течение 500 мс после ввода пользователя не "
            f"учитываются. Ответ {score:.3f}."
        ),
    )


CLS_SCORE = ItemTemplate(
    id="frontend.cls_score",
    specialization="frontend",
    topic="browser_network",
    target_grade="senior",
    format=ItemFormat.NUMERIC,
    generator=_gen_cls,
    a=1.2,
    b=1.9,
    title="Расчёт layout shift score для CLS",
    time_limit_s=300,
)

TEMPLATES = (HTTP_CACHE, CORS_PREFLIGHT, SCRIPT_ORDER, CLS_SCORE)
