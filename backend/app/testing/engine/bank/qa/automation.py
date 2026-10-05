"""QA — автотесты: уровень теста, локаторы, флаки-тесты, порядок фикстур pytest."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ...templates import ItemFormat, ItemTemplate, Variant, make_single_choice

# --------------------------------------------------------------------------- уровень теста

_LEVELS = {
    "unit": "Модульный (unit) тест",
    "integration": "Интеграционный тест",
    "e2e": "Сквозной (E2E) тест через интерфейс",
    "load": "Нагрузочный тест",
}


def _gen_level(rng: random.Random) -> Variant:
    fn = rng.choice(("calc_discount", "parse_phone", "format_price", "validate_inn"))
    db = rng.choice(("PostgreSQL", "MySQL", "MongoDB"))
    scenarios = [
        (
            f"Проверить функцию {fn}() на десятке наборов входных данных, без сети и базы.",
            "unit",
        ),
        (
            f"Проверить, что репозиторий заказов сохраняет запись в настоящую {db} "
            "(в контейнере) и читает её обратно.",
            "integration",
        ),
        (
            "Проверить, что пользователь регистрируется в браузере, получает письмо, "
            "переходит по ссылке и входит в личный кабинет.",
            "e2e",
        ),
        (
            "Каких тестов по «пирамиде тестирования» в проекте должно быть больше всего?",
            "unit",
        ),
        (
            "Какие тесты по «пирамиде тестирования» самые медленные и хрупкие, поэтому их "
            "должно быть меньше всего?",
            "e2e",
        ),
        (
            f"Проверить, что сервис корзины правильно вызывает сервис цен по HTTP и разбирает "
            f"его ответ (оба сервиса подняты, {db} — тестовая).",
            "integration",
        ),
        (
            f"Проверить, что {fn}() бросает ValueError на пустой строке.",
            "unit",
        ),
    ]
    text, correct = rng.choice(scenarios)
    return make_single_choice(
        rng,
        f"{text}\nКакой вид теста подходит?" if not text.endswith("?") else text,
        _LEVELS[correct],
        [v for k, v in _LEVELS.items() if k != correct],
        explanation=f"Верно: {_LEVELS[correct]}.",
    )


TEST_LEVEL = ItemTemplate(
    id="qa.test_level_choice",
    specialization="qa",
    topic="automation",
    target_grade="intern",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_level,
    a=1.0,
    b=-1.6,
    title="Какой уровень теста выбрать",
    time_limit_s=90,
)

# --------------------------------------------------------------------------- локаторы


def _gen_locator(rng: random.Random) -> Variant:
    f1, f2 = rng.sample(("login", "signup", "search", "feedback", "subscribe", "order"), 2)
    t1 = rng.choice(("Войти", "Отправить", "Сохранить", "Продолжить"))
    t2 = rng.choice([t for t in ("Найти", "Подписаться", "Применить", "Далее") if t != t1])
    n1, n2 = rng.sample(("email", "username", "q", "phone", "code"), 2)
    testid = f"{f1}-submit" if rng.random() < 0.5 else None
    tid_attr = f' data-testid="{testid}"' if testid else ""
    html = "\n".join(
        [
            f'<form id="{f1}-form">',
            f'  <input type="text" name="{n1}" class="input">',
            f'  <button type="submit" class="btn btn-primary"{tid_attr}>{t1}</button>',
            '  <button type="button" class="btn">Отмена</button>',
            "</form>",
            f'<form id="{f2}-form">',
            f'  <input type="text" name="{n2}" class="input">',
            f'  <button type="submit" class="btn btn-primary">{t2}</button>',
            "</form>",
        ]
    )
    good = [
        f'#{f1}-form button[type="submit"]',
        f"#{f1}-form .btn-primary",
        f'//form[@id="{f1}-form"]//button[@type="submit"]',
        f'//button[text()="{t1}"]',
    ]
    if testid:
        good.append(f'[data-testid="{testid}"]')
    bad = [
        ".btn-primary",
        'button[type="submit"]',
        f"#{f1}-form .btn",
        f"#{f1}-form button",
        '//button[@type="submit"]',
        f'#{f2}-form button[type="submit"]',
        f'//form[@id="{f2}-form"]//button',
        "button.primary",
    ]
    return make_single_choice(
        rng,
        f"Нужен локатор (CSS или XPath), который находит ровно одну кнопку «{t1}» и больше "
        "ни одного элемента на странице. Какой подходит?",
        rng.choice(good),
        bad,
        code=html,
        extra={"language": "html"},
        explanation="Остальные находят несколько элементов, чужую кнопку или ничего.",
    )


LOCATOR = ItemTemplate(
    id="qa.locator_choice",
    specialization="qa",
    topic="automation",
    target_grade="junior",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_locator,
    a=1.3,
    b=-0.4,
    title="Уникальный локатор элемента",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- флаки-тест


def _flaky_program(rng: random.Random) -> tuple[str, list[str], int]:
    page = rng.choice(("profile", "settings", "cart", "checkout"))
    kind = rng.randrange(5)
    if kind == 0:
        lines = [
            "def test_save_settings(driver):",
            f'    driver.get(BASE_URL + "/{page}")',
            '    driver.find_element(By.ID, "name").send_keys("Анна")',
            '    driver.find_element(By.ID, "save").click()',
            f"    time.sleep({rng.choice((1, 2, 3))})",
            '    toast = driver.find_element(By.CSS_SELECTOR, ".toast")',
            '    assert toast.text == "Сохранено"',
        ]
        return (
            "Тест иногда падает на медленном CI: «.toast» не найден, локально проходит.",
            lines,
            4,
        )
    if kind == 1:
        lines = [
            "created_ids = []",
            "",
            "def test_create_order(api):",
            f'    resp = api.post("/orders", json={{"item": "{page}", "qty": 1}})',
            "    assert resp.status_code == 201",
            '    created_ids.append(resp.json()["id"])',
            "",
            "def test_cancel_order(api):",
            '    resp = api.post(f"/orders/{created_ids[0]}/cancel")',
            "    assert resp.status_code == 200",
        ]
        return (
            "test_cancel_order проходит в полном прогоне, но падает при запуске отдельно "
            "или в случайном порядке (pytest-randomly).",
            lines,
            8,
        )
    if kind == 2:
        lines = [
            "def test_order_date(api):",
            '    resp = api.post("/orders", json={"qty": 1})',
            "    assert resp.status_code == 201",
            '    created = date.fromisoformat(resp.json()["created_date"])',
            "    assert created == datetime.now().date()",
        ]
        return "Тест падает примерно раз в сутки — если прогон идёт около полуночи.", lines, 4
    if kind == 3:
        lines = [
            "def test_register(api):",
            f'    email = f"user{{random.randint(1, {rng.choice((50, 100, 500))})}}@test.ru"',
            '    resp = api.post("/register", json={"email": email, "password": "Qwerty123!"})',
            "    assert resp.status_code == 201",
            '    assert resp.json()["email"] == email',
        ]
        return (
            "Тест иногда падает с ответом «пользователь с таким email уже существует» "
            "(база между прогонами не очищается).",
            lines,
            1,
        )
    lines = [
        "def test_tags(api):",
        f'    api.post("/{page}/tags", json=["new", "sale", "hit"])',
        f'    resp = api.get("/{page}/tags")',
        '    assert list(set(resp.json())) == ["new", "sale", "hit"]',
    ]
    return (
        "Тест то проходит, то падает на сравнении списков, хотя API всегда возвращает "
        "одни и те же теги в одном порядке.",
        lines,
        3,
    )


_FLAKY_HEADER = (
    "import random",
    "import time",
    "from datetime import date, datetime",
    "from selenium.webdriver.common.by import By",
)


def _gen_flaky(rng: random.Random) -> Variant:
    symptom, lines, bug = _flaky_program(rng)
    header = [h for h in _FLAKY_HEADER if rng.random() < 0.6] + [""]
    lines = header + lines
    bug += len(header)
    return Variant(
        prompt=f"{symptom} В какой строке причина нестабильности? Укажите номер строки.",
        key=bug + 1,
        code="\n".join(lines),
        extra={"language": "python", "line_count": len(lines)},
        explanation=f"Строка {bug + 1}: {lines[bug].strip()}",
    )


FLAKY = ItemTemplate(
    id="qa.flaky_test_line",
    specialization="qa",
    topic="automation",
    target_grade="middle",
    format=ItemFormat.FIND_BUG_LINE,
    generator=_gen_flaky,
    a=1.4,
    b=0.5,
    title="Почему тест нестабилен",
    time_limit_s=180,
)

# --------------------------------------------------------------------------- фикстуры pytest

_SCOPE_RANK = {"session": 0, "module": 1, "function": 2}


@dataclass
class Fixture:
    name: str
    scope: str
    deps: list[str] = field(default_factory=list)
    autouse: bool = False
    teardown: bool = True


def simulate_pytest(fixtures: dict[str, Fixture], tests: list[tuple[str, list[str]]]) -> list[str]:
    """Порядок print: setup по scope и зависимостям, teardown в обратном порядке."""
    out: list[str] = []
    active: dict[str, list[str]] = {"session": [], "module": [], "function": []}
    autouse = [f.name for f in fixtures.values() if f.autouse]

    def ensure(name: str) -> None:
        fx = fixtures[name]
        if name in active[fx.scope]:
            return
        for dep in fx.deps:
            ensure(dep)
        out.append(f"{name}+")
        active[fx.scope].append(name)

    def finish(scope: str) -> None:
        for name in reversed(active[scope]):
            if fixtures[name].teardown:
                out.append(f"{name}-")
        active[scope] = []

    for test_name, args in tests:
        closure = [*autouse]
        for a in args:
            if a not in closure:
                closure.append(a)
        i = 0
        while i < len(closure):
            for dep in fixtures[closure[i]].deps:
                if dep not in closure:
                    closure.append(dep)
            i += 1
        closure.sort(key=lambda n: _SCOPE_RANK[fixtures[n].scope])
        for name in closure:
            ensure(name)
        out.append(f"run_{test_name}")
        finish("function")
    finish("module")
    finish("session")
    return out


def _render_fixture(fx: Fixture) -> list[str]:
    params = []
    if fx.scope != "function":
        params.append(f'scope="{fx.scope}"')
    if fx.autouse:
        params.append("autouse=True")
    deco = "@pytest.fixture" + (f"({', '.join(params)})" if params else "")
    lines = [deco, f"def {fx.name}({', '.join(fx.deps)}):", f'    print("{fx.name}+")']
    if fx.teardown:
        lines += ["    yield", f'    print("{fx.name}-")']
    else:
        lines.append("    return None")
    return lines


def _gen_pytest_order(rng: random.Random) -> Variant:
    s_name, a_name, b_name, u_name = rng.choice(
        (
            ("db", "client", "user", "clean"),
            ("server", "api", "token", "logs"),
            ("cfg", "app", "admin", "tmp"),
        )
    )
    while True:
        fixtures = {
            s_name: Fixture(s_name, rng.choice(("session", "module"))),
            a_name: Fixture(a_name, "function", [s_name] if rng.random() < 0.6 else []),
            b_name: Fixture(
                b_name, "function", rng.choice(([a_name], [s_name], [], [a_name, s_name]))
            ),
        }
        if rng.random() < 0.45:
            fixtures[u_name] = Fixture(u_name, "function", autouse=True)
        for fx in fixtures.values():
            fx.teardown = rng.random() < 0.8
        names = [s_name, a_name, b_name]
        tests = []
        for t in rng.sample(("login", "logout", "search", "pay", "export"), rng.randint(2, 3)):
            args = rng.sample(names, rng.randint(1, 2))
            tests.append((t, args))
        out = simulate_pytest(fixtures, tests)
        if 8 <= len(out) <= 18:  # не слишком коротко и не слишком длинно
            break
    order = [s_name, a_name, b_name] + ([u_name] if u_name in fixtures else [])
    rng.shuffle(order)
    blocks = ["import pytest"]
    blocks += ["\n".join(_render_fixture(fixtures[name])) for name in order]
    blocks += [f'def test_{t}({", ".join(args)}):\n    print("run_{t}")' for t, args in tests]
    code = "\n\n\n".join(blocks)
    return Variant(
        prompt=(
            "Файл запускают командой pytest -s, тесты выполняются в порядке объявления. "
            "Что напечатают вызовы print? Перечислите значения через пробел в порядке вывода, "
            "служебный вывод pytest не учитывайте."
        ),
        key=" ".join(out),
        code=code,
        extra={"language": "python"},
        explanation="Сначала фикстуры большего scope, зависимости раньше зависимых; "
        "teardown в обратном порядке.",
    )


PYTEST_ORDER = ItemTemplate(
    id="qa.pytest_fixture_order",
    specialization="qa",
    topic="automation",
    target_grade="senior",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_pytest_order,
    a=1.5,
    b=1.4,
    title="Порядок фикстур pytest",
    time_limit_s=300,
)

TEMPLATES = [TEST_LEVEL, LOCATOR, FLAKY, PYTEST_ORDER]
