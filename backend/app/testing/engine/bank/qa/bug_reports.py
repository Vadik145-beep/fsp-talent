"""QA — дефекты: серьёзность и приоритет, шаги воспроизведения, качество баг-репорта."""

from __future__ import annotations

import random

from ...templates import (
    ItemFormat,
    ItemTemplate,
    Variant,
    make_multi_choice,
    make_ordering,
    make_single_choice,
)

# --------------------------------------------------------------------------- severity и priority

_SP = {
    ("high", "high"): "Серьёзность высокая, приоритет высокий",
    ("high", "low"): "Серьёзность высокая, приоритет низкий",
    ("low", "high"): "Серьёзность низкая, приоритет высокий",
    ("low", "low"): "Серьёзность низкая, приоритет низкий",
}
_PRODUCTS = ("интернет-магазина", "банковского приложения", "сервиса доставки", "онлайн-кинотеатра")


def _gen_severity(rng: random.Random) -> Variant:
    product = rng.choice(_PRODUCTS)
    share = rng.choice((0.1, 0.2, 0.3, 0.5))
    brand = rng.choice(("ФСП-Маркет", "ТалантБанк", "Быстрая Доставка", "КиноПлюс"))
    scenarios = [
        (
            f"На главной странице {product} в логотипе опечатка: «{brand[:-1]}» вместо "
            f"«{brand}». Завтра стартует рекламная кампания.",
            ("low", "high"),
        ),
        (
            f"У {product} ни одна оплата картой не проходит: после ввода кода из SMS — ошибка 500.",
            ("high", "high"),
        ),
        (
            f"Админка {product} падает при экспорте отчёта в устаревший формат XLS. Им пользуются "
            f"{share}% сотрудников, есть экспорт в XLSX, который работает.",
            ("high", "low"),
        ),
        (
            f"В {product} на странице «О компании» в браузере, которым пользуются {share}% "
            "посетителей, иконка соцсети смещена на 2 пикселя.",
            ("low", "low"),
        ),
        (
            f"Приложение {product} теряет все данные пользователя при обновлении на новую версию. "
            "Релиз с этой версией запланирован на сегодня.",
            ("high", "high"),
        ),
        (
            f"В {product} в английской версии раздела помощи, которую открывают {share}% "
            "пользователей, перепутаны местами два абзаца.",
            ("low", "low"),
        ),
    ]
    text, sp = rng.choice(scenarios)
    return make_single_choice(
        rng,
        f"{text}\nКак оценить серьёзность (severity) и приоритет (priority) этого дефекта?",
        _SP[sp],
        [v for k, v in _SP.items() if k != sp],
        explanation=f"Верно: {_SP[sp]}.",
    )


SEVERITY_PRIORITY = ItemTemplate(
    id="qa.severity_priority",
    specialization="qa",
    topic="bug_reports",
    target_grade="intern",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_severity,
    a=1.0,
    b=-1.4,
    title="Серьёзность и приоритет дефекта",
    time_limit_s=90,
)

# --------------------------------------------------------------------------- шаги воспроизведения


def _gen_repro(rng: random.Random) -> Variant:
    login = rng.choice(("qa_user1", "test_buyer", "anna.test", "demo42"))
    item = rng.choice(("Наушники X2", "Чайник Lite", "Рюкзак City", "Кроссовки Run"))
    code = rng.choice(("SALE10", "AUTUMN15", "WELCOME", "FSP2026"))
    city = rng.choice(("Казань", "Самара", "Пермь"))
    file_ = rng.choice(("avatar.png", "photo.jpg", "me.webp"))
    scenarios = [
        (
            f"Промокод {code} не применяется к заказу.",
            [
                f"Открыть сайт магазина и войти под пользователем {login}",
                f"Добавить в корзину товар «{item}»",
                "Перейти в корзину",
                f"Ввести промокод {code} в поле «Промокод»",
                "Нажать «Применить» и посмотреть итоговую сумму",
            ],
        ),
        (
            "Ссылка для сброса пароля из письма ведёт на страницу 404.",
            [
                "Открыть страницу входа",
                "Нажать «Забыли пароль?»",
                f"Ввести email пользователя {login} и отправить форму",
                "Открыть пришедшее письмо в почтовом ящике",
                "Перейти по ссылке из письма",
            ],
        ),
        (
            f"После загрузки {file_} аватар в профиле не меняется.",
            [
                f"Войти под пользователем {login}",
                "Открыть «Профиль»",
                "Нажать «Изменить фото»",
                f"Выбрать файл {file_} и подтвердить загрузку",
                "Обновить страницу профиля и посмотреть на аватар",
            ],
        ),
        (
            f"При бронировании столика в городе {city} не приходит подтверждение.",
            [
                f"Запустить мобильное приложение и войти под пользователем {login}",
                f"Выбрать город {city} и ресторан из списка",
                "Выбрать дату, время и число гостей",
                "Нажать «Забронировать»",
                "Открыть раздел «Мои брони»",
            ],
        ),
    ]
    bug, steps = rng.choice(scenarios)
    return make_ordering(
        rng,
        f"Вы описываете баг: «{bug}». Расставьте шаги воспроизведения в правильном порядке.",
        steps,
        explanation=" → ".join(steps),
    )


REPRO_STEPS = ItemTemplate(
    id="qa.repro_steps_order",
    specialization="qa",
    topic="bug_reports",
    target_grade="intern",
    format=ItemFormat.ORDERING,
    generator=_gen_repro,
    a=0.9,
    b=-1.8,
    title="Шаги воспроизведения бага",
    time_limit_s=120,
)

# --------------------------------------------------------------------------- качество баг-репорта

_ISSUES = {
    "title": "Заголовок не описывает суть проблемы",
    "env": "Не указано окружение (браузер, ОС, версия приложения или стенд)",
    "steps": "Шаги воспроизведения неконкретные, по ним не повторить ошибку",
    "expected": "Не указан ожидаемый результат",
    "two_bugs": "В одном отчёте описаны две разные ошибки",
    "actual": "Не указан фактический результат",
}


def _gen_report_quality(rng: random.Random) -> Variant:
    page = rng.choice(("Корзина", "Профиль", "Каталог", "Оформление заказа"))
    browser = rng.choice(("Chrome 129", "Firefox 131", "Safari 18", "Edge 129"))
    os_ = rng.choice(("Windows 11", "macOS 15", "Ubuntu 24.04"))
    build = f"{rng.randint(1, 4)}.{rng.randint(0, 20)}.{rng.randint(0, 9)}"
    qty = rng.randint(2, 9)
    broken = set(rng.sample(sorted(_ISSUES), rng.randint(2, 3)))
    if "actual" in broken and "two_bugs" in broken:
        broken.discard("two_bugs")
    lines = []
    lines.append(
        "Заголовок: Ничего не работает!!!"
        if "title" in broken
        else f"Заголовок: [{page}] Итог не пересчитывается при изменении количества товара"
    )
    if "env" not in broken:
        lines.append(f"Окружение: {browser}, {os_}, сборка {build}, стенд test")
    lines.append("Шаги:")
    if "steps" in broken:
        lines.append("  1. Немного покликать по корзине")
        lines.append("  2. Что-нибудь поменять")
    else:
        lines.append(f"  1. Открыть страницу «{page}» с одним товаром")
        lines.append(f"  2. Изменить количество товара с 1 на {qty}")
    if "expected" not in broken:
        lines.append(f"Ожидаемый результат: сумма заказа умножилась на {qty}")
    if "actual" not in broken:
        actual = "Фактический результат: сумма заказа осталась прежней"
        if "two_bugs" in broken:
            actual += "; кроме того, в профиле не загружается аватар"
        lines.append(actual)
    lines.append("Вложения: screenshot.png")
    correct = [_ISSUES[k] for k in sorted(broken)]
    wrong = [v for k, v in _ISSUES.items() if k not in broken]
    return make_multi_choice(
        rng,
        "Коллега завёл баг-репорт. Отметьте все его недостатки.",
        correct,
        wrong,
        code="\n".join(lines),
        extra={"min_choices": 1},
        explanation="Недостатки: " + "; ".join(correct),
    )


REPORT_QUALITY = ItemTemplate(
    id="qa.bug_report_quality",
    specialization="qa",
    topic="bug_reports",
    target_grade="junior",
    format=ItemFormat.MULTI_CHOICE,
    generator=_gen_report_quality,
    a=1.1,
    b=-0.8,
    title="Что не так с баг-репортом",
    time_limit_s=150,
)

TEMPLATES = [SEVERITY_PRIORITY, REPRO_STEPS, REPORT_QUALITY]
