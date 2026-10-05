"""Backend · безопасность: SQL-инъекция, хранение паролей, обход каталога (path traversal)."""

from __future__ import annotations

import posixpath
import random
from collections.abc import Callable

from ...templates import ItemFormat, ItemTemplate, Variant, make_single_choice

# ------------------------------------------------------------ SQL-инъекция

# Функции репозитория: (имя, параметр, безопасная версия, уязвимая версия).
# В безопасной версии {ph} — плейсхолдер драйвера (? для sqlite3, %s для psycopg).


def _repo_functions(ph: str) -> list[tuple[str, list[str], list[str]]]:
    return [
        (
            "find_user",
            [
                "def find_user(login):",
                "    cur = conn.cursor()",
                f'    cur.execute("SELECT id, email FROM users WHERE login = {ph}", (login,))',
                "    return cur.fetchone()",
            ],
            [
                "def find_user(login):",
                "    cur = conn.cursor()",
                "    query = f\"SELECT id, email FROM users WHERE login = '{login}'\"",
                "    cur.execute(query)",
                "    return cur.fetchone()",
            ],
        ),
        (
            "list_orders",
            [
                "def list_orders(status):",
                "    cur = conn.cursor()",
                f'    cur.execute("SELECT id, total FROM orders WHERE status = {ph}", (status,))',
                "    return cur.fetchall()",
            ],
            [
                "def list_orders(status):",
                "    cur = conn.cursor()",
                "    query = \"SELECT id, total FROM orders WHERE status = '%s'\" % status",
                "    cur.execute(query)",
                "    return cur.fetchall()",
            ],
        ),
        (
            "search_products",
            [
                "def search_products(term):",
                '    pattern = f"%{term}%"',
                "    cur = conn.cursor()",
                "    cur.execute(",
                f'        "SELECT id, title FROM products WHERE title LIKE {ph}", (pattern,)',
                "    )",
                "    return cur.fetchall()",
            ],
            [
                "def search_products(term):",
                "    cur = conn.cursor()",
                '    query = "SELECT id, title FROM products WHERE title LIKE \'%" + term + "%\'"',
                "    cur.execute(query)",
                "    return cur.fetchall()",
            ],
        ),
        (
            "count_reviews",
            [
                "def count_reviews(author):",
                "    cur = conn.cursor()",
                "    cur.execute(",
                f'        "SELECT count(*) FROM reviews WHERE author = {ph}", (author,)',
                "    )",
                "    return cur.fetchone()[0]",
            ],
            [
                "def count_reviews(author):",
                "    cur = conn.cursor()",
                "    query = \"SELECT count(*) FROM reviews WHERE author = '{}'\".format(author)",
                "    cur.execute(query)",
                "    return cur.fetchone()[0]",
            ],
        ),
    ]


def _gen_sql_injection(rng: random.Random) -> Variant:
    driver = rng.choice(("sqlite3", "psycopg"))
    ph = "?" if driver == "sqlite3" else "%s"
    funcs = rng.sample(_repo_functions(ph), 3)
    bad = rng.randrange(3)
    lines = ["from app.db import get_connection", "", "conn = get_connection()"]
    bug_line = 0
    for i, (_, safe, vuln) in enumerate(funcs):
        lines += ["", ""]
        body = vuln if i == bad else safe
        if i == bad:
            bug_line = len(lines) + 3  # третья строка уязвимой функции — сборка запроса
        lines += body
    return Variant(
        prompt=(
            f"Модуль репозитория (драйвер {driver}). Аргументы функций приходят из HTTP-запроса "
            "без проверки. В какой строке возможна SQL-инъекция — пользовательский ввод "
            "попадает прямо в текст SQL-запроса?"
        ),
        key=bug_line,
        code="\n".join(lines),
        extra={"language": "python", "line_count": len(lines)},
        explanation=f"Строка {bug_line}: запрос собирается из ввода строковыми операциями.",
    )


SQL_INJECTION = ItemTemplate(
    id="backend.sql_injection_line",
    specialization="backend",
    topic="security",
    target_grade="intern",
    format=ItemFormat.FIND_BUG_LINE,
    generator=_gen_sql_injection,
    a=1.1,
    b=-1.3,
    title="Где SQL-инъекция",
    time_limit_s=150,
)

# ------------------------------------------------------------ хранение паролей

_PASSWORDS: dict[tuple[str, str], tuple[list[str], list[str]]] = {
    ("python", "store"): (
        [
            "password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())",
            "password_hash = argon2.PasswordHasher().hash(password)",
        ],
        [
            "password_hash = hashlib.sha256(password.encode()).hexdigest()",
            "password_hash = hashlib.md5((SALT + password).encode()).hexdigest()  "
            "# SALT общий для всех",
            "password_hash = base64.b64encode(password.encode()).decode()",
            "password_hash = Fernet(SECRET_KEY).encrypt(password.encode())",
            "password_hash = hashlib.sha256(os.urandom(16) + password.encode()).hexdigest()",
            "password_hash = hashlib.sha512((user.email + password).encode()).hexdigest()",
        ],
    ),
    ("python", "verify"): (
        ["ok = bcrypt.checkpw(password.encode(), user.password_hash)"],
        [
            "ok = user.password_hash == bcrypt.hashpw(password.encode(), bcrypt.gensalt())",
            "ok = bcrypt.checkpw(user.password_hash, password.encode())",
            "ok = user.password_hash == hashlib.sha256(password.encode()).hexdigest()",
            "ok = user.password_hash.decode() == password",
        ],
    ),
    ("node", "store"): (
        ["const passwordHash = await bcrypt.hash(password, 12);"],
        [
            "const passwordHash = crypto.createHash('sha256').update(password).digest('hex');",
            "const passwordHash = crypto.createHash('md5').update(SALT + password).digest('hex');",
            "const passwordHash = Buffer.from(password).toString('base64');",
            "const passwordHash = jwt.sign({ password }, JWT_SECRET);",
            "const passwordHash = crypto.createHash('sha256')"
            ".update(crypto.randomBytes(16) + password).digest('hex');",
        ],
    ),
    ("node", "verify"): (
        ["const ok = await bcrypt.compare(password, user.passwordHash);"],
        [
            "const ok = user.passwordHash === await bcrypt.hash(password, 12);",
            "const ok = await bcrypt.compare(user.passwordHash, password);",
            "const ok = bcrypt.compare(password, user.passwordHash);  // без await",
            "const ok = user.passwordHash === password;",
        ],
    ),
    ("go", "store"): (
        ["hash, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)"],
        [
            "sum := sha256.Sum256([]byte(password))",
            "sum := md5.Sum([]byte(salt + password)) // salt общий для всех",
            "enc := base64.StdEncoding.EncodeToString([]byte(password))",
            "sum := sha512.Sum512([]byte(user.Email + password))",
        ],
    ),
    ("go", "verify"): (
        ["err := bcrypt.CompareHashAndPassword(user.PasswordHash, []byte(password))"],
        [
            "h, _ := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost); "
            "ok := bytes.Equal(h, user.PasswordHash)",
            "err := bcrypt.CompareHashAndPassword([]byte(password), user.PasswordHash)",
            "ok := string(user.PasswordHash) == password",
        ],
    ),
}
_LANG_NAME = {"python": "Python", "node": "Node.js", "go": "Go"}


def _gen_password(rng: random.Random) -> Variant:
    lang = rng.choice(("python", "node", "go"))
    action = rng.choice(("store", "verify"))
    goods, bads = _PASSWORDS[(lang, action)]
    correct = rng.choice(goods)
    service = rng.choice(("интернет-магазина", "CRM", "онлайн-банка", "сервиса доставки"))
    if action == "store":
        prompt = (
            f"Регистрация пользователя в бэкенде {service} ({_LANG_NAME[lang]}). "
            "Какая строка правильно готовит пароль к сохранению в БД?"
        )
    else:
        prompt = (
            f"Вход пользователя в бэкенде {service} ({_LANG_NAME[lang]}). Пароли в БД хранятся "
            "как bcrypt-хэши. Какая строка правильно проверяет введённый пароль?"
        )
    return make_single_choice(
        rng,
        prompt,
        correct,
        bads,
        extra={"language": lang},
        explanation="Пароль хранят медленным хэшем с солью (bcrypt/argon2), сверяют функцией "
        "библиотеки.",
    )


PASSWORD_HASHING = ItemTemplate(
    id="backend.password_hashing",
    specialization="backend",
    topic="security",
    target_grade="junior",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_password,
    a=1.2,
    b=-0.5,
    title="Как хранить и проверять пароль",
    time_limit_s=150,
)

# ------------------------------------------------------------ обход каталога

BASE_DIR = "/srv/app/uploads"

_GUARDS: dict[str, list[str]] = {
    "none": ["    return posixpath.join(BASE_DIR, filename)"],
    "dots": [
        '    if ".." in filename:',
        "        raise PermissionError(filename)",
        "    return posixpath.join(BASE_DIR, filename)",
    ],
    "prefix": [
        "    path = posixpath.normpath(posixpath.join(BASE_DIR, filename))",
        "    if not path.startswith(BASE_DIR):",
        "        raise PermissionError(filename)",
        "    return path",
    ],
    "commonpath": [
        "    path = posixpath.normpath(posixpath.join(BASE_DIR, filename))",
        "    if posixpath.commonpath([path, BASE_DIR]) != BASE_DIR:",
        "        raise PermissionError(filename)",
        "    return path",
    ],
    "replace": [
        '    filename = filename.replace("../", "")',
        "    return posixpath.normpath(posixpath.join(BASE_DIR, filename))",
    ],
    "basename": ["    return posixpath.join(BASE_DIR, posixpath.basename(filename))"],
}


def _guard_none(f: str) -> str:
    return posixpath.join(BASE_DIR, f)


def _guard_dots(f: str) -> str:
    if ".." in f:
        raise PermissionError(f)
    return posixpath.join(BASE_DIR, f)


def _guard_prefix(f: str) -> str:
    path = posixpath.normpath(posixpath.join(BASE_DIR, f))
    if not path.startswith(BASE_DIR):
        raise PermissionError(f)
    return path


def _guard_commonpath(f: str) -> str:
    path = posixpath.normpath(posixpath.join(BASE_DIR, f))
    if posixpath.commonpath([path, BASE_DIR]) != BASE_DIR:
        raise PermissionError(f)
    return path


def _guard_replace(f: str) -> str:
    return posixpath.normpath(posixpath.join(BASE_DIR, f.replace("../", "")))


def _guard_basename(f: str) -> str:
    return posixpath.join(BASE_DIR, posixpath.basename(f))


GUARD_FUNCS: dict[str, Callable[[str], str]] = {
    "none": _guard_none,
    "dots": _guard_dots,
    "prefix": _guard_prefix,
    "commonpath": _guard_commonpath,
    "replace": _guard_replace,
    "basename": _guard_basename,
}

_INPUTS = (
    "report.pdf",
    "2026/invoice-17.pdf",
    "avatars/u42.png",
    "notes..v2.txt",
    "./readme.md",
    "../../etc/passwd",
    "/etc/passwd",
    "../uploads_old/secret.txt",
    "....//....//....//etc/passwd",
    "img/../../config/settings.py",
    "../uploads/../uploads/report.pdf",
)
NONE_OPTION = "Ни один из этих запросов"


def escapes(guard: str, filename: str) -> bool:
    """Откроет ли сервер файл вне BASE_DIR (ОС сама разрешает «..» при открытии)."""
    try:
        path = GUARD_FUNCS[guard](filename)
    except PermissionError:
        return False
    real = posixpath.normpath(path)
    return not (real == BASE_DIR or real.startswith(BASE_DIR + "/"))


def _gen_path_traversal(rng: random.Random) -> Variant:
    guard = rng.choice(tuple(_GUARDS))
    bad = [f for f in _INPUTS if escapes(guard, f)]
    good = [f for f in _INPUTS if not escapes(guard, f)]
    if bad and rng.random() < 0.8:
        chosen_bad = rng.choice(bad)
        options = [chosen_bad, *rng.sample(good, 3)]
        correct = chosen_bad
    else:
        options = rng.sample(good, 4)
        correct = NONE_OPTION
    labels = [f'name = "{f}"' for f in options]
    correct_label = correct if correct == NONE_OPTION else f'name = "{correct}"'
    distractors = [lb for lb in labels if lb != correct_label]
    if correct != NONE_OPTION:
        distractors.append(NONE_OPTION)
    code = "\n".join(
        [
            "import posixpath",
            "",
            f'BASE_DIR = "{BASE_DIR}"',
            "",
            "",
            "def resolve(filename: str) -> str:",
            *_GUARDS[guard],
            "",
            "",
            "# обработчик: open(resolve(request.query['name']), 'rb') — отдаёт файл клиенту",
        ]
    )
    return make_single_choice(
        rng,
        "Сервис отдаёт загруженные файлы, значение name задаёт клиент (ниже — значения уже "
        "после разбора запроса). С каким значением name клиент прочитает файл вне BASE_DIR?",
        correct_label,
        distractors,
        n_options=5,
        code=code,
        extra={"language": "python"},
        explanation=f"Защита {guard}.",
    )


PATH_TRAVERSAL = ItemTemplate(
    id="backend.path_traversal",
    specialization="backend",
    topic="security",
    target_grade="middle",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_path_traversal,
    a=1.4,
    b=0.5,
    title="Обход каталога: какая защита дырявая",
    time_limit_s=240,
)

TEMPLATES = [SQL_INJECTION, PASSWORD_HASHING, PATH_TRAVERSAL]
