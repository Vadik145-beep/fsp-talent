"""Проверка точности на образцах `data/samples` и отчёты в `docs/validation/*.md`.

Те же функции зовут тесты (с порогами), поэтому цифры в отчётах и в тестах совпадают.
Перегенерировать отчёты: `python -m app.nlp.validation` (из backend/).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from app.core.config import REPO_ROOT
from app.nlp.need_parser import parse_detailed
from app.nlp.skills_lexicon import normalize_skill
from app.nlp.vacancy_tests import analyze_vacancy, choose_templates

SAMPLES = REPO_ROOT / "data" / "samples"
DOCS = REPO_ROOT / "docs" / "validation"
RESUME_TODAY = date(2026, 10, 1)  # эталон стажа в образцах посчитан «на октябрь 2026»


def _code(name: str) -> str:
    return normalize_skill(name) or name.strip().lower()


def _codes(names: list[str]) -> set[str]:
    return {_code(n) for n in names}


def _norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower().replace("ё", "е"))


# ---------------------------------------------------------------- потребности (T6.1)


@dataclass
class NeedRow:
    id: str
    text: str
    fields: dict[str, bool]
    got: dict[str, Any]

    @property
    def ok(self) -> bool:
        return all(self.fields.values())


def _stack_ok(got: set[str], exp: set[str], acceptable: dict[str, Any], key: str) -> bool:
    if key == "required":
        for group in acceptable.get("stack_required_any_of", []):
            codes = _codes(group)
            if not got & codes:
                return False
            exp = exp - codes
            got = got - codes
        got = got - _codes(acceptable.get("stack_required_extra", []))
    return got == exp


def need_rows() -> list[NeedRow]:
    data = json.loads((SAMPLES / "needs_phrases.json").read_text(encoding="utf-8"))
    rows = []
    for item in data["items"]:
        e = item["expected"]
        acc = e.get("acceptable", {})
        p = parse_detailed(item["text"])
        req = {s.code for s in p.required}
        des = {s.code for s in p.desired}
        domain_ok = (
            p.team_description is None
            if e["domain"] is None
            else any(_norm(part) in _norm(p.team_description) for part in e["domain"].split(","))
        )
        fields = {
            "specialization": p.specialization == e["specialization"],
            "grade": p.grade == e["grade"] or p.grade in acc.get("grade", []),
            "stack_required": _stack_ok(req, _codes(e["stack_required"]), acc, "required"),
            "stack_optional": _stack_ok(des, _codes(e["stack_optional"]), acc, "optional"),
            "salary": (p.salary_from, p.salary_to) == (e["salary_from"], e["salary_to"]),
            "work_format": p.work_format == e["work_format"]
            or p.work_format in acc.get("work_format", []),
            "city": p.city == e["city"],
            "domain": domain_ok,
        }
        got = {
            "specialization": p.specialization,
            "grade": p.grade,
            "required": sorted(req),
            "desired": sorted(des),
            "salary": f"{p.salary_from}–{p.salary_to}",
            "work_format": p.work_format,
            "city": p.city,
            "domain": p.team_description,
        }
        rows.append(NeedRow(item["id"], item["text"], fields, got))
    return rows


def need_report_md(rows: list[NeedRow]) -> str:
    ok = sum(r.ok for r in rows)
    field_names = list(rows[0].fields)
    per_field = {f: sum(r.fields[f] for r in rows) for f in field_names}
    lines = [
        "# Разбор свободного текста потребности (T6.1)",
        "",
        "Образцы: `data/samples/needs_phrases.json` (12 формулировок с эталоном). Режим — правила "
        "(без ключа LLM). Отчёт генерирует `python -m app.nlp.validation`; те же цифры проверяет "
        "тест `backend/tests/test_nlp_need_parser.py` (порог — не меньше 10 из 12).",
        "",
        f"**Итог: верно разобрано {ok} из {len(rows)}** (формулировка верна, если верны все поля).",
        "",
        "Как сравниваем: специализация, грейд, формат, город, вилка — точно (с учётом "
        "`acceptable`); стек — множества кодов после справочника синонимов отдельно для "
        "обязательного и желательного; технологии вне справочника платформы (Nuxt) тоже должны "
        "быть узнаны и попасть в нужный список (наружу они уходят в `unrecognized`); предметная "
        "область — мягко: хотя бы "
        "одна часть эталона есть в `team_description`.",
        "",
        "| Поле | Верно |",
        "|---|---|",
        *[f"| {f} | {n} / {len(rows)} |" for f, n in per_field.items()],
        "",
        "| # | Текст | Итог | Распознано | Ошибки |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        g = r.got
        got = (
            f"{g['specialization']}, {g['grade']}, req={g['required']}, des={g['desired']}, "
            f"{g['salary']}, {g['work_format']}, {g['city']}, «{g['domain']}»"
        )
        bad = ", ".join(f for f, v in r.fields.items() if not v) or "—"
        mark = "✅" if r.ok else "❌"
        lines.append(f"| {r.id} | {r.text} | {mark} | {got} | {bad} |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- резюме (T3.2)


@dataclass
class ResumeRow:
    file: str
    exact: dict[str, bool]
    stack_precision: float
    stack_recall: float
    roles_hit: tuple[int, int, int]  # верно, найдено, в эталоне
    soft_hit: tuple[int, int, int]
    got: dict[str, Any] = field(default_factory=dict)
    two_column: bool = False


def _soft_set(values: list[str]) -> set[str]:
    return {_norm(v).split()[0][:6] if v else "" for v in values}


def resume_rows() -> list[ResumeRow]:
    from app.candidates.resume import parse_resume_pdf

    rows = []
    for exp_path in sorted((SAMPLES / "resumes").glob("*.expected.json")):
        e = json.loads(exp_path.read_text(encoding="utf-8"))
        r = parse_resume_pdf((exp_path.parent / e["file"]).read_bytes(), RESUME_TODAY)
        v = r.value
        formats = v("work_formats") or []
        links = v("links") or []
        exact = {
            "full_name": _norm(v("full_name")) == _norm(e["full_name"]),
            "email": _norm(v("email")) == _norm(e["email"]),
            "phone": v("phone") == e["phone"],
            "city": _norm(v("city")) == _norm(e["city"]),
            "specialization": v("specialization") == e["specialization"],
            "grade": v("grade") == e["grade"],
            "experience_years": abs(float(v("experience_years") or 0) - e["experience_years"])
            <= 0.5,
            "work_format": (formats[0] if formats else None) == e["work_format"],
            "links": all(any(url in got for got in links) for url in e["links"].values())
            and (bool(links) == bool(e["links"])),
        }
        got_stack = _codes([*(v("stack") or []), *r.unmatched_skills])
        exp_stack = _codes(e["stack"])
        tp = len(got_stack & exp_stack)
        roles_got, roles_exp = _soft_set(v("roles_in_team") or []), _soft_set(e["roles"])
        soft_got, soft_exp = _soft_set(v("soft_skills") or []), _soft_set(e["soft_skills"])
        rows.append(
            ResumeRow(
                e["file"],
                exact,
                tp / len(got_stack) if got_stack else 0.0,
                tp / len(exp_stack) if exp_stack else 1.0,
                (len(roles_got & roles_exp), len(roles_got), len(roles_exp)),
                (len(soft_got & soft_exp), len(soft_got), len(soft_exp)),
                {
                    "stack_extra": sorted(got_stack - exp_stack),
                    "stack_missed": sorted(exp_stack - got_stack),
                    "experience_years": v("experience_years"),
                    "roles": v("roles_in_team"),
                    "soft": v("soft_skills"),
                },
                bool(r.two_column_pages),
            )
        )
    return rows


def resume_summary(rows: list[ResumeRow]) -> dict[str, float]:
    n = len(rows)
    summary = {f: sum(r.exact[f] for r in rows) / n for f in rows[0].exact}
    summary["stack_precision"] = sum(r.stack_precision for r in rows) / n
    summary["stack_recall"] = sum(r.stack_recall for r in rows) / n
    for name, attr in (("roles", "roles_hit"), ("soft_skills", "soft_hit")):
        tp = sum(getattr(r, attr)[0] for r in rows)
        got = sum(getattr(r, attr)[1] for r in rows)
        exp = sum(getattr(r, attr)[2] for r in rows)
        summary[f"{name}_precision"] = tp / got if got else 0.0
        summary[f"{name}_recall"] = tp / exp if exp else 1.0
    return summary


def resume_report_md(rows: list[ResumeRow]) -> str:
    s = resume_summary(rows)
    exact_fields = list(rows[0].exact)
    lines = [
        "# Разбор PDF-резюме (T3.2)",
        "",
        "Образцы: `data/samples/resumes/` (5 PDF разной вёрстки, эталон в `*.expected.json`). "
        "Режим — правила (pdfplumber + справочник синонимов, без LLM). Страницы в две колонки "
        "определяются по вертикальному просвету и режутся по колонкам. Стаж считается на "
        "01.10.2026. Отчёт генерирует `python -m app.nlp.validation`; пороги проверяет "
        "`backend/tests/test_resume_parsing.py`.",
        "",
        "## Точность по полям (5 резюме)",
        "",
        "| Поле | Метрика | Значение |",
        "|---|---|---|",
        *[f"| {f} | доля верных | {s[f]:.0%} |" for f in exact_fields],
        f"| stack | precision / recall (среднее) | {s['stack_precision']:.0%} / "
        f"{s['stack_recall']:.0%} |",
        f"| roles | precision / recall | {s['roles_precision']:.0%} / {s['roles_recall']:.0%} |",
        f"| soft_skills | precision / recall | {s['soft_skills_precision']:.0%} / "
        f"{s['soft_skills_recall']:.0%} |",
        "",
        "Сравнение: ФИО, почта, город — без учёта регистра; телефон — `+7XXXXXXXXXX`; стаж — ±0,5 "
        "года; формат — первый из найденных (приоритет удалёнка → гибрид → офис); стек — "
        "множества кодов после справочника синонимов (технологии вне справочника платформы "
        "считаются по `unmatched_skills`); роли и софт-скиллы — мягко, по основе первого слова.",
        "",
        "## По файлам",
        "",
        "| Файл | Две колонки | Точные поля | Стек P / R | Лишнее в стеке | Пропущено | Роли | "
        "Софт-скиллы |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        exact_ok = sum(r.exact.values())
        bad = [f for f, v in r.exact.items() if not v]
        exact_txt = f"{exact_ok} / {len(r.exact)}" + (f" (ошибки: {', '.join(bad)})" if bad else "")
        lines.append(
            f"| {r.file} | {'да' if r.two_column else 'нет'} | {exact_txt} | "
            f"{r.stack_precision:.0%} / {r.stack_recall:.0%} | "
            f"{', '.join(r.got['stack_extra']) or '—'} | "
            f"{', '.join(r.got['stack_missed']) or '—'} | "
            f"{r.roles_hit[0]}/{r.roles_hit[2]} (найдено {r.roles_hit[1]}) | "
            f"{r.soft_hit[0]}/{r.soft_hit[2]} (найдено {r.soft_hit[1]}) |"
        )
    lines += [
        "",
        "Известные расхождения: в резюме №5 найдены «Наставник» (роль) и «Стрессоустойчивость» "
        "(«спокойно работаю в стрессовых ситуациях») — их нет в эталоне, но в тексте они есть; "
        "Zabbix из №5 (упомянут как прошлый инструмент) в стек не попадает, потому что стек "
        "берётся из раздела навыков, если он есть.",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- вакансии (T4.8)


@dataclass
class VacancyRow:
    file: str
    spec_ok: bool
    grade_ok: bool
    topics: list[str]
    items: list[str]
    drafts: list[str]
    expected_topics: list[str]
    covered_expected: list[bool]
    explanation: list[str]


def _stems(text: str) -> set[str]:
    return {w[:5] for w in re.findall(r"[a-zа-яё0-9/+]{3,}", _norm(text))}


def vacancy_rows() -> list[VacancyRow]:
    rows = []
    for md in sorted((SAMPLES / "vacancies").glob("*.md")):
        e = json.loads(md.with_suffix(".json").read_text(encoding="utf-8"))
        text = md.read_text(encoding="utf-8")
        a = analyze_vacancy(text)
        picks = choose_templates(a)
        picked = {p.hit.topic.id for p in picks}
        drafts = [h for h in a.topics if h.topic.id not in picked and not h.covered]
        pool = [_stems(h.topic.label + " " + " ".join(h.matched)) for h in a.topics]
        covered = [any(_stems(t) & p for p in pool) for t in e["expected_topics"]]
        rows.append(
            VacancyRow(
                md.name,
                a.specialization == e["specialization"],
                a.grade == e["grade"],
                [f"{h.topic.label} ({h.confidence:.2f})" for h in a.topics],
                [f"{p.template.id} [{p.template.target_grade}]" for p in picks],
                [h.topic.label for h in drafts],
                e["expected_topics"],
                covered,
                [a.spec_reason, a.grade_reason, *[p.reason for p in picks]],
            )
        )
    return rows


def vacancy_report_md(rows: list[VacancyRow]) -> str:
    total_exp = sum(len(r.expected_topics) for r in rows)
    total_cov = sum(sum(r.covered_expected) for r in rows)
    lines = [
        "# Тест из текста вакансии (T4.8)",
        "",
        "Образцы: `data/samples/vacancies/` (5 вакансий, разметка в `*.json`). Режим — правила "
        "и словарь тем `app/nlp/vacancy_topics.py`, без LLM (черновики — по заготовкам словаря). "
        "Банк — `bank_registry()` (192 шаблона). Отчёт генерирует `python -m app.nlp.validation`; "
        "пороги проверяет `backend/tests/test_vacancy_tests.py`.",
        "",
        f"**Специализация верна: {sum(r.spec_ok for r in rows)} из {len(rows)}; грейд верен: "
        f"{sum(r.grade_ok for r in rows)} из {len(rows)}; ожидаемые темы найдены: {total_cov} из "
        f"{total_exp}.** Тема из `expected_topics` считается найденной, если её слова совпали с "
        "подписью или ключевыми словами хотя бы одной найденной темы (это ориентир, не точный "
        "эталон).",
        "",
        "| Вакансия | Спец. / грейд | Найденные темы (уверенность) | Тест: шаблоны банка [грейд] | "
        "Черновики (нет в банке) | Ожидаемые темы |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        exp = "; ".join(
            ("✅ " if c else "❌ ") + t
            for t, c in zip(r.expected_topics, r.covered_expected, strict=True)
        )
        lines.append(
            f"| {r.file} | {'✅' if r.spec_ok else '❌'} / {'✅' if r.grade_ok else '❌'} | "
            f"{'; '.join(r.topics)} | {'; '.join(r.items)} | {'; '.join(r.drafts) or '—'} | {exp} |"
        )
    lines += ["", "## Объяснение выбора (как его видит админ)", ""]
    for r in rows:
        lines.append(f"### {r.file}")
        lines += [f"- {x}" for x in r.explanation]
        lines.append("")
    return "\n".join(lines)


def write_reports(folder: Path = DOCS) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    for name, body in (
        ("need_parsing.md", need_report_md(need_rows())),
        ("resume_parsing.md", resume_report_md(resume_rows())),
        ("vacancy_tests.md", vacancy_report_md(vacancy_rows())),
    ):
        path = folder / name
        path.write_bytes(body.encode("utf-8"))
        out.append(path)
    return out


if __name__ == "__main__":
    for p in write_reports():
        print(p)
