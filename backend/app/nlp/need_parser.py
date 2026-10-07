"""Разбор свободного текста потребности работодателя в поля формы (T6.1).

Единая точка: эндпоинт `/api/matching/needs/parse` (модуль matching) вызывает только `parse_need`.
Правила работают всегда; если задан ключ LLM — она уточняет поля, ответ проверяется pydantic,
при любой ошибке остаётся разбор правилами.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.nlp import llm
from app.nlp.skills_lexicon import SkillMention, find_skills, is_catalog, label, normalize_skill
from app.nlp.text_rules import (
    GRADE_LABELS,
    SPEC_LABELS,
    detect_city,
    detect_domains,
    detect_grade,
    detect_salary,
    detect_specialization,
    primary_work_format,
)

DESIRED_MARKERS = (
    r"(?<![а-яёa-z])(?:желательн\w*|плюсом|будет плюсом|плюс(?![а-яё])|nice to have|"
    r"приветству\w*|как преимуществ\w*|преимуществом|опционально|optional|"
    r"дополнительн\w*|хорошо бы|было бы здорово)"
)
REQUIRED_MARKERS = (
    r"(?<![а-яёa-z])(?:обязательн\w*|необходим\w*|must|требовани\w*|требуется|ждём|ждем|"
    r"нужн\w*|ищем|мы ждём|мы ждем)"
)
_CLAUSE_END = re.compile(r"[.;!?\n]")


@dataclass
class NeedParse:
    """Полный разбор (для отчёта о точности); наружу уходит `to_result()`."""

    specialization: str | None = None
    grade: str | None = None
    required: list[SkillMention] = field(default_factory=list)
    desired: list[SkillMention] = field(default_factory=list)
    work_format: str | None = None
    city: str | None = None
    salary_from: int | None = None
    salary_to: int | None = None
    domains: list[str] = field(default_factory=list)
    parser: str = "rules"

    @property
    def team_description(self) -> str | None:
        return ", ".join(self.domains) or None

    def title(self) -> str | None:
        if not (self.specialization and self.grade):
            return None
        base = f"{GRADE_LABELS[self.grade]} {SPEC_LABELS[self.specialization]}"
        main = [s.label for s in self.required if s.in_catalog][:2]
        return f"{base} ({', '.join(main)})" if main else base

    def to_result(self) -> dict[str, Any]:
        draft: dict[str, Any] = {
            "title": self.title(),
            "specialization": self.specialization,
            "grade": self.grade,
            "skills_required": [s.code for s in self.required if s.in_catalog],
            "skills_desired": [s.code for s in self.desired if s.in_catalog],
            "team_description": self.team_description,
            "work_format": self.work_format,
            "city": self.city,
            "salary_from": self.salary_from,
            "salary_to": self.salary_to,
        }
        recognized = [
            k
            for k in (
                "specialization",
                "grade",
                "skills_required",
                "skills_desired",
                "team_description",
                "work_format",
                "city",
                "salary_from",
                "salary_to",
            )
            if draft[k] not in (None, [])
        ]
        # технологии, которых нет в справочнике стека: показываем, чтобы рекрутер решил сам
        unrecognized = [s.label for s in (*self.required, *self.desired) if not s.in_catalog]
        return {
            "draft": draft,
            "parser": self.parser,
            "recognized_fields": recognized,
            "unrecognized": unrecognized,
        }


def _desired_positions(text: str) -> list[tuple[int, int]]:
    """Отрезки текста «желательного» стека: от маркера до конца фразы (или до раздела)."""
    spans: list[tuple[int, int]] = []
    # разделы markdown: «## Будет плюсом» действует до следующего заголовка
    for m in re.finditer(r"^#+[^\n]*$", text, re.MULTILINE):
        if re.search(DESIRED_MARKERS, m.group(0), re.IGNORECASE):
            nxt = re.search(r"^#+", text[m.end() :], re.MULTILINE)
            spans.append((m.end(), m.end() + nxt.start() if nxt else len(text)))
    for m in re.finditer(DESIRED_MARKERS, text, re.IGNORECASE):
        line_start = text.rfind("\n", 0, m.start()) + 1
        if text[line_start : m.start()].lstrip().startswith("#"):
            continue
        end = _CLAUSE_END.search(text, m.end())
        stop = end.start() if end else len(text)
        req = re.search(REQUIRED_MARKERS, text[m.end() : stop], re.IGNORECASE)
        if req:
            stop = m.end() + req.start()
        spans.append((m.start(), stop))
    return spans


def split_stack(text: str) -> tuple[list[SkillMention], list[SkillMention]]:
    """Технологии → (обязательные, желательные)."""
    spans = _desired_positions(text)
    required: list[SkillMention] = []
    desired: list[SkillMention] = []
    for s in find_skills(text):
        if any(a <= s.start < b for a, b in spans):
            desired.append(s)
        else:
            required.append(s)
    return required, desired


def parse_rules(text: str) -> NeedParse:
    required, desired = split_stack(text)
    spec = detect_specialization(text, [*required, *desired])
    grade, _ = detect_grade(text)
    salary = detect_salary(text)
    city, _ = detect_city(text)
    return NeedParse(
        specialization=spec.code,
        grade=grade,
        required=required,
        desired=desired,
        work_format=primary_work_format(text),
        city=city,
        salary_from=salary.salary_from if salary else None,
        salary_to=salary.salary_to if salary else None,
        domains=detect_domains(text),
    )


# ---------------------------------------------------------------- LLM

SpecLiteral = Literal["backend", "frontend", "mobile", "data_ml", "qa", "devops"]
GradeLiteral = Literal["intern", "junior", "middle", "senior"]
FormatLiteral = Literal["office", "hybrid", "remote"]


class LlmNeed(BaseModel):
    specialization: SpecLiteral | None = None
    grade: GradeLiteral | None = None
    skills_required: list[str] = Field(default_factory=list, max_length=30)
    skills_desired: list[str] = Field(default_factory=list, max_length=30)
    work_format: FormatLiteral | None = None
    city: str | None = Field(default=None, max_length=100)
    salary_from: int | None = Field(default=None, ge=0, le=10_000_000)
    salary_to: int | None = Field(default=None, ge=0, le=10_000_000)
    team_description: str | None = Field(default=None, max_length=300)


NEED_SYSTEM_PROMPT = (
    "Ты разбираешь запрос работодателя на IT-специалиста. Верни только JSON с полями: "
    "specialization (backend|frontend|mobile|data_ml|qa|devops|null), "
    "grade (intern|junior|middle|senior|null; «лид» = senior, «джун+» = junior), "
    "skills_required и skills_desired (списки названий технологий; «желательно/плюсом» — "
    "в desired), work_format (office|hybrid|remote|null), city (официальное название или null), "
    "salary_from и salary_to (рубли целым числом; «300–400к» = 300000 и 400000; "
    "одна сумма — оба поля), team_description (предметная область коротко или null). "
    "Не выдумывай: чего нет в тексте — null."
)


def _mention(name: str) -> SkillMention | None:
    code = normalize_skill(name)
    if code is None:
        return None
    return SkillMention(code, label(code), is_catalog(code), name, -1, -1)


def merge_llm(rules: NeedParse, answer: LlmNeed) -> NeedParse:
    """Поля LLM поверх правил; технологии — только узнанные справочником синонимов."""
    req = [m for m in (_mention(n) for n in answer.skills_required) if m]
    des = [m for m in (_mention(n) for n in answer.skills_desired) if m]
    req_codes = {m.code for m in req}
    des = [m for m in des if m.code not in req_codes]
    salary_from, salary_to = answer.salary_from, answer.salary_to
    if salary_from and salary_to and salary_from > salary_to:
        salary_from, salary_to = rules.salary_from, rules.salary_to
    return NeedParse(
        specialization=answer.specialization or rules.specialization,
        grade=answer.grade or rules.grade,
        required=req or rules.required,
        desired=des if (req or des) else rules.desired,
        work_format=answer.work_format or rules.work_format,
        city=answer.city or rules.city,
        salary_from=salary_from if salary_from is not None else rules.salary_from,
        salary_to=salary_to if salary_to is not None else rules.salary_to,
        domains=[answer.team_description] if answer.team_description else rules.domains,
        parser="llm",
    )


def parse_detailed(text: str) -> NeedParse:
    rules = parse_rules(text)
    if not llm.llm_enabled():
        return rules
    answer = llm.complete_json(NEED_SYSTEM_PROMPT, text, LlmNeed)
    return merge_llm(rules, answer) if answer else rules


def parse_need(text: str) -> dict[str, Any]:
    """Текст → черновик потребности (формат ответа NeedParseResult из контракта)."""
    return parse_detailed(text).to_result()
