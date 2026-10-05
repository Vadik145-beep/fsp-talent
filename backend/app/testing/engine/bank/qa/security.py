"""QA — безопасность: класс уязвимости, уязвимая строка кода, поток OAuth 2.0 + PKCE."""

from __future__ import annotations

import random

from ...templates import ItemFormat, ItemTemplate, Variant, make_ordering, make_single_choice

# --------------------------------------------------------------------------- класс уязвимости

_VULNS = {
    "sqli": "SQL-инъекция",
    "xss": "Хранимый XSS",
    "idor": "IDOR — нарушение контроля доступа к чужим объектам",
    "traversal": "Path traversal — выход за пределы каталога",
    "redirect": "Open redirect",
    "csrf": "CSRF — подделка межсайтового запроса",
    "ssrf": "SSRF — запрос сервера на внутренний адрес",
}


def _gen_vuln_type(rng: random.Random) -> Variant:
    rid = rng.randint(1000, 99999)
    host = rng.choice(("shop.example.ru", "bank.test", "crm.local"))
    evil = rng.choice(("evil.example.com", "phish.test", "attacker.site"))
    scenarios = [
        (
            f"GET https://{host}/search?q=' OR '1'='1 возвращает все записи таблицы товаров.",
            "sqli",
        ),
        (
            f"В отзыв на {host} вставили <img src=x onerror=alert(document.cookie)>; "
            "код срабатывает у каждого, кто открывает страницу товара.",
            "xss",
        ),
        (
            f"Пользователь открыл свой заказ /api/orders/{rid}, поменял номер на {rid + 1} "
            "и увидел чужой заказ с адресом и телефоном.",
            "idor",
        ),
        (
            f"GET https://{host}/download?file=../../../etc/passwd возвращает содержимое "
            "системного файла.",
            "traversal",
        ),
        (
            f"Ссылка https://{host}/login?next=https://{evil}/ после входа отправляет "
            "пользователя на чужой сайт.",
            "redirect",
        ),
        (
            f"Страница на {evil} незаметно отправляет POST-форму на https://{host}/transfer; "
            "браузер жертвы прикладывает её cookie, и перевод проходит без проверки токена.",
            "csrf",
        ),
        (
            f"Функция предпросмотра ссылок на {host} по URL http://169.254.169.254/latest/"
            "meta-data/ вернула служебные данные облака.",
            "ssrf",
        ),
    ]
    text, correct = rng.choice(scenarios)
    return make_single_choice(
        rng,
        f"При тестировании безопасности обнаружено: {text}\nКак называется уязвимость?",
        _VULNS[correct],
        [v for k, v in _VULNS.items() if k != correct],
        explanation=f"Верно: {_VULNS[correct]}.",
    )


VULN_TYPE = ItemTemplate(
    id="qa.vuln_type",
    specialization="qa",
    topic="security",
    target_grade="junior",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_vuln_type,
    a=1.2,
    b=-0.5,
    title="Класс уязвимости по симптому",
    time_limit_s=120,
)

# --------------------------------------------------------------------------- уязвимая строка

# (безопасный вариант, индекс заменяемой строки, уязвимая строка)
_SNIPPETS: tuple[tuple[list[str], int, str], ...] = (
    (
        [
            '@app.get("/users")',
            "def find_user():",
            '    email = request.args["email"]',
            '    row = db.execute("SELECT id, name FROM users WHERE email = ?", (email,))'
            ".fetchone()",
            "    return jsonify(dict(row) if row else {})",
        ],
        3,
        "    row = db.execute(f\"SELECT id, name FROM users WHERE email = '{email}'\").fetchone()",
    ),
    (
        [
            '@app.get("/orders/<int:order_id>")',
            "@login_required",
            "def get_order(order_id):",
            "    order = Order.query.filter_by(id=order_id, user_id=current_user.id)"
            ".first_or_404()",
            "    return jsonify(order.to_dict())",
        ],
        3,
        "    order = Order.query.get_or_404(order_id)",
    ),
    (
        [
            '@app.get("/download")',
            "def download():",
            '    name = request.args["file"]',
            "    return send_from_directory(UPLOAD_DIR, name)",
        ],
        3,
        "    return send_file(os.path.join(UPLOAD_DIR, name))",
    ),
    (
        [
            '@app.get("/search")',
            "def search():",
            '    q = request.args.get("q", "")',
            '    return render_template("search.html", q=q)',
        ],
        3,
        '    return f"<h1>Результаты по запросу: {q}</h1>"',
    ),
    (
        [
            "def set_password(user, password):",
            "    user.password_hash = generate_password_hash(password)",
            "    db.session.commit()",
        ],
        1,
        "    user.password_hash = hashlib.md5(password.encode()).hexdigest()",
    ),
    (
        [
            '@app.post("/ping")',
            "def ping():",
            '    host = request.form["host"]',
            '    out = subprocess.run(["ping", "-c", "1", host], capture_output=True, text=True)',
            "    return out.stdout",
        ],
        3,
        '    out = subprocess.run(f"ping -c 1 {host}", shell=True, capture_output=True, text=True)',
    ),
)

_HEADER = (
    "import hashlib",
    "import os",
    "import subprocess",
    "",
    "from flask import Flask, jsonify, render_template, request, send_file, send_from_directory",
    "from flask_login import current_user, login_required",
    "from werkzeug.security import generate_password_hash",
    "",
    "app = Flask(__name__)",
    'UPLOAD_DIR = "/srv/uploads"',
)


def _gen_vulnerable_line(rng: random.Random) -> Variant:
    chosen = rng.sample(range(len(_SNIPPETS)), rng.randint(3, 4))
    bad = rng.choice(chosen)
    lines = list(_HEADER)
    bug = -1
    for idx in chosen:
        safe, pos, vuln = _SNIPPETS[idx]
        block = list(safe)
        lines += ["", ""]
        if idx == bad:
            block[pos] = vuln
            bug = len(lines) + pos
        lines += block
    return Variant(
        prompt=(
            "В этом коде на Flask ровно одна уязвимость, остальное написано безопасно "
            "(db, Order и шаблоны определены в другом месте). В какой строке уязвимость? "
            "Укажите номер строки."
        ),
        key=bug + 1,
        code="\n".join(lines),
        extra={"language": "python", "line_count": len(lines)},
        explanation=f"Строка {bug + 1}: {lines[bug].strip()}",
    )


VULNERABLE_LINE = ItemTemplate(
    id="qa.vulnerable_line",
    specialization="qa",
    topic="security",
    target_grade="senior",
    format=ItemFormat.FIND_BUG_LINE,
    generator=_gen_vulnerable_line,
    a=1.5,
    b=1.3,
    title="Найди уязвимую строку",
    time_limit_s=210,
)

# --------------------------------------------------------------------------- OAuth 2.0 + PKCE


def _gen_oauth(rng: random.Random) -> Variant:
    client = rng.choice(("mobile-app", "spa-web", "partner-portal"))
    idp = rng.choice(("auth.example.ru", "sso.company.local", "id.test"))
    api = rng.choice(("api.example.ru", "gateway.company.local", "api.test"))
    scope = rng.choice(("orders:read", "profile email", "payments:write"))
    steps = [
        f"Клиент {client} генерирует случайный code_verifier и вычисляет code_challenge",
        f"Браузер перенаправляется на https://{idp}/authorize с code_challenge и scope={scope}",
        "Пользователь вводит логин и пароль и подтверждает доступ",
        f"{idp} перенаправляет на redirect_uri клиента с одноразовым параметром code",
        f"Клиент отправляет POST https://{idp}/token с code и code_verifier",
        "Клиент получает access_token (и refresh_token)",
        f"Клиент вызывает https://{api} с заголовком Authorization: Bearer <access_token>",
    ]
    return make_ordering(
        rng,
        "Вы тестируете вход через OAuth 2.0 Authorization Code + PKCE. Расставьте шаги "
        "потока в правильном порядке.",
        steps,
        explanation="verifier → /authorize → логин → code → /token → токены → API.",
    )


OAUTH = ItemTemplate(
    id="qa.oauth_pkce_order",
    specialization="qa",
    topic="security",
    target_grade="senior",
    format=ItemFormat.ORDERING,
    generator=_gen_oauth,
    a=1.2,
    b=1.0,
    title="Поток OAuth 2.0 + PKCE",
    time_limit_s=180,
)

TEMPLATES = [VULN_TYPE, VULNERABLE_LINE, OAUTH]
