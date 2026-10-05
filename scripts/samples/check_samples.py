"""Проверка образцов в data/samples.

- Резюме: текст извлекается pdfplumber, кириллица читается, все эталонные значения
  из <имя>.expected.json действительно есть в PDF. Это проверка самих образцов, а не парсера:
  парсер (T3.2) должен ещё и разложить текст по полям.
- Вакансии: коды специализации/грейда/формата из справочников, «от» ≤ «до»,
  весь стек из .json упомянут в тексте .md.
- Формулировки потребностей: коды из справочников, «от» ≤ «до».

Запуск из корня репозитория:
    python scripts/samples/check_samples.py
Код выхода 1, если что-то не так.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pdfplumber

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"
SPECS = {"backend", "frontend", "mobile", "data_ml", "qa", "devops"}
GRADES = {"intern", "junior", "middle", "senior"}
FORMATS = {"office", "hybrid", "remote"}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def pdf_text(path: Path) -> tuple[str, int, int]:
    """Текст PDF построчно + отдельно по колонкам. Возвращает (текст, страниц, символов)."""
    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        chars = len(text)
        # Для резюме в две колонки построчное извлечение перемешивает колонки.
        # Добавляем текст левой и правой части страницы отдельно (так же стоит
        # поступать и парсеру: резать страницу по колонкам).
        for page in pdf.pages:
            split = page.width * 0.37
            for box in ((0, 0, split, page.height), (split, 0, page.width, page.height)):
                text += "\n" + (page.crop(box).extract_text() or "")
        return text, len(pdf.pages), chars


def check_resumes() -> int:
    failed = 0
    folder = SAMPLES / "resumes"
    for exp_path in sorted(folder.glob("*.expected.json")):
        exp = json.loads(exp_path.read_text(encoding="utf-8"))
        text, pages, chars = pdf_text(folder / exp["file"])
        flat, digits = norm(text), re.sub(r"\D", "", text)
        cyr = len(re.findall(r"[а-яё]", text[:chars], re.I))
        checks = {
            "full_name": exp["full_name"],
            "email": exp["email"],
            "city": exp["city"],
            **{f"stack:{x}": x for x in exp["stack"]},
            **{f"link:{k}": v for k, v in exp["links"].items()},
        }
        missing = [k for k, v in checks.items() if norm(v) not in flat]
        # Телефон в PDF записан по-разному (+7 / 8, скобки, дефисы) — сравниваем 10 цифр.
        if exp["phone"][-10:] not in digits:
            missing.append("phone")
        if cyr < 50:
            missing.append("cyrillic")
        if exp["specialization"] not in SPECS or exp["grade"] not in GRADES | {None}:
            missing.append("codes")
        status = "OK " if not missing else "ERR"
        print(
            f"{status} резюме {exp['file']}: страниц {pages}, символов {chars}, "
            f"кириллица {cyr}, проверено значений {len(checks) + 1}"
            + (f", не найдено: {missing}" if missing else "")
        )
        failed += bool(missing)
    return failed


def check_vacancies() -> int:
    failed = 0
    for path in sorted((SAMPLES / "vacancies").glob("*.json")):
        v = json.loads(path.read_text(encoding="utf-8"))
        md = norm((path.parent / v["file"]).read_text(encoding="utf-8"))
        errors = []
        if v["specialization"] not in SPECS or v["grade"] not in GRADES:
            errors.append("codes")
        if v["work_format"] not in FORMATS:
            errors.append("work_format")
        if not (0 < v["salary_from"] <= v["salary_to"]):
            errors.append("salary")
        errors += [
            f"stack:{x}" for x in v["stack_required"] + v["stack_optional"] if norm(x) not in md
        ]
        print(
            ("OK " if not errors else "ERR")
            + f" вакансия {path.name}: {v['title']}"
            + (f", ошибки: {errors}" if errors else "")
        )
        failed += bool(errors)
    return failed


def check_needs() -> int:
    data = json.loads((SAMPLES / "needs_phrases.json").read_text(encoding="utf-8"))
    errors = []
    for item in data["items"]:
        e = item["expected"]
        if e["specialization"] not in SPECS or e["grade"] not in GRADES | {None}:
            errors.append(f"{item['id']}:codes")
        if e["work_format"] not in FORMATS | {None}:
            errors.append(f"{item['id']}:work_format")
        if e["salary_from"] and e["salary_to"] and e["salary_from"] > e["salary_to"]:
            errors.append(f"{item['id']}:salary")
    print(
        ("OK " if not errors else "ERR")
        + f" формулировки потребностей: {len(data['items'])} шт."
        + (f", ошибки: {errors}" if errors else "")
    )
    return int(bool(errors))


def main() -> int:
    failed = check_resumes() + check_vacancies() + check_needs()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
