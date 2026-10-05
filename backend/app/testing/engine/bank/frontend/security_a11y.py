"""Frontend / безопасность и доступность: XSS-приёмник в коде, отправка cookie по SameSite,
какие элементы попадают в порядок фокуса по Tab."""

from __future__ import annotations

import random

from ...templates import ItemFormat, ItemTemplate, Variant, make_multi_choice

# --------------------------------------------------------------------------- XSS


def _safe_lines(v: str) -> list[str]:
    return [
        f"  title.textContent = {v};",
        f"  input.value = {v};",
        f"  preview.alt = {v};",
        f"  hint.setAttribute('title', {v});",
        f"  counter.textContent = String({v}.length);",
        f"  document.title = 'Поиск: ' + {v};",
        f"  history.replaceState(null, '', '?q=' + encodeURIComponent({v}));",
        f"  localStorage.setItem('lastQuery', {v});",
        f"  console.log('search', {v});",
        "  results.innerHTML = '';",
        "  empty.innerHTML = '<i>Ничего не найдено</i>';",
        f"  const li = document.createElement('li');\n  li.textContent = {v};\n  list.append(li);",
    ]


def _unsafe_lines(v: str) -> list[str]:
    return [
        f"  results.innerHTML = '<b>' + {v} + '</b>';",
        f"  list.insertAdjacentHTML('beforeend', `<li>${{{v}}}</li>`);",
        f"  document.write('<h2>' + {v} + '</h2>');",
        f"  setTimeout('track(\"' + {v} + '\")', 0);",
        f'  banner.outerHTML = `<div class="banner">${{{v}}}</div>`;',
        f"  back.href = {v};",
    ]


def _gen_xss(rng: random.Random) -> Variant:
    v = rng.choice(("q", "query", "term", "text"))
    fn = rng.choice(("renderSearch", "showResults", "updatePage", "applyQuery"))
    unsafe_pool = _unsafe_lines(v)
    unsafe_i = rng.randrange(len(unsafe_pool))
    unsafe = unsafe_pool[unsafe_i]
    safe = rng.sample(_safe_lines(v), rng.randint(4, 6))
    pos = rng.randint(0, len(safe))
    body = [*safe[:pos], unsafe, *safe[pos:]]
    head = [
        "const params = new URLSearchParams(location.search);",
        f"const {v} = params.get('{'next' if unsafe_i == 5 else 'q'}') ?? '';",
        "",
        f"function {fn}({v}) {{",
    ]
    text = "\n".join([*head, *body, "}", "", f"{fn}({v});"])
    lines = text.split("\n")
    bug = lines.index(unsafe.split("\n")[0]) + 1
    return Variant(
        prompt=(
            f"Значение {v} берётся из адресной строки и полностью контролируется атакующим "
            "(ссылку он может прислать жертве). В какой строке XSS-уязвимость? "
            "Укажите номер строки."
        ),
        key=bug,
        code=text,
        extra={"language": "javascript", "line_count": len(lines)},
        explanation=(
            "Опасны приёмники, которые разбирают строку как HTML или код: innerHTML/outerHTML/"
            "insertAdjacentHTML/document.write с пользовательскими данными, setTimeout со "
            "строкой, href с javascript:-ссылкой. textContent, value, setAttribute('title') "
            "безопасны."
        ),
    )


XSS_SINK = ItemTemplate(
    id="frontend.xss_sink",
    specialization="frontend",
    topic="web_security",
    target_grade="junior",
    format=ItemFormat.FIND_BUG_LINE,
    generator=_gen_xss,
    a=1.3,
    b=-0.4,
    title="Найди строку с XSS-уязвимостью",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- SameSite

_SITES = (
    ("bank.example", "evil.test"),
    ("shop.example", "promo.test"),
    ("mail.example", "phish.test"),
    ("crm.example", "ads.test"),
)


def _samesite_scenarios(site: str, other: str) -> list[tuple[str, dict[str, bool]]]:
    """(описание запроса к site, отправится ли cookie при Strict / Lax / None)."""
    sub = f"https://pay.{site}"
    return [
        (
            f"на https://{other} пользователь кликает обычную ссылку на https://{site}/account",
            {"Strict": False, "Lax": True, "None": True},
        ),
        (
            f'страница https://{other} отправляет форму method="POST" на https://{site}/transfer',
            {"Strict": False, "Lax": False, "None": True},
        ),
        (
            f'на https://{other} есть <img src="https://{site}/avatar.png">',
            {"Strict": False, "Lax": False, "None": True},
        ),
        (
            f"скрипт на https://{other} вызывает fetch('https://{site}/api/me', "
            "{ credentials: 'include' })",
            {"Strict": False, "Lax": False, "None": True},
        ),
        (
            f'страница https://{other} встраивает <iframe src="https://{site}/widget">',
            {"Strict": False, "Lax": False, "None": True},
        ),
        (
            f"скрипт на {sub} вызывает fetch('https://{site}/api/me', "
            "{ credentials: 'include' })",
            {"Strict": True, "Lax": True, "None": True},
        ),
        (
            f"пользователь вводит https://{site}/ в адресной строке",
            {"Strict": True, "Lax": True, "None": True},
        ),
        (
            f"скрипт на https://{other} выполняет location.href = 'https://{site}/orders'",
            {"Strict": False, "Lax": True, "None": True},
        ),
        (
            f"пользователь открывает http://{site}/ (без https) из закладки",
            {"Strict": False, "Lax": False, "None": False},
        ),
    ]


def _gen_samesite(rng: random.Random) -> Variant:
    site, other = rng.choice(_SITES)
    mode = rng.choice(("Strict", "Lax", "Lax", "None"))
    cookie = rng.choice(("sid", "session", "auth", "token"))
    scen = _samesite_scenarios(site, other)
    while True:
        chosen = rng.sample(scen, rng.randint(5, 6))
        yes = [d for d, m in chosen if m[mode]]
        no = [d for d, m in chosen if not m[mode]]
        if yes and no:
            break
    return make_multi_choice(
        rng,
        f"Сервер https://{site} установил cookie (вчера; актуальный Chrome, сторонние "
        "cookie не заблокированы):\n"
        f"Set-Cookie: {cookie}={rng.randint(10**5, 10**6)}; Path=/; Secure; HttpOnly; "
        f"SameSite={mode}\n"
        f"В каких случаях браузер приложит эту cookie к запросу на {site}? "
        "Отметьте все подходящие.",
        [d[0].upper() + d[1:] for d in yes],
        [d[0].upper() + d[1:] for d in no],
        extra={"topic": "cookies"},
        explanation=(
            "Strict — только запросы с того же сайта (поддомены — тот же сайт) и прямой ввод "
            "адреса; Lax — плюс переходы верхнего уровня методом GET с чужого сайта; None — "
            "всегда, но только с Secure и по HTTPS. Secure-cookie не уходит по http."
        ),
    )


COOKIE_SAMESITE = ItemTemplate(
    id="frontend.cookie_samesite",
    specialization="frontend",
    topic="web_security",
    target_grade="senior",
    format=ItemFormat.MULTI_CHOICE,
    generator=_gen_samesite,
    a=1.3,
    b=1.1,
    title="Когда cookie уходит с запросом: SameSite",
    time_limit_s=240,
)

# --------------------------------------------------------------------------- фокус по Tab

_LABELS = ("Купить", "Отправить", "Войти", "Корзина", "Подробнее", "Сохранить", "Удалить", "Далее")


def _focus_pool(rng: random.Random) -> tuple[list[str], list[str]]:
    lbl = rng.sample(_LABELS, 6)
    href = rng.choice(("/cart", "/profile", "/help", "#reviews"))
    yes = [
        f"<button>{lbl[0]}</button>",
        f'<a href="{href}">{lbl[1]}</a>',
        f'<input type="text" name="q" placeholder="{lbl[2]}">',
        '<select name="city"><option>Москва</option></select>',
        '<textarea name="comment"></textarea>',
        f'<div tabindex="0">{lbl[3]}</div>',
        f"<details><summary>{lbl[4]}</summary>…</details>",
    ]
    no = [
        f'<div onclick="go()">{lbl[0]}</div>',
        f"<a>{lbl[1]}</a>",
        f'<span class="btn">{lbl[2]}</span>',
        f"<button disabled>{lbl[3]}</button>",
        '<input type="hidden" name="csrf">',
        f'<div tabindex="-1">{lbl[4]}</div>',
        f'<img src="logo.png" alt="{lbl[5]}">',
        f"<button hidden>{lbl[5]}</button>",
    ]
    return yes, no


def _gen_focusable(rng: random.Random) -> Variant:
    yes_pool, no_pool = _focus_pool(rng)
    n_yes = rng.randint(2, 4)
    yes = rng.sample(yes_pool, n_yes)
    no = rng.sample(no_pool, 6 - n_yes)
    return make_multi_choice(
        rng,
        "Какие элементы попадут в последовательность фокуса при нажатии Tab (Chrome, "
        "без JavaScript и дополнительного CSS)? Отметьте все подходящие.",
        yes,
        no,
        extra={"language": "html"},
        explanation=(
            "По Tab фокусируются ссылки с href, кнопки, поля форм, summary и элементы с "
            'tabindex="0". div/span с onclick, <a> без href, disabled, hidden, '
            'type=hidden и tabindex="-1" — нет.'
        ),
    )


A11Y_FOCUSABLE = ItemTemplate(
    id="frontend.a11y_focusable",
    specialization="frontend",
    topic="accessibility",
    target_grade="intern",
    format=ItemFormat.MULTI_CHOICE,
    generator=_gen_focusable,
    a=1.0,
    b=-1.8,
    title="Какие элементы доступны с клавиатуры",
    time_limit_s=120,
)

TEMPLATES = (XSS_SINK, COOKIE_SAMESITE, A11Y_FOCUSABLE)
