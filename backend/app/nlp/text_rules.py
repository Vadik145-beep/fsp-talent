"""Правила разбора текста: грейд, специализация, формат работы, город, вилка, предметная область.

Общие для потребности работодателя (T6.1), резюме (T3.2) и вакансии (T4.8).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from app.nlp.skills_lexicon import SkillMention, find_skills, specializations_of

GRADES = ("intern", "junior", "middle", "senior")
GRADE_LABELS = {"intern": "Стажёр", "junior": "Junior", "middle": "Middle", "senior": "Senior"}
SPEC_LABELS = {
    "backend": "Backend",
    "frontend": "Frontend",
    "mobile": "Mobile",
    "data_ml": "Data Science / ML",
    "qa": "QA",
    "devops": "DevOps",
}

_B = r"(?<![0-9a-zа-яё])"  # начало слова
_E = r"(?![0-9a-zа-яё])"  # конец слова

GRADE_PATTERNS: dict[str, str] = {
    "senior": (
        rf"{_B}(?:сень[оеё]р\w*|синь[оеё]р\w*|сени[оа]р\w*|senior|sr\.?{_E}|ведущ\w*|"
        rf"лид{_E}|лида{_E}|тимлид\w*|team\s?lead\w*|tech\s?lead\w*|lead{_E}|"
        rf"principal{_E}|staff{_E})"
    ),
    "middle": rf"{_B}(?:мидл\w*|миддл\w*|мидд?\+|middle|mid{_E}|mid-level|средн\w* уровня)",
    "junior": rf"{_B}(?:джун\w*|джуниор\w*|junior|jr\.?{_E}|младш\w*|начинающ\w*)",
    "intern": rf"{_B}(?:стаж[её]р\w*|стажир\w*|intern\w*|trainee|практикант\w*|студент\w*)",
}

# Явные слова роли: вес 3 (против 1 за технологию).
SPEC_PATTERNS: dict[str, str] = {
    "backend": (
        rf"{_B}(?:бэк\w*|бек\w*|backend\w*|back-end|серверн\w*|server-side|"
        rf"питонист\w*|джавист\w*|гошник\w*|пхпшник\w*)"
    ),
    "frontend": (
        rf"{_B}(?:фронт\w*|frontend\w*|front-end|верстальщик\w*|веб-интерфейс\w*|"
        rf"клиентск\w* част\w*)"
    ),
    "mobile": (
        rf"{_B}(?:мобильн\w*|mobile|ios{_E}|android\w*|андроид\w*|айос\w*|"
        rf"flutter|флаттер\w*|react native)"
    ),
    "data_ml": (
        rf"{_B}(?:ml{_E}|ml-\w*|машинн\w* обучени\w*|data scien\w*|data engineer\w*|"
        rf"дата[\s-]?сайент\w*|специалист\w* по данным|аналитик\w* данных|"
        rf"нейросет\w*|computer vision|nlp{_E}|рекомендательн\w*)"
    ),
    "qa": (
        rf"{_B}(?:qa{_E}|qa-\w*|тестировщик\w*|автотест\w*|тестирован\w*|"
        rf"автоматизатор\w*|aqa{_E}|sdet{_E})"
    ),
    "devops": (
        rf"{_B}(?:devops\w*|dev-ops|девопс\w*|sre{_E}|инфраструктур\w*|"
        rf"системн\w* администратор\w*|platform engineer\w*)"
    ),
}

FORMAT_PATTERNS: dict[str, str] = {
    "remote": (
        rf"{_B}(?:удал[её]нн?\w*|удал[её]нк\w*|remote\w*|фулл?[\s-]?рем[оу]ут\w*|"
        rf"full[\s-]?remote|из любого города|дистанционн\w*)"
    ),
    "hybrid": rf"{_B}(?:гибрид\w*|hybrid|смешанн\w* формат\w*)",
    "office": rf"{_B}(?:офис\w*|office|on-?site|в офисе)",
}

# Город → формы (в нижнем регистре, полные слова).
CITIES: dict[str, tuple[str, ...]] = {
    "Москва": ("москва", "москве", "москву", "москвы", "мск", "moscow"),
    "Санкт-Петербург": (
        "санкт-петербург",
        "санкт-петербурге",
        "петербург",
        "петербурге",
        "спб",
        "питер",
        "питере",
        "saint petersburg",
    ),
    "Казань": ("казань", "казани", "kazan"),
    "Новосибирск": ("новосибирск", "новосибирске", "нск"),
    "Екатеринбург": ("екатеринбург", "екатеринбурге", "екб"),
    "Нижний Новгород": ("нижний новгород", "нижнем новгороде", "нн"),
    "Краснодар": ("краснодар", "краснодаре"),
    "Самара": ("самара", "самаре"),
    "Ростов-на-Дону": ("ростов-на-дону", "ростове-на-дону", "ростов", "ростове"),
    "Пермь": ("пермь", "перми"),
    "Уфа": ("уфа", "уфе"),
    "Воронеж": ("воронеж", "воронеже"),
    "Томск": ("томск", "томске"),
    "Челябинск": ("челябинск", "челябинске"),
    "Омск": ("омск", "омске"),
    "Иннополис": ("иннополис", "иннополисе"),
    "Калининград": ("калининград", "калининграде"),
    "Владивосток": ("владивосток", "владивостоке"),
    "Красноярск": ("красноярск", "красноярске"),
    "Тюмень": ("тюмень", "тюмени"),
    "Саратов": ("саратов", "саратове"),
    "Ярославль": ("ярославль", "ярославле"),
    "Ижевск": ("ижевск", "ижевске"),
    "Минск": ("минск", "минске"),
}

DOMAINS: tuple[tuple[str, str], ...] = (
    (rf"{_B}(?:финтех\w*|fintech)", "финтех"),
    (rf"{_B}банк\w*", "банк"),
    (rf"{_B}антифрод\w*|{_B}anti-?fraud", "антифрод"),
    (rf"{_B}(?:e-?commerce|ecom\w*|интернет-магазин\w*|маркетплейс\w*)", "e-commerce"),
    (rf"{_B}(?:highload|хайлоад\w*|высоконагруж\w*)", "highload"),
    (rf"{_B}доставк\w* еды", "доставка еды"),
    (rf"{_B}облачн\w* (?:сервис|платформ|провайдер)\w*", "облачный сервис"),
    (rf"{_B}(?:платёж\w*|платеж\w*|процессинг\w*)", "платежи"),
    (rf"{_B}рекомендательн\w*", "рекомендательные системы"),
    (rf"{_B}(?:медицин\w*|телемедицин\w*|healthtech)", "медицина"),
    (rf"{_B}(?:edtech|образовательн\w*)", "образование"),
    (rf"{_B}(?:геймдев\w*|gamedev|игров\w*)", "геймдев"),
    (rf"{_B}логистик\w*", "логистика"),
    (rf"{_B}(?:ритейл\w*|retail)", "ритейл"),
    (rf"{_B}телеком\w*", "телеком"),
    (rf"{_B}страхов\w*", "страхование"),
    (rf"{_B}(?:госсектор\w*|госуслуг\w*|государствен\w*)", "госсектор"),
    (rf"{_B}(?:оплат\w* проезда|транспорт\w*)", "транспорт"),
)


def _first(pattern: str, text: str) -> re.Match[str] | None:
    return re.search(pattern, text, re.IGNORECASE)


def detect_grade(text: str) -> tuple[str | None, str | None]:
    """Первый по тексту грейд → (код, слово из текста). «junior/middle» → junior."""
    best: tuple[int, str, str] | None = None
    for grade, pattern in GRADE_PATTERNS.items():
        m = _first(pattern, text)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), grade, m.group(0))
    return (best[1], best[2]) if best else (None, None)


def grade_from_experience(years: float | None) -> str | None:
    if years is None:
        return None
    if years >= 5:
        return "senior"
    if years >= 2.5:
        return "middle"
    if years >= 0.5:
        return "junior"
    return "intern"


@dataclass(frozen=True)
class SpecGuess:
    code: str | None
    confidence: float
    evidence: list[str]


def detect_specialization(
    text: str, skills: Iterable[SkillMention], title: str | None = None
) -> SpecGuess:
    """Явные слова роли (вес 3, в заголовке ×2) + технологии (основная специализация — 1,
    остальные — 0,5)."""
    scores: dict[str, float] = {}
    evidence: dict[str, list[str]] = {}
    for spec, pattern in SPEC_PATTERNS.items():
        for source, weight in ((title or "", 6.0), (text, 3.0)):
            hits = re.findall(pattern, source, re.IGNORECASE)
            if hits:
                scores[spec] = scores.get(spec, 0.0) + weight
                evidence.setdefault(spec, []).append(hits[0])
                break
    for s in skills:
        specs = specializations_of(s.code)
        for i, spec in enumerate(specs):
            scores[spec] = scores.get(spec, 0.0) + (1.0 if i == 0 else 0.5)
            if i == 0:
                evidence.setdefault(spec, []).append(s.label)
    # технология в заголовке («Senior Go-разработчик») весит больше
    for s in find_skills(title or ""):
        specs = specializations_of(s.code)
        if specs:
            scores[specs[0]] = scores.get(specs[0], 0.0) + 2.0
            evidence.setdefault(specs[0], []).insert(0, s.label)
    if not scores:
        return SpecGuess(None, 0.0, [])
    order = list(SPEC_LABELS)
    best = max(scores, key=lambda k: (scores[k], -order.index(k)))
    total = sum(scores.values())
    return SpecGuess(best, round(min(0.97, 0.4 + 0.6 * scores[best] / total), 2), evidence[best])


def detect_work_formats(text: str) -> list[str]:
    """Все упомянутые форматы в порядке приоритета: удалёнка → гибрид → офис."""
    return [f for f, p in FORMAT_PATTERNS.items() if _first(p, text)]


def primary_work_format(text: str) -> str | None:
    formats = detect_work_formats(text)
    return formats[0] if formats else None


def detect_city(text: str) -> tuple[str | None, int]:
    """Первый по тексту город → (название, позиция)."""
    best: tuple[int, str] | None = None
    low = text.lower().replace("ё", "е")
    for city, forms in CITIES.items():
        for form in forms:
            m = re.search(rf"{_B}{re.escape(form)}{_E}", low)
            if m and (best is None or m.start() < best[0]):
                best = (m.start(), city)
    return (best[1], best[0]) if best else (None, -1)


def detect_domains(text: str) -> list[str]:
    found: list[tuple[int, str]] = []
    for pattern, lbl in DOMAINS:
        m = _first(pattern, text)
        if m:
            found.append((m.start(), lbl))
    return [lbl for _, lbl in sorted(found)]


# ---------------------------------------------------------------- зарплата

_NUM = r"\d{1,3}(?:[   ]\d{3})+|\d+(?:[.,]\d+)?"
_K_UNIT = r"к{_E}|k{_E}|тыс\w*\.?|т\.?\s?р\.?|тр{_E}|тысяч\w*".replace("{_E}", _E)
_R_UNIT = r"руб\w*\.?|р\.|₽|rub"
_NOT_MONEY = (
    r"\s*(?:лет|года?|год{E}|мес|чел|%|раз|дн|недел|час|млн|млрд|минут|сервис|кластер|"
    r"команд|инженер|разработчик|продукт|транзакц|эндпоинт|хост|сервер|окружени)"
).replace("{E}", _E)


def _to_rub(raw: str, unit: str | None, assume_thousands: bool) -> int | None:
    value = float(re.sub(r"[   ]", "", raw).replace(",", "."))
    if (unit and re.match(_K_UNIT, unit, re.IGNORECASE)) or (value < 1000 and assume_thousands):
        value *= 1000
    if not 10_000 <= value <= 10_000_000:
        return None
    return round(value)


@dataclass(frozen=True)
class Salary:
    salary_from: int | None
    salary_to: int | None
    text: str


def detect_salary(text: str) -> Salary | None:
    """Вилка: «300–400к», «от 250 тыс.», «до 120к», «200-260 тысяч», «250 000 – 300 000 руб.»,
    «от 350 000 до 450 000 ₽», одна сумма «60 000» (от = до)."""
    t = re.sub(r"[\u2009\u00a0\u202f]", " ", text)

    def unit(n: int) -> str:
        return rf"(?:\s?(?P<u{n}>{_K_UNIT}|{_R_UNIT}))?"

    def num(n: int) -> str:
        return rf"(?<![\d.,])(?P<n{n}>{_NUM})"

    # от A до B
    m = re.search(
        rf"{_B}от\s*{num(1)}{unit(1)}\s*(?:до|-|–|—)\s*"
        rf"{num(2)}{unit(2)}",
        t,
        re.IGNORECASE,
    )
    if not m:
        # A – B
        m = re.search(
            rf"{num(1)}{unit(1)}\s*(?:-|–|—|до)\s*"
            rf"{num(2)}{unit(2)}(?!\s*\d)(?!{_NOT_MONEY})",
            t,
            re.IGNORECASE,
        )
    if m:
        u1, u2 = m.group("u1"), m.group("u2")
        common = u2 or u1
        a = _to_rub(m.group("n1"), u1 or common, True)
        b = _to_rub(m.group("n2"), u2 or common, True)
        if a and b and a <= b:
            return Salary(a, b, m.group(0).strip())
    one = rf"{num(1)}{unit(1)}(?!{_NOT_MONEY})"
    m = re.search(rf"{_B}от\s*{one}", t, re.IGNORECASE)
    if m:
        a = _to_rub(m.group("n1"), m.group("u1"), bool(m.group("u1")))
        if a:
            return Salary(a, None, m.group(0).strip())
    m = re.search(rf"{_B}до\s*{one}", t, re.IGNORECASE)
    if m:
        b = _to_rub(m.group("n1"), m.group("u1"), bool(m.group("u1")))
        if b:
            return Salary(None, b, m.group(0).strip())
    for m in re.finditer(one, t, re.IGNORECASE):
        has_unit = bool(m.group("u1"))
        raw = re.sub(r"\D", "", m.group("n1"))
        if not has_unit and len(raw) < 5:
            continue
        a = _to_rub(m.group("n1"), m.group("u1"), has_unit)
        if a:
            return Salary(a, a, m.group(0).strip())
    return None
