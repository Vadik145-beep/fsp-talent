"""Генератор 5 тестовых PDF-резюме и эталонов к ним для проверки разбора резюме (T3.2).

Запуск из корня репозитория:
    pip install -r scripts/samples/requirements.txt
    python scripts/samples/generate_resumes.py

Результат: data/samples/resumes/<имя>.pdf и <имя>.expected.json.
Все люди, компании, телефоны и почты выдуманы (почты на домене example.com).

Шрифты свободные, не системные: DejaVu Sans/Serif (берутся из пакета matplotlib) и
Montserrat (SIL OFL, скачивается с GitHub в scripts/samples/.fonts при первом запуске).
PDF собираются в «инвариантном» режиме reportlab: повторный запуск даёт те же байты.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from reportlab import rl_config

rl_config.invariant = 1  # без даты создания и случайного ID — PDF воспроизводимы

from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_LEFT  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.doctemplate import BaseDocTemplate  # noqa: E402
from reportlab.platypus.flowables import HRFlowable  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "samples" / "resumes"
FONT_CACHE = Path(__file__).resolve().parent / ".fonts"
MONTSERRAT_URL = "https://raw.githubusercontent.com/JulietaUla/Montserrat/master/fonts/ttf/{}.ttf"

ACCENT = colors.HexColor("#310F53")
PINK = colors.HexColor("#FF0053")
GREY = colors.HexColor("#555555")


# ---------------------------------------------------------------- шрифты


def _dejavu_dir() -> Path:
    import matplotlib

    return Path(matplotlib.__file__).parent / "mpl-data" / "fonts" / "ttf"


def _montserrat(name: str) -> Path:
    FONT_CACHE.mkdir(exist_ok=True)
    path = FONT_CACHE / f"{name}.ttf"
    if not path.exists():
        print(f"Скачиваю шрифт {name}…")
        urllib.request.urlretrieve(MONTSERRAT_URL.format(name), path)
    return path


def register_fonts() -> None:
    dv = _dejavu_dir()
    fonts = {
        "Sans": dv / "DejaVuSans.ttf",
        "Sans-Bold": dv / "DejaVuSans-Bold.ttf",
        "Serif": dv / "DejaVuSerif.ttf",
        "Serif-Bold": dv / "DejaVuSerif-Bold.ttf",
        "Serif-Italic": dv / "DejaVuSerif-Italic.ttf",
        "Mont": _montserrat("Montserrat-Regular"),
        "Mont-Bold": _montserrat("Montserrat-Bold"),
    }
    for name, path in fonts.items():
        pdfmetrics.registerFont(TTFont(name, str(path)))


def style(name: str, font: str, size: float, **kw) -> ParagraphStyle:
    kw.setdefault("leading", size * 1.3)
    return ParagraphStyle(name, fontName=font, fontSize=size, alignment=TA_LEFT, **kw)


def bullets(items: list[str], st: ParagraphStyle, mark: str = "•") -> list[Paragraph]:
    return [Paragraph(f"{mark}&nbsp;{x}", st) for x in items]


# ---------------------------------------------------------------- эталон


@dataclass
class Sample:
    name: str  # имя файла без расширения
    layout: str
    expected: dict
    build: callable = field(repr=False, default=None)


def write_expected(sample: Sample) -> None:
    data = {"file": f"{sample.name}.pdf", "layout": sample.layout, **sample.expected}
    path = OUT / f"{sample.name}.expected.json"
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def meta(doc_kwargs: dict, title: str) -> dict:
    return {
        "title": title,
        "author": "fsp-talent samples (синтетические данные)",
        "creator": "scripts/samples/generate_resumes.py",
        **doc_kwargs,
    }


# ---------------------------------------------------------------- 1. одна колонка


def build_backend(path: Path) -> None:
    h1 = style("h1", "Serif-Bold", 20, textColor=ACCENT, spaceAfter=2)
    sub = style("sub", "Serif", 12, textColor=GREY, spaceAfter=6)
    h2 = style("h2", "Serif-Bold", 13, textColor=ACCENT, spaceBefore=10, spaceAfter=4)
    p = style("p", "Serif", 10.5)
    it = style("it", "Serif-Italic", 10, textColor=GREY)
    b = style("b", "Serif", 10.5, leftIndent=10)

    story = [
        Paragraph("Морозов Денис Андреевич", h1),
        Paragraph("Python-разработчик (Middle)", sub),
        Paragraph(
            "Казань · готов к гибридному формату · +7 (917) 245-18-63 · denis.morozov@example.com",
            p,
        ),
        Paragraph("GitHub: github.com/denis-morozov-dev", p),
        HRFlowable(width="100%", color=ACCENT, thickness=1, spaceBefore=6, spaceAfter=4),
        Paragraph("О себе", h2),
        Paragraph(
            "Бэкенд-разработчик, пишу на Python с 2021 года. Делаю API и интеграции для "
            "B2B-сервисов, люблю понятный код и хорошие тесты. Ответственно отношусь "
            "к срокам, легко нахожу общий язык с командой, помогаю новичкам освоиться.",
            p,
        ),
        Paragraph("Опыт работы — 5 лет 6 месяцев", h2),
        Paragraph("<b>ООО «Северный код»</b>, Казань — Backend-разработчик", p),
        Paragraph("Апрель 2023 — настоящее время", it),
        *bullets(
            [
                "Разработка REST API на FastAPI для сервиса складского учёта (40+ эндпоинтов).",
                "Перевод фоновых задач на Celery и Redis: время обработки заказов "
                "сократилось вдвое.",
                "Проектирование схем PostgreSQL, миграции на Alembic, оптимизация запросов.",
                "Наставник для двух junior-разработчиков, проведение code review.",
            ],
            b,
        ),
        Spacer(1, 6),
        Paragraph("<b>ООО «Тёплый софт»</b>, Казань — Junior Python-разработчик", p),
        Paragraph("Апрель 2021 — Март 2023", it),
        *bullets(
            [
                "Поддержка и развитие внутреннего портала на Django.",
                "Интеграция с платёжными шлюзами, покрытие кода тестами на pytest.",
                "Упаковка сервисов в Docker, настройка сборки в GitLab CI.",
            ],
            b,
        ),
        Paragraph("Ключевые навыки", h2),
        Paragraph(
            "Python, FastAPI, Django, PostgreSQL, Redis, Celery, SQLAlchemy, Alembic, "
            "Docker, GitLab CI, pytest, Git, Linux",
            p,
        ),
        Paragraph("Личные качества", h2),
        Paragraph("Ответственность, коммуникабельность, наставничество.", p),
        Paragraph("Образование", h2),
        Paragraph("Казанский федеральный университет, Институт ВМиИТ, бакалавр, 2021", p),
        Paragraph("Языки", h2),
        Paragraph("Русский — родной, английский — B1 (читаю документацию).", p),
    ]
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        **meta({}, "Резюме — Морозов Денис"),
    )
    doc.build(story)


BACKEND = Sample(
    name="01_backend_python_middle",
    layout="Одна колонка, шрифт с засечками, классическое резюме",
    expected={
        "full_name": "Морозов Денис Андреевич",
        "email": "denis.morozov@example.com",
        "phone": "+79172451863",
        "city": "Казань",
        "specialization": "backend",
        "grade": "middle",
        "stack": [
            "Python",
            "FastAPI",
            "Django",
            "PostgreSQL",
            "Redis",
            "Celery",
            "SQLAlchemy",
            "Alembic",
            "Docker",
            "GitLab CI",
            "pytest",
            "Git",
            "Linux",
        ],
        "experience_years": 5.5,
        "roles": ["Backend-разработчик", "Наставник"],
        "soft_skills": ["Ответственность", "Коммуникабельность", "Наставничество"],
        "work_format": "hybrid",
        "links": {"github": "github.com/denis-morozov-dev"},
    },
    build=build_backend,
)


# ---------------------------------------------------------------- 2. две колонки


def build_frontend(path: Path) -> None:
    W, H = A4
    side_w = 74 * mm
    name = style("name", "Mont-Bold", 16, textColor=colors.white, leading=20)
    role = style("role", "Mont", 11, textColor=colors.HexColor("#FFD6E4"), spaceAfter=10)
    sh = style(
        "sh", "Mont-Bold", 10.5, textColor=colors.HexColor("#FFD6E4"), spaceBefore=10, spaceAfter=3
    )
    sp = style("sp", "Mont", 9, textColor=colors.white, leading=12.5)
    h2 = style("h2", "Mont-Bold", 13, textColor=ACCENT, spaceBefore=8, spaceAfter=4)
    p = style("p", "Mont", 9.5, leading=13)
    period = style("period", "Mont", 9, textColor=PINK, spaceAfter=2)
    b = style("b", "Mont", 9.5, leading=13, leftIndent=8)

    side = [
        Paragraph("Колесникова<br/>Анна Сергеевна", name),
        Paragraph("Senior Frontend Developer", role),
        Paragraph("Контакты", sh),
        Paragraph("Санкт-Петербург", sp),
        Paragraph("+7 921 555 03 17", sp),
        Paragraph("anna.kolesnikova@example.com", sp),
        Paragraph("github.com/anna-kolesnikova", sp),
        Paragraph("Формат", sh),
        Paragraph("Удалённо или гибрид", sp),
        Paragraph("Стек", sh),
        *[
            Paragraph(x, sp)
            for x in [
                "TypeScript",
                "JavaScript",
                "React",
                "Redux Toolkit",
                "Next.js",
                "Vite",
                "Webpack",
                "Jest",
                "Playwright",
                "Storybook",
                "HTML",
                "CSS",
            ]
        ],
        Paragraph("Сильные стороны", sh),
        Paragraph("Лидерство", sp),
        Paragraph("Наставничество", sp),
        Paragraph("Работа в команде", sp),
        Paragraph("Языки", sh),
        Paragraph("Английский — B2", sp),
    ]
    main = [
        Paragraph("Профиль", h2),
        Paragraph(
            "8 лет во фронтенде. Последние три года веду команду из пяти разработчиков: "
            "планирование, архитектура, ревью, найм. Отвечаю за дизайн-систему "
            "и производительность клиентских приложений.",
            p,
        ),
        Paragraph("Опыт", h2),
        Paragraph("<b>Тимлид фронтенда</b> · АО «Финтех-Лаб»", p),
        Paragraph("Октябрь 2020 — сейчас", period),
        *bullets(
            [
                "Руковожу командой фронтенда личного кабинета банка (5 человек).",
                "Перевела монолит на Next.js и микрофронтенды, время загрузки −35%.",
                "Создала дизайн-систему на React и Storybook, её используют 4 продукта.",
                "Внедрила e2e-тесты на Playwright и обязательное ревью.",
            ],
            b,
            "—",
        ),
        Spacer(1, 6),
        Paragraph("<b>Frontend-разработчик</b> · ООО «Медиаплатформа»", p),
        Paragraph("Октябрь 2018 — Сентябрь 2020", period),
        *bullets(
            [
                "SPA для редакции на React и Redux, сборка на Webpack.",
                "Покрытие компонентов тестами на Jest, доступность (a11y).",
            ],
            b,
            "—",
        ),
        Paragraph("Образование", h2),
        Paragraph("СПбГУ ИТМО, программная инженерия, 2018", p),
        Paragraph("Выступления", h2),
        Paragraph("Доклад «Дизайн-система за полгода» на городском фронтенд-митапе, 2025.", p),
    ]

    def background(canv, _doc):
        canv.saveState()
        canv.setFillColor(ACCENT)
        canv.rect(0, 0, side_w, H, stroke=0, fill=1)
        canv.restoreState()

    doc = BaseDocTemplate(str(path), pagesize=A4, **meta({}, "Резюме — Колесникова Анна"))
    left = Frame(7 * mm, 12 * mm, side_w - 12 * mm, H - 24 * mm, id="side", showBoundary=0)
    right = Frame(side_w + 8 * mm, 12 * mm, W - side_w - 18 * mm, H - 24 * mm, id="main")
    doc.addPageTemplates([PageTemplate(id="two", frames=[left, right], onPage=background)])
    from reportlab.platypus import FrameBreak

    doc.build(side + [FrameBreak()] + main)


FRONTEND = Sample(
    name="02_frontend_react_senior",
    layout="Две колонки: тёмная боковая панель с контактами и стеком, справа опыт; Montserrat",
    expected={
        "full_name": "Колесникова Анна Сергеевна",
        "email": "anna.kolesnikova@example.com",
        "phone": "+79215550317",
        "city": "Санкт-Петербург",
        "specialization": "frontend",
        "grade": "senior",
        "stack": [
            "TypeScript",
            "JavaScript",
            "React",
            "Redux Toolkit",
            "Next.js",
            "Vite",
            "Webpack",
            "Jest",
            "Playwright",
            "Storybook",
            "HTML",
            "CSS",
        ],
        "experience_years": 8.0,
        "roles": ["Frontend-разработчик", "Тимлид"],
        "soft_skills": ["Лидерство", "Наставничество", "Работа в команде"],
        "work_format": "remote",
        "links": {"github": "github.com/anna-kolesnikova"},
    },
    build=build_frontend,
)


# ---------------------------------------------------------------- 3. таблица навыков


def build_data(path: Path) -> None:
    h1 = style("h1", "Sans-Bold", 17, spaceAfter=2)
    sub = style("sub", "Sans", 11, textColor=PINK, spaceAfter=8)
    h2 = style("h2", "Sans-Bold", 12, spaceBefore=10, spaceAfter=5, textColor=ACCENT)
    p = style("p", "Sans", 9.5, leading=13)
    cell = style("cell", "Sans", 9, leading=11)
    head = style("head", "Sans-Bold", 9, leading=11, textColor=colors.white)

    info = Table(
        [
            [
                Paragraph("Город:", cell),
                Paragraph("Новосибирск (рассматриваю переезд в Москву)", cell),
            ],
            [Paragraph("Телефон:", cell), Paragraph("8-913-402-77-15", cell)],
            [Paragraph("E-mail:", cell), Paragraph("timur.akhmetov@example.com", cell)],
            [Paragraph("Формат:", cell), Paragraph("офис или гибрид", cell)],
        ],
        colWidths=[25 * mm, 120 * mm],
        style=TableStyle(
            [("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]
        ),
        hAlign="LEFT",
    )
    skills = [
        ("Python", "уверенно", "2,5 года"),
        ("Pandas", "уверенно", "2 года"),
        ("NumPy", "уверенно", "2 года"),
        ("scikit-learn", "уверенно", "2 года"),
        ("PyTorch", "базово", "1 год"),
        ("SQL", "уверенно", "2 года"),
        ("PostgreSQL", "средне", "1,5 года"),
        ("Jupyter", "уверенно", "2,5 года"),
        ("Git", "средне", "2 года"),
        ("Docker", "базово", "полгода"),
    ]
    rows = [[Paragraph(x, head) for x in ("Навык", "Уровень", "Практика")]]
    rows += [[Paragraph(a, cell), Paragraph(b, cell), Paragraph(c, cell)] for a, b, c in skills]
    table = Table(rows, colWidths=[50 * mm, 40 * mm, 40 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3EEF8")]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BBBBBB")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    exp = Table(
        [
            [Paragraph("<b>Период</b>", cell), Paragraph("<b>Компания и должность</b>", cell)],
            [
                Paragraph("04.2025 — н.в.", cell),
                Paragraph(
                    "ООО «ДатаСиб», Junior Data Scientist. Модели оттока клиентов "
                    "(градиентный бустинг, логистическая регрессия), подготовка признаков, "
                    "отчёты для бизнеса.",
                    cell,
                ),
            ],
            [
                Paragraph("10.2024 — 03.2025", cell),
                Paragraph(
                    "ООО «ДатаСиб», стажёр-аналитик данных. SQL-выгрузки, дашборды, "
                    "чистка данных в Pandas.",
                    cell,
                ),
            ],
        ],
        colWidths=[35 * mm, 130 * mm],
        hAlign="LEFT",
        style=TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BBBBBB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        ),
    )
    story = [
        Paragraph("Ахметов Тимур Ринатович", h1),
        Paragraph("Junior Data Scientist", sub),
        info,
        Paragraph("Навыки", h2),
        table,
        Paragraph("Опыт работы (2 года)", h2),
        exp,
        Paragraph("Проекты", h2),
        Paragraph(
            "Классификация отзывов покупателей (PyTorch, дообучение BERT) — учебный "
            "проект, точность 0,89. Участник соревнований по алгоритмическому "
            "программированию (студенческий уровень).",
            p,
        ),
        Paragraph("Личные качества", h2),
        Paragraph("Быстро обучаюсь, аналитическое мышление, внимательность к деталям.", p),
        Paragraph("Образование", h2),
        Paragraph("НГУ, механико-математический факультет, бакалавр, 2025.", p),
    ]
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        **meta({}, "Резюме — Ахметов Тимур"),
    )
    doc.build(story)


DATA = Sample(
    name="03_data_ml_junior",
    layout="Таблица контактов, таблица навыков с уровнями, опыт таблицей; DejaVu Sans",
    expected={
        "full_name": "Ахметов Тимур Ринатович",
        "email": "timur.akhmetov@example.com",
        "phone": "+79134027715",
        "city": "Новосибирск",
        "specialization": "data_ml",
        "grade": "junior",
        "stack": [
            "Python",
            "Pandas",
            "NumPy",
            "scikit-learn",
            "PyTorch",
            "SQL",
            "PostgreSQL",
            "Jupyter",
            "Git",
            "Docker",
        ],
        "experience_years": 2.0,
        "roles": ["Data Scientist", "Аналитик данных"],
        "soft_skills": ["Обучаемость", "Аналитическое мышление", "Внимательность к деталям"],
        "work_format": "hybrid",
        "links": {},
    },
    build=build_data,
)


# ---------------------------------------------------------------- 4. минимум текста


def build_qa(path: Path) -> None:
    p = style("p", "Sans", 11, leading=16)
    big = style("big", "Sans-Bold", 15, spaceAfter=6)
    story = [
        Paragraph("Ершова Полина", big),
        Paragraph("Стажёр QA · Екатеринбург", p),
        Paragraph("+7 900 555-33-11 · polina.ershova@example.com", p),
        Spacer(1, 10),
        Paragraph(
            "Ищу стажировку тестировщиком. Прошла курс по ручному тестированию, "
            "тестировала учебные веб-проекты.",
            p,
        ),
        Spacer(1, 6),
        Paragraph("Знаю: тест-кейсы, чек-листы, Postman, SQL, Jira, основы Python.", p),
        Paragraph("Внимательная, усидчивая.", p),
    ]
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=25 * mm,
        rightMargin=25 * mm,
        topMargin=25 * mm,
        **meta({}, "Резюме — Ершова Полина"),
    )
    doc.build(story)


QA = Sample(
    name="04_qa_intern_minimal",
    layout="Минимум текста: полстраницы, без разделов, без отчества и без опыта работы",
    expected={
        "full_name": "Ершова Полина",
        "email": "polina.ershova@example.com",
        "phone": "+79005553311",
        "city": "Екатеринбург",
        "specialization": "qa",
        "grade": "intern",
        "stack": ["Postman", "SQL", "Jira", "Python"],
        "experience_years": 0.0,
        "roles": ["Тестировщик"],
        "soft_skills": ["Внимательность", "Усидчивость"],
        "work_format": None,
        "links": {},
    },
    build=build_qa,
)


# ---------------------------------------------------------------- 5. длинное


def build_devops(path: Path) -> None:
    h1 = style("h1", "Sans-Bold", 18, spaceAfter=2, textColor=ACCENT)
    sub = style("sub", "Sans", 11, spaceAfter=4, textColor=GREY)
    h2 = style("h2", "Sans-Bold", 12.5, spaceBefore=12, spaceAfter=4, textColor=ACCENT)
    h3 = style("h3", "Sans-Bold", 10.5, spaceBefore=6)
    p = style("p", "Sans", 9.5, leading=13.5)
    period = style("period", "Sans", 9, textColor=GREY, spaceAfter=2)
    b = style("b", "Sans", 9.5, leading=13.5, leftIndent=10)

    def job(title: str, when: str, about: str, items: list[str]) -> list:
        return [
            KeepTogether([Paragraph(title, h3), Paragraph(when, period), Paragraph(about, p)]),
            *bullets(items, b),
        ]

    story = [
        Paragraph("Гусев Михаил Олегович", h1),
        Paragraph("Ведущий DevOps-инженер / SRE (Senior)", sub),
        Paragraph("Москва · м. Савёловская · удалённо или гибрид", p),
        Paragraph(
            "Моб.: +7 (903) 712-40-58 · Почта: m.gusev@example.com · GitHub: github.com/mgusev-ops",
            p,
        ),
        HRFlowable(width="100%", color=PINK, thickness=1.2, spaceBefore=6, spaceAfter=2),
        Paragraph("Кратко", h2),
        Paragraph(
            "11 лет 6 месяцев в эксплуатации и DevOps. Строю платформы на Kubernetes для "
            "продуктовых команд, отвечаю за надёжность, наблюдаемость и стоимость "
            "инфраструктуры. Последние годы — тимлид платформенной команды, архитектор "
            "CI/CD. Умею объяснять сложное простыми словами и договариваться с "
            "разработкой, безопасностью и бизнесом.",
            p,
        ),
        Paragraph("Технологии", h2),
        Paragraph("<b>Оркестрация и контейнеры:</b> Kubernetes, Docker, Helm, Argo CD", p),
        Paragraph("<b>Инфраструктура как код:</b> Terraform, Ansible", p),
        Paragraph("<b>CI/CD:</b> GitLab CI, Jenkins", p),
        Paragraph("<b>Наблюдаемость:</b> Prometheus, Grafana, Loki, Alertmanager", p),
        Paragraph("<b>Облака:</b> Yandex Cloud, AWS", p),
        Paragraph("<b>Данные и очереди:</b> PostgreSQL, Kafka, Redis", p),
        Paragraph("<b>Сети и веб:</b> Nginx, HAProxy", p),
        Paragraph("<b>Языки:</b> Bash, Python, Go", p),
        Paragraph("<b>ОС:</b> Linux (Debian, Ubuntu, RHEL)", p),
        Paragraph("Опыт работы", h2),
        *job(
            "Ведущий DevOps-инженер, тимлид платформенной команды — ООО «Облачный ритейл»",
            "Апрель 2020 — по настоящее время (6 лет 6 месяцев)",
            "Маркетплейс, 300+ микросервисов, 60 продуктовых команд.",
            [
                "Спроектировал и запустил внутреннюю платформу на Kubernetes (12 кластеров, "
                "Yandex Cloud и собственный ЦОД), миграция 300 сервисов без простоя.",
                "Ввёл GitOps на Argo CD и шаблоны Helm-чартов: время вывода нового сервиса "
                "сократилось с двух недель до одного дня.",
                "Построил наблюдаемость на Prometheus, Grafana, Loki; SLO и бюджеты ошибок "
                "для 40 ключевых сервисов, дежурства и разборы инцидентов.",
                "Инфраструктура полностью описана в Terraform и Ansible, ревью изменений через "
                "merge request, автоматические проверки политик.",
                "Снизил затраты на облако на 28% за счёт автоскейлинга и прерываемых ВМ.",
                "Руковожу командой из 6 инженеров: найм, развитие, планирование, 1-on-1.",
                "Наставник для 9 инженеров, внутренний курс «Kubernetes для разработчиков».",
                "Провёл переход с Jenkins на GitLab CI для 60 команд.",
                "Организовал учения по отказу дата-центра, RTO сократился до 15 минут.",
                "Настроил резервное копирование PostgreSQL и Kafka с регулярной проверкой "
                "восстановления.",
            ],
        ),
        *job(
            "DevOps-инженер — АО «ГосТехСервис»",
            "Апрель 2017 — Март 2020 (3 года)",
            "Интегратор, проекты для государственных заказчиков.",
            [
                "Перевёл 25 приложений с ручного деплоя на Docker и GitLab CI.",
                "Автоматизировал подготовку серверов на Ansible (200+ хостов, RHEL).",
                "Внедрил мониторинг на Prometheus и Grafana вместо Zabbix.",
                "Писал утилиты на Python и Go для миграции данных и проверки конфигураций.",
                "Настройка Nginx и HAProxy, TLS-сертификаты, балансировка нагрузки.",
                "Участвовал в аттестации систем по требованиям информационной безопасности.",
            ],
        ),
        *job(
            "Системный администратор Linux — ООО «Интернет-Решения»",
            "Апрель 2015 — Март 2017 (2 года)",
            "Хостинг-провайдер.",
            [
                "Администрирование 150 серверов Debian и Ubuntu, веб-сервера, почта, DNS.",
                "Скрипты автоматизации на Bash, резервное копирование.",
                "Дежурства второй линии, работа с обращениями клиентов.",
            ],
        ),
        Paragraph("Ключевые проекты", h2),
        Paragraph(
            "<b>Платформа «Кластер за час».</b> Самообслуживание для команд: заказ "
            "окружения через merge request в репозиторий Terraform. Результат: 400 "
            "окружений в месяц без участия эксплуатации.",
            p,
        ),
        Spacer(1, 4),
        Paragraph(
            "<b>Единая наблюдаемость.</b> Логи, метрики и трассировка в одном интерфейсе, "
            "алерты по SLO вместо порогов. Количество ночных вызовов дежурных снизилось "
            "втрое.",
            p,
        ),
        Spacer(1, 4),
        Paragraph(
            "<b>Миграция в облако.</b> Перенос 80 сервисов из собственного ЦОД в Yandex "
            "Cloud, гибридная сеть, план отката, нулевой простой.",
            p,
        ),
        Paragraph("Образование", h2),
        Paragraph("МИРЭА, информационные системы и технологии, специалист, 2015.", p),
        Paragraph("Курсы и сертификаты", h2),
        *bullets(
            [
                "Certified Kubernetes Administrator (CKA), 2021.",
                "HashiCorp Certified: Terraform Associate, 2022.",
                "Курс по SRE-практикам, 2023.",
            ],
            b,
        ),
        Paragraph("Публикации и выступления", h2),
        *bullets(
            [
                "Статья «Как мы считаем бюджет ошибок для 300 сервисов» в корпоративном блоге.",
                "Доклад о GitOps на отраслевой конференции по эксплуатации, 2024.",
                "Ментор на студенческом хакатоне по продуктовому программированию, 2025.",
            ],
            b,
        ),
        Paragraph("Личные качества", h2),
        Paragraph(
            "Системное мышление, ответственность, наставничество, умение договариваться. "
            "Спокойно работаю в стрессовых ситуациях, люблю порядок в документации.",
            p,
        ),
        Paragraph("Дополнительно", h2),
        Paragraph(
            "Английский — B2 (переписка, документация, созвоны). Готов к командировкам. "
            "Есть загранпаспорт. Рассматриваю роли: ведущий DevOps, SRE-лид, "
            "архитектор платформы.",
            p,
        ),
    ]

    def footer(canv, doc):
        canv.saveState()
        canv.setFont("Sans", 8)
        canv.setFillColor(GREY)
        canv.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Гусев М. О. — стр. {doc.page}")
        canv.restoreState()

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        **meta({}, "Резюме — Гусев Михаил"),
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


DEVOPS = Sample(
    name="05_devops_senior_long",
    layout="Длинное резюме на 2 полные страницы: стек по группам, подробный опыт, проекты, курсы",
    expected={
        "full_name": "Гусев Михаил Олегович",
        "email": "m.gusev@example.com",
        "phone": "+79037124058",
        "city": "Москва",
        "specialization": "devops",
        "grade": "senior",
        "stack": [
            "Kubernetes",
            "Docker",
            "Helm",
            "Argo CD",
            "Terraform",
            "Ansible",
            "GitLab CI",
            "Jenkins",
            "Prometheus",
            "Grafana",
            "Loki",
            "Alertmanager",
            "Yandex Cloud",
            "AWS",
            "PostgreSQL",
            "Kafka",
            "Redis",
            "Nginx",
            "HAProxy",
            "Bash",
            "Python",
            "Go",
            "Linux",
        ],
        "experience_years": 11.5,
        "roles": ["DevOps-инженер", "SRE", "Тимлид", "Архитектор"],
        "soft_skills": [
            "Системное мышление",
            "Ответственность",
            "Наставничество",
            "Умение договариваться",
        ],
        "work_format": "remote",
        "links": {"github": "github.com/mgusev-ops"},
    },
    build=build_devops,
)

SAMPLES = [BACKEND, FRONTEND, DATA, QA, DEVOPS]


def main() -> None:
    register_fonts()
    OUT.mkdir(parents=True, exist_ok=True)
    for s in SAMPLES:
        s.build(OUT / f"{s.name}.pdf")
        write_expected(s)
        print(f"Готово: {s.name}.pdf")


if __name__ == "__main__":
    main()
