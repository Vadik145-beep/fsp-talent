"""Разбор PDF-резюме в предзаполненную форму профиля (T3.2).

pdfplumber → текст (страницы в две колонки режем по колонкам) → правила по полям
(+ LLM дозаполняет пустые поля, если подключена) → поля с уверенностью.
Кандидат подтверждает форму сам.
"""

from __future__ import annotations

import io
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

import pdfplumber
from fastapi import UploadFile
from pydantic import BaseModel, Field, create_model
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.candidates.models import Resume
from app.candidates.schemas import ResumeParseResult
from app.core.errors import AppError
from app.nlp import llm
from app.nlp.settings import get_nlp_settings
from app.nlp.skills_lexicon import SkillMention, find_skills, is_catalog, label, normalize_skill
from app.nlp.text_rules import (
    CITIES,
    detect_city,
    detect_grade,
    detect_specialization,
    detect_work_formats,
)

log = logging.getLogger(__name__)

PDF_TYPES = ("application/pdf", "application/x-pdf", "application/octet-stream")


class ResumeParseResponse(ResumeParseResult):
    """Ответ загрузки резюме. Расширение контракта: `warnings` — что не удалось прочитать."""

    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------- текст из PDF


@dataclass
class PdfText:
    text: str
    pages: int
    two_column_pages: list[int] = field(default_factory=list)


def _column_split(page: Any) -> float | None:
    """x-координата вертикального просвета между колонками или None (одна колонка).

    Просвет — полоса, которую почти не пересекают слова, а слева и справа от неё
    заметная доля текста. Таблицы на одноколоночной странице не режем: абзацы во всю
    ширину пересекают любую полосу.
    """
    words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
    n = len(words)
    if n < 30:
        return None
    width = float(page.width)
    valid: list[float] = []
    x = width * 0.2
    while x <= width * 0.65:
        crossing = sum(1 for w in words if w["x0"] < x < w["x1"])
        left = sum(1 for w in words if w["x1"] <= x)
        right = n - left - crossing
        if crossing <= 1 and left >= 0.15 * n and right >= 0.15 * n:
            valid.append(x)
        x += 2.0
    if not valid:
        return None
    # самый широкий непрерывный просвет, режем по его середине
    runs: list[list[float]] = [[valid[0]]]
    for v in valid[1:]:
        if v - runs[-1][-1] <= 2.01:
            runs[-1].append(v)
        else:
            runs.append([v])
    best = max(runs, key=len)
    if len(best) < 3:  # просвет уже 6 pt — скорее межсловный пробел
        return None
    return (best[0] + best[-1]) / 2


def extract_pdf_text(data: bytes, max_pages: int = 10) -> PdfText:
    parts: list[str] = []
    two_col: list[int] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages = pdf.pages[:max_pages]
        for i, page in enumerate(pages, start=1):
            split = _column_split(page)
            if split is None:
                parts.append(page.extract_text() or "")
                continue
            two_col.append(i)
            h, w = float(page.height), float(page.width)
            left = page.crop((0, 0, split, h)).extract_text() or ""
            right = page.crop((split, 0, w, h)).extract_text() or ""
            parts.append(left + "\n" + right)
        return PdfText("\n".join(parts), len(pdf.pages), two_col)


# ---------------------------------------------------------------- разделы

SECTION_HEADERS: dict[str, tuple[str, ...]] = {
    "skills": (
        "ключевые навыки",
        "навыки",
        "стек",
        "технологии",
        "технический стек",
        "технологический стек",
        "hard skills",
        "skills",
        "инструменты",
        "знаю",
        "умею",
    ),
    "soft": (
        "личные качества",
        "сильные стороны",
        "soft skills",
        "качества",
        "о себе как о сотруднике",
    ),
    "about": ("о себе", "профиль", "кратко", "summary", "обо мне", "цель"),
    "experience": ("опыт работы", "опыт", "experience", "места работы"),
    "contacts": ("контакты", "контактная информация", "contacts"),
    "other": (
        "образование",
        "проекты",
        "ключевые проекты",
        "курсы",
        "курсы и сертификаты",
        "сертификаты",
        "языки",
        "выступления",
        "публикации",
        "публикации и выступления",
        "дополнительно",
        "формат",
        "достижения",
        "хобби",
    ),
}


_HEADER_INDEX = {
    name.replace("ё", "е"): kind for kind, names in SECTION_HEADERS.items() for name in names
}


def _header_kind(line: str) -> tuple[str, str] | None:
    """Строка — заголовок раздела? → (вид, текст после двоеточия).

    «Опыт работы (2 года)» и «Опыт работы — 5 лет» — тоже заголовки.
    """
    head, sep, rest = line.strip().partition(":")
    core = re.split(r"\s*[(—–]\s*|\s+-\s+", head.lower().replace("ё", "е"))[0].strip(" .")
    kind = _HEADER_INDEX.get(core)
    if kind is None:
        return None
    return kind, rest.strip() if sep else ""


def split_sections(lines: list[str]) -> dict[str, list[str]]:
    """Строки по разделам; «header» — всё до первого заголовка.

    Строка «Ключ: значение» начинает новый раздел только для навыков («Знаю: Postman, SQL»);
    «Языки: Bash, Python» внутри раздела технологий остаётся в нём.
    """
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in lines:
        found = _header_kind(line)
        if found and (not found[1] or found[0] == "skills"):
            current = found[0]
            sections.setdefault(current, [])
            if found[1]:
                sections[current].append(found[1])
            # «Опыт работы — 5 лет 6 месяцев»: сам заголовок тоже несёт данные
            if current == "experience":
                sections[current].append(line)
            continue
        sections.setdefault(current, []).append(line)
    return sections


# ---------------------------------------------------------------- поля

EMAIL_RE = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
PHONE_RE = re.compile(r"(?<!\d)(?:\+7|8)[\s\-(]*\d{3}[\s\-)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}(?!\d)")
GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[\w\-.]+", re.IGNORECASE)
LINK_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:gitlab\.com|linkedin\.com/in|t\.me|habr\.com/ru/users)/[\w\-./]+",
    re.IGNORECASE,
)
NAME_WORD = re.compile(r"^[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?$")
NOT_NAME = {
    "Профиль",
    "Контакты",
    "Резюме",
    "Опыт",
    "Стек",
    "Навыки",
    "Образование",
    "Формат",
    "Языки",
    "Кратко",
}
_CITY_WORDS = {f.capitalize() for forms in CITIES.values() for f in forms}

MONTHS = {
    "янв": 1,
    "фев": 2,
    "мар": 3,
    "апр": 4,
    "мая": 5,
    "май": 5,
    "июн": 6,
    "июл": 7,
    "авг": 8,
    "сен": 9,
    "окт": 10,
    "ноя": 11,
    "дек": 12,
}
_MONTH = r"(?:январ\w*|феврал\w*|март\w*|апрел\w*|ма[йя]\w*|июн\w*|июл\w*|август\w*|сентябр\w*|октябр\w*|ноябр\w*|декабр\w*|янв\.?|фев\.?|мар\.?|апр\.?|авг\.?|сен\.?|окт\.?|ноя\.?|дек\.?)"  # noqa: E501
_NOW = r"(?:по\s+)?(?:настоящее время|наст\.? время|н\.\s?в\.?|сейчас|текущее время|present|now)"
_POINT = rf"(?:{_MONTH}\s*\d{{4}}|\d{{1,2}}\.\d{{4}}|\d{{4}})"
PERIOD_RE = re.compile(rf"(?P<a>{_POINT})\s*[—–-]\s*(?P<b>{_POINT}|{_NOW})", re.IGNORECASE)
YEARS_RE = r"(\d+(?:[.,]\d+)?)\s*(?:год|года|лет)(?:\s*(?:и\s*)?(\d+)\s*месяц\w*)?"

ROLE_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        r"backend|бэкенд|бекенд|python-разработчик|go-разработчик|java-разработчик",
        "Backend-разработчик",
    ),
    (r"frontend|фронтенд-разработчик|фронтенд разработчик", "Frontend-разработчик"),
    (r"ios-разработчик|android-разработчик|мобильн\w* разработчик|mobile", "Mobile-разработчик"),
    (r"data scientist|дата-сайентист", "Data Scientist"),
    (r"ml-инженер|ml engineer|machine learning engineer", "ML-инженер"),
    (r"аналитик данных|data analyst", "Аналитик данных"),
    (r"тестировщик|qa-инженер|qa engineer|стаж[её]р qa|qa{_E}", "Тестировщик"),
    (r"devops", "DevOps-инженер"),
    (r"(?<![a-zа-яё])sre(?![a-zа-яё])", "SRE"),
    (r"тимлид|team ?lead|руковож\w* команд|веду команду|руководитель команды", "Тимлид"),
    (r"архитектор", "Архитектор"),
    (r"наставник(?!ств)|ментор", "Наставник"),
)

SOFT_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"внимательн\w* к детал", "Внимательность к деталям"),
    (r"аналитическ\w* мышлени", "Аналитическое мышление"),
    (r"системн\w* мышлени", "Системное мышление"),
    (r"критическ\w* мышлени", "Критическое мышление"),
    (r"ответствен", "Ответственность"),
    (r"коммуникаб|общий язык|коммуникац", "Коммуникабельность"),
    (r"наставничеств", "Наставничество"),
    (r"лидерств|лидерск", "Лидерство"),
    (r"работ\w* в команде|командн\w* игрок", "Работа в команде"),
    (r"обучаем|быстро обучаюсь|быстро учусь", "Обучаемость"),
    (r"внимательн", "Внимательность"),
    (r"усидчив", "Усидчивость"),
    (r"договарива", "Умение договариваться"),
    (r"самостоятельн", "Самостоятельность"),
    (r"стрессоустойчив|в стрессовых", "Стрессоустойчивость"),
    (r"тайм-менеджмент|управлени\w* временем", "Тайм-менеджмент"),
    (r"инициативн", "Инициативность"),
    (r"пунктуальн", "Пунктуальность"),
    (r"креативн", "Креативность"),
    (r"публичн\w* выступлени", "Публичные выступления"),
)
# специфичное поглощает общее: «внимательность к деталям» ⊃ «внимательность»
SOFT_SUBSUMES = {"Внимательность к деталям": "Внимательность"}


def _norm_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    return "+7" + digits[-10:]


def _full_name(lines: list[str]) -> str | None:
    words: list[str] = []
    for line in lines[:8]:
        tokens = line.split()
        ok = (
            1 <= len(tokens) <= 3
            and all(NAME_WORD.match(t) for t in tokens)
            and not any(t in NOT_NAME or t in _CITY_WORDS for t in tokens)
        )
        if ok and len(words) + len(tokens) <= 3:
            words += tokens
            if len(words) == 3:
                break
            continue
        if words:
            break
    return " ".join(words) if len(words) >= 2 else None


def _month_index(point: str, today: date) -> int | None:
    p = point.strip().lower()
    if re.fullmatch(_NOW, p, re.IGNORECASE):
        return today.year * 12 + today.month - 1
    m = re.fullmatch(r"(\d{1,2})\.(\d{4})", p)
    if m:
        return int(m.group(2)) * 12 + int(m.group(1)) - 1
    m = re.fullmatch(rf"({_MONTH})\s*(\d{{4}})", p, re.IGNORECASE)
    if m:
        month = MONTHS.get(m.group(1)[:3].lower(), 1)
        return int(m.group(2)) * 12 + month - 1
    m = re.fullmatch(r"\d{4}", p)
    if m:
        return int(p) * 12
    return None


def periods_months(text: str, today: date) -> int:
    """Сумма периодов работы в месяцах (пересечения не считаем дважды)."""
    intervals: list[tuple[int, int]] = []
    for m in PERIOD_RE.finditer(text):
        a = _month_index(m.group("a"), today)
        b_raw = m.group("b")
        b = _month_index(b_raw, today)
        if a is None or b is None:
            continue
        is_now = bool(re.fullmatch(_NOW, b_raw.strip(), re.IGNORECASE))
        if re.fullmatch(r"\d{4}", b_raw.strip()):
            b += 11  # «2019 — 2020»: год без месяца — по декабрь
        end = b if is_now else b + 1  # закрытый период включает последний месяц
        if end > a:
            intervals.append((a, end))
    intervals.sort()
    total, cur_a, cur_b = 0, None, None
    for a, b in intervals:
        if cur_b is None or a > cur_b:
            if cur_b is not None and cur_a is not None:
                total += cur_b - cur_a
            cur_a, cur_b = a, b
        else:
            cur_b = max(cur_b, b)
    if cur_a is not None and cur_b is not None:
        total += cur_b - cur_a
    return total


def _years(m: re.Match[str]) -> float:
    years = float(m.group(1).replace(",", "."))
    months = int(m.group(2)) if m.group(2) else 0
    return round(years + months / 12, 1)


def experience_years(sections: dict[str, list[str]], text: str, today: date) -> tuple[float, float]:
    """Стаж (лет) и уверенность: явное «Опыт работы — N лет» > сумма периодов > «N лет в …»."""
    for line in sections.get("experience", [])[:2]:
        if "опыт" in line.lower():
            m = re.search(YEARS_RE, line, re.IGNORECASE)
            if m:
                return _years(m), 0.95
    months = periods_months(text, today)
    if months:
        return round(months / 12 * 2) / 2, 0.8
    m = re.search(YEARS_RE + r"\s+(?:в|во|опыта)\s", text, re.IGNORECASE)
    if m:
        return _years(m), 0.6
    return 0.0, 0.3


def find_roles(text: str) -> list[str]:
    found: list[tuple[int, str]] = []
    for pattern, role in ROLE_PATTERNS:
        p = pattern.replace("{_E}", r"(?![a-zа-яё])")
        m = re.search(p, text, re.IGNORECASE)
        if m:
            found.append((m.start(), role))
    return [r for _, r in sorted(found)]


def find_soft_skills(text: str) -> list[str]:
    found: list[tuple[int, str]] = []
    for pattern, skill in SOFT_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            found.append((m.start(), skill))
    names = [s for _, s in sorted(found)]
    drop = {SOFT_SUBSUMES[s] for s in names if s in SOFT_SUBSUMES}
    return [s for s in names if s not in drop]


@dataclass
class ResumeParse:
    fields: dict[str, dict[str, Any]]
    unmatched_skills: list[str]
    parser: str = "rules"
    warnings: list[str] = field(default_factory=list)
    two_column_pages: list[int] = field(default_factory=list)

    def value(self, name: str) -> Any:
        return self.fields.get(name, {}).get("value")


def _field(value: Any, confidence: float) -> dict[str, Any]:
    empty = value is None or value == [] or value == ""
    return {"value": None if empty else value, "confidence": 0.0 if empty else confidence}


def parse_resume_text(text: str, today: date | None = None) -> ResumeParse:
    today = today or date.today()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    sections = split_sections(lines)
    header_lines = (sections.get("header", [])[:12] + sections.get("contacts", [])[:8]) or lines[
        :12
    ]
    header = "\n".join(header_lines)

    email = EMAIL_RE.search(text)
    phone = PHONE_RE.search(text)
    name = _full_name(lines)

    city_line = next((ln for ln in lines if re.match(r"город\s*:", ln, re.IGNORECASE)), None)
    city, _ = detect_city(city_line or header)
    city_conf = 0.95 if city_line and city else 0.85
    if city is None:
        city, _ = detect_city(text)
        city_conf = 0.55

    skills_text = "\n".join(sections.get("skills", []))
    mentions: list[SkillMention] = find_skills(skills_text) if skills_text else []
    stack_conf = 0.9
    if not mentions:
        mentions, stack_conf = find_skills(text), 0.6

    title = "\n".join(lines[:5])
    spec = detect_specialization(text, mentions, title=title)
    grade, _ = detect_grade("\n".join(lines[:6]))

    fmt_lines = list(header_lines)
    for i, ln in enumerate(lines):
        if "формат" in ln.lower():
            fmt_lines += lines[i : i + 2]
    formats = detect_work_formats("\n".join(fmt_lines))

    years, years_conf = experience_years(sections, text, today)

    soft_text = "\n".join(sections.get("soft", []))
    soft = find_soft_skills(soft_text) if soft_text else []
    soft_conf = 0.8
    if not soft:
        soft, soft_conf = find_soft_skills(text), 0.5

    links = [m.group(0) for m in GITHUB_RE.finditer(text)] + [
        m.group(0) for m in LINK_RE.finditer(text)
    ]
    # Без схемы и www — для склейки дублей; в ответ — всегда с https:// (так ссылку примет форма).
    bare = dict.fromkeys(
        re.sub(r"^https?://(www\.)?", "", ln, flags=re.IGNORECASE).rstrip(".") for ln in links
    )
    links = [f"https://{ln}" for ln in bare]
    about = " ".join(sections.get("about", []))[:3000] or None

    fields = {
        "full_name": _field(name, 0.9 if name and len(name.split()) == 3 else 0.8),
        "email": _field(email.group(0) if email else None, 0.99),
        "phone": _field(_norm_phone(phone.group(0)) if phone else None, 0.95),
        "city": _field(city, city_conf),
        "specialization": _field(spec.code, spec.confidence),
        "grade": _field(grade, 0.85),
        "stack": _field([m.code for m in mentions if m.in_catalog], stack_conf),
        "experience_years": {"value": years, "confidence": years_conf},
        "roles_in_team": _field(find_roles(text), 0.6),
        "soft_skills": _field(soft, soft_conf),
        "work_formats": _field(formats, 0.8),
        "links": _field(links, 0.95),
        "about": _field(about, 0.7),
    }
    unmatched = [m.label for m in mentions if not m.in_catalog]
    return ResumeParse(fields, unmatched)


# ---------------------------------------------------------------- LLM
#
# Правила — основной разбор (на образцах 100%). Модель зовётся, только если правила оставили
# поля пустыми, и только дозаполняет их с низкой уверенностью: найденное правилами не меняется.
# В запрос уходит начало текста резюме и схема только с недостающими полями — так короче ответ
# (модель на 2 ядрах печатает ~10 токенов в секунду).


class LlmResume(BaseModel):
    full_name: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    specialization: Literal["backend", "frontend", "mobile", "data_ml", "qa", "devops"] | None = (
        None
    )
    grade: Literal["intern", "junior", "middle", "senior"] | None = None
    stack: list[str] = Field(default_factory=list, max_length=60)
    experience_years: float | None = Field(default=None, ge=0, le=60)
    roles: list[str] = Field(default_factory=list, max_length=10)
    soft_skills: list[str] = Field(default_factory=list, max_length=15)


RESUME_SYSTEM_PROMPT = (
    "Ты разбираешь текст резюме IT-специалиста. Верни только JSON с запрошенными полями: "
    "full_name (ФИО как в резюме), city, specialization (backend|frontend|mobile|data_ml|qa|"
    "devops|null), grade (intern|junior|middle|senior|null — только если указан), stack "
    "(названия технологий), experience_years (суммарный стаж работы в годах числом), roles "
    "(роли в команде), soft_skills. Не выдумывай: чего нет — null или пустой список."
)
# поле ответа модели → поле разбора
LLM_TO_FIELD = {
    "full_name": "full_name",
    "city": "city",
    "specialization": "specialization",
    "grade": "grade",
    "stack": "stack",
    "experience_years": "experience_years",
    "roles": "roles_in_team",
    "soft_skills": "soft_skills",
}
LLM_CONFIDENCE = 0.5  # дозаполнено нейросетью — кандидат проверит в форме
RESUME_LLM_MAX_CHARS = 3000
RESUME_LLM_MAX_TOKENS = 300


def missing_fields(rules: ResumeParse) -> list[str]:
    """Поля ответа модели, которые правила не нашли (стаж — если не нашли ни одного признака)."""
    missing = []
    for name, key in LLM_TO_FIELD.items():
        f = rules.fields.get(key, {})
        empty = f.get("value") in (None, "", [])
        if key == "experience_years":
            empty = f.get("confidence", 0) <= 0.3
        if empty:
            missing.append(name)
    return missing


def request_schema(fields: list[str]) -> type[BaseModel]:
    """Схема ответа только с недостающими полями (по ней llama.cpp строит грамматику)."""
    defs: dict[str, Any] = {
        name: (LlmResume.model_fields[name].annotation, LlmResume.model_fields[name])
        for name in fields
    }
    return create_model("LlmResumePart", **defs)


def merge_llm(rules: ResumeParse, answer: BaseModel) -> ResumeParse:
    """Ответ модели дозаполняет только пустые поля разбора правилами."""
    f = dict(rules.fields)
    unmatched = list(rules.unmatched_skills)
    filled = False
    missing = set(missing_fields(rules))
    for name, value in answer.model_dump().items():
        if name not in missing or value in (None, "", []):
            continue
        key = LLM_TO_FIELD[name]
        if name == "stack":
            stack: list[str] = []
            for raw in value:
                code = normalize_skill(raw)
                if code and is_catalog(code):
                    if code not in stack:
                        stack.append(code)
                elif code and label(code) not in unmatched:
                    unmatched.append(label(code))
            if not stack:
                continue
            value = stack
        if name == "experience_years":
            f[key] = {"value": value, "confidence": LLM_CONFIDENCE}
        else:
            f[key] = _field(value, LLM_CONFIDENCE)
        filled = True
    if not filled:
        return rules
    return ResumeParse(f, unmatched, "llm", rules.warnings, rules.two_column_pages)


def _llm_request(rules: ResumeParse, text: str | None) -> tuple[type[BaseModel], str] | None:
    if not text or not llm.llm_enabled():
        return None
    fields = missing_fields(rules)
    if not fields:
        return None
    return request_schema(fields), text[:RESUME_LLM_MAX_CHARS]


def fill_with_llm(rules: ResumeParse, text: str | None) -> ResumeParse:
    """Синхронно (скрипт валидации)."""
    req = _llm_request(rules, text)
    if req is None:
        return rules
    schema, user = req
    answer = llm.complete_json(
        RESUME_SYSTEM_PROMPT,
        user,
        schema,
        timeout=get_nlp_settings().llm_resume_timeout_sec,
        max_tokens=RESUME_LLM_MAX_TOKENS,
    )
    return merge_llm(rules, answer) if answer else rules


async def fill_with_llm_async(rules: ResumeParse, text: str | None) -> ResumeParse:
    """Для обработчика загрузки: не блокирует цикл событий; при ошибке — разбор правилами."""
    req = _llm_request(rules, text)
    if req is None:
        return rules
    schema, user = req
    answer = await llm.acomplete_json(
        RESUME_SYSTEM_PROMPT,
        user,
        schema,
        timeout=get_nlp_settings().llm_resume_timeout_sec,
        max_tokens=RESUME_LLM_MAX_TOKENS,
    )
    return merge_llm(rules, answer) if answer else rules


# ---------------------------------------------------------------- точка входа


def parse_resume_rules(data: bytes, today: date | None = None) -> tuple[ResumeParse, str | None]:
    """PDF → разбор правилами и текст для LLM (None — текста нет, звать модель незачем)."""
    settings = get_nlp_settings()
    try:
        pdf = extract_pdf_text(data, settings.resume_max_pages)
    except Exception as exc:  # pdfplumber/pdfminer бросают разные исключения на битых файлах
        log.info("PDF не читается: %s", exc)
        empty = parse_resume_text("", today)
        empty.warnings.append("Не удалось прочитать PDF — заполните форму вручную")
        return empty, None
    result = parse_resume_text(pdf.text, today)
    result.two_column_pages = pdf.two_column_pages
    if len(re.sub(r"\s", "", pdf.text)) < 50:
        result.warnings.append(
            "В PDF почти нет текста (скан или картинка) — заполните форму вручную"
        )
        return result, None
    if pdf.pages > settings.resume_max_pages:
        result.warnings.append(f"Разобраны первые {settings.resume_max_pages} страниц")
    return result, pdf.text


def parse_resume_pdf(data: bytes, today: date | None = None) -> ResumeParse:
    """PDF (байты) → разбор. Нечитаемый или пустой PDF → пустые поля и предупреждение."""
    result, text = parse_resume_rules(data, today)
    return fill_with_llm(result, text)


class ResumeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upload(self, candidate_id: int, file: UploadFile) -> dict[str, Any]:
        settings = get_nlp_settings()
        if file.content_type not in PDF_TYPES:
            raise AppError(
                415, "unsupported_file", "Нужен PDF", {"content_type": file.content_type}
            )
        data = await file.read(settings.resume_max_bytes + 1)
        if len(data) > settings.resume_max_bytes:
            raise AppError(
                413,
                "file_too_large",
                f"Файл больше {settings.resume_max_bytes // (1024 * 1024)} МБ",
                {"max_bytes": settings.resume_max_bytes},
            )
        if not data.startswith(b"%PDF"):
            raise AppError(
                415, "unsupported_file", "Нужен PDF", {"content_type": file.content_type}
            )
        rules, text = await run_in_threadpool(parse_resume_rules, data)
        parsed = await fill_with_llm_async(rules, text)
        filename = (file.filename or "resume.pdf")[:255]
        storage_path = ""
        if settings.resume_storage_dir:
            folder = Path(settings.resume_storage_dir)
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / f"{candidate_id}-{uuid.uuid4().hex}.pdf"
            target.write_bytes(data)
            storage_path = str(target)
        resume = Resume(
            candidate_id=candidate_id,
            filename=filename,
            storage_path=storage_path,
            parser=parsed.parser,
            parsed={
                "fields": parsed.fields,
                "unmatched_skills": parsed.unmatched_skills,
                "warnings": parsed.warnings,
                "two_column_pages": parsed.two_column_pages,
            },
        )
        self.session.add(resume)
        await self.session.commit()
        return {
            "resume_id": resume.id,
            "filename": filename,
            "parser": parsed.parser,
            "fields": parsed.fields,
            "unmatched_skills": parsed.unmatched_skills,
            "warnings": parsed.warnings,
        }
