"""Тест из текста вакансии (T4.8): специализация, грейд, темы → шаблоны банка → черновики.

1. Специализация и грейд — правилами (заголовок вакансии весит больше текста).
2. Темы — словарь `vacancy_topics.TOPICS`: ключевые слова с уверенностью; «Будет плюсом»
   весит вдвое меньше обязательных требований.
3. По каждой теме — шаблон из `bank_registry()`, ближайший по грейду (с объяснением выбора).
4. Тема без шаблонов в банке → черновик нового шаблона (LLM при ключе, иначе заготовка
   словаря) в таблице `items` со статусом draft: админ одобряет его как пилотный.
"""

from __future__ import annotations

import hashlib
import logging
import random
import re
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.nlp import llm
from app.nlp.models import VacancyTest
from app.nlp.need_parser import _desired_positions
from app.nlp.settings import get_nlp_settings
from app.nlp.skills_lexicon import find_skills
from app.nlp.text_rules import (
    GRADE_LABELS,
    GRADES,
    SPEC_LABELS,
    detect_grade,
    detect_specialization,
    grade_from_experience,
)
from app.nlp.vacancy_topics import TOPICS, VacancyTopic, catalog_topic_of
from app.testing.engine.bank import bank_registry
from app.testing.engine.templates import ItemTemplate
from app.testing.models import Item

log = logging.getLogger(__name__)

MAX_TOPICS = 8
MIN_ITEMS = 5
CROSS_SPEC_FACTOR = 0.9
# форматы движка → форматы контракта (ItemFormat)
FORMAT_TO_CONTRACT = {"multi_choice": "multiple_choice", "find_bug_line": "find_error_line"}
DRAFT_B = {"intern": -1.5, "junior": -0.5, "middle": 0.5, "senior": 1.5}


@dataclass
class TopicHit:
    topic: VacancyTopic
    matched: list[str]
    score: float
    confidence: float
    covered: bool


@dataclass
class VacancyAnalysis:
    title: str
    specialization: str
    grade: str
    spec_reason: str
    grade_reason: str
    topics: list[TopicHit] = field(default_factory=list)


def vacancy_title(text: str) -> str:
    for line in text.splitlines():
        clean = re.sub(r"[#*_`>]+", "", line).strip()
        if clean:
            return clean[:200]
    return "Вакансия"


def _bank_by_key() -> dict[tuple[str, str], list[ItemTemplate]]:
    result: dict[tuple[str, str], list[ItemTemplate]] = {}
    for t in bank_registry():
        if str(t.status) == "active" or getattr(t.status, "value", "") == "active":
            result.setdefault((t.specialization, t.topic), []).append(t)
    return result


def _grade(title: str, text: str) -> tuple[str, str]:
    g, word = detect_grade(title)
    if g:
        return g, f"Грейд {GRADE_LABELS[g]} взят из заголовка вакансии («{word}»)"
    g, word = detect_grade(text)
    if g:
        return g, f"Грейд {GRADE_LABELS[g]} найден в тексте вакансии («{word}»)"
    m = re.search(r"от\s*(\d+(?:[.,]\d+)?)\s*(?:лет|года|год)", text, re.IGNORECASE)
    if m:
        years = float(m.group(1).replace(",", "."))
        g = grade_from_experience(years) or "middle"
        return g, f"Грейд {GRADE_LABELS[g]} — по требуемому стажу от {m.group(1)} лет"
    return "middle", "Грейд в тексте не указан — взят Middle по умолчанию"


def analyze_vacancy(text: str, specialization: str | None = None) -> VacancyAnalysis:
    title = vacancy_title(text)
    skills = find_skills(text)
    if specialization:
        spec, spec_reason = specialization, "Специализация задана администратором"
    else:
        guess = detect_specialization(text, skills, title=title)
        spec = guess.code or "backend"
        evidence = ", ".join(dict.fromkeys(guess.evidence[:4])) or "нет явных признаков"
        spec_reason = f"Специализация {SPEC_LABELS[spec]} — по словам: {evidence}"
    grade, grade_reason = _grade(title, text)

    desired = _desired_positions(text)
    bank = _bank_by_key()
    hits: list[TopicHit] = []
    for topic in TOPICS:
        if spec not in topic.specs:
            continue
        score, matched = 0.0, list[str]()
        for pattern in topic.keywords:
            found = list(re.finditer(pattern, text, re.IGNORECASE))
            if not found:
                continue
            strong = any(not any(a <= m.start() < b for a, b in desired) for m in found)
            score += 1.0 if strong else 0.5
            if re.search(pattern, title, re.IGNORECASE):
                score += 1.5
            word = found[0].group(0).strip()
            if word.lower() not in (w.lower() for w in matched):
                matched.append(word)
        if score <= 0:
            continue
        conf = min(0.95, 0.4 + 0.15 * score)
        if topic.specs[0] != spec:
            conf *= CROSS_SPEC_FACTOR
        covered = any(bank.get(key) for key in topic.bank)
        hits.append(TopicHit(topic, matched[:5], score, round(conf, 2), covered))
    order = {t.id: i for i, t in enumerate(TOPICS)}
    hits.sort(key=lambda h: (-h.confidence, -h.score, order[h.topic.id]))
    return VacancyAnalysis(title, spec, grade, spec_reason, grade_reason, hits[:MAX_TOPICS])


# ---------------------------------------------------------------- выбор шаблонов


@dataclass
class Pick:
    template: ItemTemplate
    hit: TopicHit
    reason: str


def _grade_distance(a: str, b: str) -> int:
    return abs(GRADES.index(a) - GRADES.index(b))


def choose_templates(analysis: VacancyAnalysis) -> list[Pick]:
    bank = _bank_by_key()
    used: set[str] = set()
    picks: list[Pick] = []

    def candidates(hit: TopicHit) -> list[ItemTemplate]:
        pool: list[ItemTemplate] = []
        for key in hit.topic.bank:
            pool += [t for t in bank.get(key, []) if t.id not in used]
        bank_order = {key: i for i, key in enumerate(hit.topic.bank)}
        return sorted(
            pool,
            key=lambda t: (
                _grade_distance(t.target_grade, analysis.grade),
                0 if t.specialization == analysis.specialization else 1,
                bank_order[(t.specialization, t.topic)],
                t.id,
            ),
        )

    def reason(hit: TopicHit, t: ItemTemplate, second: bool) -> str:
        words = ", ".join(hit.matched[:3])
        dist = _grade_distance(t.target_grade, analysis.grade)
        grade_part = (
            f"грейд {GRADE_LABELS[t.target_grade]} совпадает с вакансией"
            if dist == 0
            else f"ближайший доступный грейд {GRADE_LABELS[t.target_grade]} "
            f"(шаблонов {GRADE_LABELS[analysis.grade]} по теме в банке нет)"
        )
        lead = "Дополнительная задача по теме" if second else "Тема"
        return f"{lead} «{hit.topic.label}» найдена по словам: {words}; {grade_part}"

    for hit in analysis.topics:
        pool = candidates(hit)
        if pool:
            used.add(pool[0].id)
            picks.append(Pick(pool[0], hit, reason(hit, pool[0], False)))
    # короткий тест добираем вторыми задачами по самым уверенным темам
    changed = True
    while len(picks) < MIN_ITEMS and changed:
        changed = False
        for hit in analysis.topics:
            if len(picks) >= MIN_ITEMS:
                break
            pool = candidates(hit)
            if pool and any(p.hit is hit for p in picks):
                used.add(pool[0].id)
                picks.append(Pick(pool[0], hit, reason(hit, pool[0], True)))
                changed = True
    return picks


# ---------------------------------------------------------------- черновики (LLM / словарь)

ContractFormat = Literal[
    "single_choice",
    "multiple_choice",
    "numeric",
    "short_text",
    "code_output",
    "find_error_line",
    "ordering",
]

Option = Annotated[str, Field(min_length=1, max_length=120)]


class LlmDraft(BaseModel):
    """Ответ модели: вопрос с выбором одного ответа. Формат жёсткий — его проще проверить."""

    title: str = Field(min_length=5, max_length=80)
    question: str = Field(min_length=20, max_length=600)
    options: list[Option] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    explanation: str = Field(min_length=10, max_length=400)


# Пример в подсказке заметно улучшает ответы маленькой модели (короткие разные варианты)
DRAFT_SYSTEM_PROMPT = (
    "Ты автор тестовых вопросов для проверки IT-специалистов. Составь один вопрос с выбором "
    "одного ответа по теме и грейду. Вопрос — про конкретное знание (что делает команда, чем "
    "отличаются понятия, что выведет код). Варианты — короткие (до 10 слов), разные по смыслу, "
    "ровно один верный. Пиши по-русски.\n"
    'Пример ответа: {"title": "Индексы в PostgreSQL", "question": "Какой индекс PostgreSQL '
    'создаёт по умолчанию команда CREATE INDEX?", "options": ["B-tree", "Hash", "GIN", '
    '"BRIN"], "correct_index": 0, "explanation": "Без USING создаётся B-tree: он поддерживает '
    'и равенство, и диапазоны."}'
)
DRAFT_MAX_TOKENS = 400
_CYRILLIC = re.compile(r"[а-яё]", re.IGNORECASE)
# иероглифы и хангыль (маленькие модели иногда переходят на китайский)
_CJK = re.compile(f"[{chr(0x3000)}-{chr(0x9FFF)}{chr(0xAC00)}-{chr(0xD7AF)}]")
# «1. », «А) », «b: » в начале варианта — нумерацию модели убираем
_OPTION_NUMBER = re.compile(r"^\s*(?:\d{1,2}|[a-dа-г])\s*[.):]\s+", re.IGNORECASE)


def clean_option(text: str) -> str:
    return _OPTION_NUMBER.sub("", re.sub(r"\s+", " ", text)).strip()


def check_llm_draft(d: LlmDraft) -> str | None:
    """Проверка сверх схемы: None — черновик годится, иначе причина отказа."""
    texts = [d.title, d.question, d.explanation, *d.options]
    if any(_CJK.search(t) for t in texts):
        return "в ответе иероглифы"
    if not (_CYRILLIC.search(d.question) and _CYRILLIC.search(d.explanation)):
        return "вопрос или объяснение не по-русски"
    opts = [clean_option(o).lower() for o in d.options]
    if any(not o for o in opts) or len(set(opts)) < len(opts):
        return "варианты ответа повторяются или пустые"
    if any(o == d.question.strip().lower() for o in opts):
        return "вариант ответа повторяет вопрос"
    return None


def _shuffled(d: LlmDraft, key: str) -> tuple[list[str], str]:
    """Перемешиваем варианты (модели любят ставить правильный первым); порядок воспроизводим."""
    options = [clean_option(o) for o in d.options]
    answer = options[d.correct_index]
    rnd = random.Random(int(hashlib.sha1(key.encode()).hexdigest()[:8], 16))
    rnd.shuffle(options)
    return options, answer


def draft_user_prompt(hit: TopicHit, analysis: VacancyAnalysis) -> str:
    """В модель уходят только тема, специализация, грейд и слова-признаки темы из вакансии."""
    return (
        f"Тема: {hit.topic.label}. Специализация: {SPEC_LABELS[analysis.specialization]}. "
        f"Грейд: {GRADE_LABELS[analysis.grade]}. Слова из вакансии: {', '.join(hit.matched)}."
    )


async def llm_draft(hit: TopicHit, analysis: VacancyAnalysis) -> dict[str, Any] | None:
    """Черновик от модели или None (недоступна, таймаут, ответ не прошёл проверку)."""
    cfg = get_nlp_settings()
    answer = await llm.acomplete_json(
        DRAFT_SYSTEM_PROMPT,
        draft_user_prompt(hit, analysis),
        LlmDraft,
        timeout=cfg.llm_draft_timeout_sec,
        max_tokens=DRAFT_MAX_TOKENS,
    )
    if answer is None:
        return None
    problem = check_llm_draft(answer)
    if problem:
        log.warning("Черновик от LLM по теме %s отклонён: %s", hit.topic.id, problem)
        return None
    options, correct = _shuffled(answer, f"{hit.topic.id}|{analysis.grade}")
    return {
        "title": answer.title.strip(),
        "format": "single_choice",
        "prompt": answer.question.strip(),
        "options": options,
        "answer": correct,
        "explanation": answer.explanation.strip(),
        "model": cfg.llm_label,
        "model_local": cfg.llm_local,
    }


def vocabulary_draft(hit: TopicHit) -> dict[str, Any]:
    seed = hit.topic.draft
    if seed is None:
        return {
            "title": f"Задача по теме «{hit.topic.label}»",
            "format": "short_text",
            "prompt": f"Опишите, как вы применяли {', '.join(hit.matched)} в работе.",
        }
    return {"title": seed.title, "format": seed.format, "prompt": seed.prompt}


async def draft_content(
    hit: TopicHit, analysis: VacancyAnalysis, *, use_llm: bool = True
) -> tuple[dict[str, Any], str]:
    """Содержимое черновика и источник: «llm» или «vocabulary»."""
    if use_llm and llm.llm_enabled():
        content = await llm_draft(hit, analysis)
        if content:
            return content, "llm"
    return vocabulary_draft(hit), "vocabulary"


def _drafts_note(drafts: list[dict[str, Any]], origins: set[str]) -> str:
    model = next((d["model"] for d in drafts if d.get("model")), None) or "LLM"
    local = any(d.get("model_local") for d in drafts)
    where = " локально на нашем сервере — текст вакансии наружу не передавался" if local else ""
    if origins == {"llm"}:
        return (
            f"Черновики написала нейросеть {model}{where}; формат и варианты ответа проверены "
            "автоматически, в тесты черновик идёт только после одобрения админом"
        )
    if "llm" in origins:
        return (
            f"Часть черновиков написала нейросеть {model}{where}, остальные собраны по словарю "
            "тем (лимит черновиков от нейросети на вакансию, или она не ответила вовремя, "
            "или ответ не прошёл проверку)"
        )
    return "Черновики собраны по словарю тем (нейросеть не подключена или не ответила)"


# ---------------------------------------------------------------- сервис


def _item_code(template_id: str) -> str:
    if len(template_id) <= 32:
        return template_id
    digest = hashlib.sha1(template_id.encode()).hexdigest()[:8]
    return f"{template_id[:23]}-{digest}"


class VacancyTestService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_bank_item(self, t: ItemTemplate) -> int:
        """id строки `items` для шаблона банка; если её нет — регистрируем шаблон."""
        code = _item_code(t.id)
        found = await self.session.scalar(
            select(Item.id).where(or_(Item.generator == t.id, Item.code == code)).limit(1)
        )
        if found is not None:
            return int(found)
        fmt = str(getattr(t.format, "value", t.format))
        item = Item(
            code=code,
            title=(t.title or t.id)[:200],
            description="Шаблон банка задач; зарегистрирован при сборке теста из вакансии.",
            specialization=t.specialization,
            topic=catalog_topic_of(t.specialization, t.topic),
            target_grade=t.target_grade,
            format=FORMAT_TO_CONTRACT.get(fmt, fmt),
            generator=t.id,
            generator_params={},
            a=t.a,
            b=t.b,
            status="active",
            source="expert",
        )
        self.session.add(item)
        await self.session.flush()
        return int(item.id)

    async def find_draft(
        self, hit: TopicHit, analysis: VacancyAnalysis
    ) -> tuple[int, dict[str, Any], str] | None:
        """Уже созданный черновик темы и грейда: (id, содержимое, источник) — новый не плодим."""
        item = await self.session.scalar(
            select(Item)
            .where(
                Item.generator == f"draft:{hit.topic.id}",
                Item.target_grade == analysis.grade,
                Item.specialization == analysis.specialization,
                Item.status.in_(("draft", "pilot")),
            )
            .limit(1)
        )
        if item is None:
            return None
        params = item.generator_params or {}
        content: dict[str, Any] = {
            "title": item.title,
            "format": item.format,
            "prompt": params.get("prompt") or item.description or "",
            "status": item.status,
        }
        for key in ("options", "answer", "explanation", "model", "model_local"):
            if params.get(key) not in (None, "", []):
                content[key] = params[key]
        return int(item.id), content, str(params.get("origin") or "vocabulary")

    async def create_draft_item(
        self, hit: TopicHit, analysis: VacancyAnalysis, content: dict[str, Any], origin: str
    ) -> int:
        """Черновик в `items` (status=draft); варианты и ответ — в generator_params."""
        key = f"{hit.topic.id}|{analysis.specialization}|{analysis.grade}"
        params: dict[str, Any] = {
            "prompt": content["prompt"],
            "topic": hit.topic.id,
            "topic_label": hit.topic.label,
            "origin": origin,
        }
        for extra in ("options", "answer", "explanation", "model", "model_local"):
            if extra in content:
                params[extra] = content[extra]
        lines = [content["prompt"]]
        if content.get("options"):
            lines += ["", "Варианты: " + "; ".join(content["options"])]
            lines.append(f"Правильный ответ: {content['answer']}")
        if content.get("explanation"):
            lines.append(f"Объяснение: {content['explanation']}")
        description = "\n".join(lines)
        item = Item(
            code=f"draft-{hashlib.sha1(key.encode()).hexdigest()[:12]}",
            title=content["title"][:200],
            description=description,
            specialization=analysis.specialization,
            topic=hit.topic.catalog_topic(analysis.specialization),
            target_grade=analysis.grade,
            format=content["format"],
            generator=f"draft:{hit.topic.id}",
            generator_params=params,
            a=1.0,
            b=DRAFT_B[analysis.grade],
            status="draft",
            source="llm_vacancy",
        )
        self.session.add(item)
        await self.session.flush()
        return int(item.id)

    async def build(self, text: str, specialization: str | None = None) -> dict[str, Any]:
        analysis = analyze_vacancy(text, specialization)
        picks = choose_templates(analysis)
        picked_topics = {p.hit.topic.id for p in picks}

        items = []
        for p in picks:
            item_id = await self.ensure_bank_item(p.template)
            items.append(
                {
                    "item_id": item_id,
                    "code": _item_code(p.template.id),
                    "title": p.template.title or p.template.id,
                    "topic": p.hit.topic.id,
                    "reason": p.reason,
                    "template_id": p.template.id,
                    "target_grade": p.template.target_grade,
                }
            )

        drafts = []
        origins: set[str] = set()
        # модель медленная (2 ядра): пишет не больше N черновиков на вакансию; если не ответила
        # или ответ не прошёл проверку — остальные темы сразу по словарю, без новых ожиданий
        llm_left = get_nlp_settings().llm_max_drafts
        for hit in analysis.topics:
            if hit.topic.id in picked_topics or hit.covered:
                continue
            found = await self.find_draft(hit, analysis)
            if found:
                item_id, content, origin = found
                reused = True
            else:
                content, origin = await draft_content(hit, analysis, use_llm=llm_left > 0)
                if llm.llm_enabled() and llm_left > 0:
                    llm_left = llm_left - 1 if origin == "llm" else 0
                item_id = await self.create_draft_item(hit, analysis, content, origin)
                reused = False
            origins.add(origin)
            drafts.append(
                {
                    "item_id": item_id,
                    "topic": hit.topic.id,
                    "label": hit.topic.label,
                    "title": content["title"],
                    "format": content["format"],
                    "prompt": content["prompt"],
                    "options": content.get("options", []),
                    "answer": content.get("answer"),
                    "explanation": content.get("explanation"),
                    "status": content.get("status", "draft"),
                    "origin": origin,
                    "model": content.get("model"),
                    "model_local": bool(content.get("model_local", False)),
                    "reused": reused,
                }
            )

        explanation = [analysis.spec_reason, analysis.grade_reason]
        covered = [h for h in analysis.topics if h.topic.id in picked_topics]
        explanation.append(
            f"Найдено тем: {len(analysis.topics)}; покрыты шаблонами банка: {len(covered)}; "
            f"в тесте задач: {len(items)}"
        )
        lower = sorted(
            {
                p.hit.topic.label
                for p in picks
                if _grade_distance(p.template.target_grade, analysis.grade) > 0
            }
        )
        if lower:
            explanation.append(
                f"Для тем {', '.join(f'«{x}»' for x in lower)} шаблонов грейда "
                f"{GRADE_LABELS[analysis.grade]} нет — взяты ближайшие по грейду"
            )
        for d in drafts:
            what = "уже есть черновик" if d["reused"] else "создан черновик"
            explanation.append(
                f"Для темы «{d['label']}» шаблонов в банке нет — {what} (задача #{d['item_id']}); "
                "после одобрения админом он пойдёт в тесты как непроверочный (пилот)"
            )
        if drafts:
            explanation.append(_drafts_note(drafts, origins))
        parser = "llm" if "llm" in origins else "rules"
        topics = [
            {
                "topic": h.topic.id,
                "label": h.topic.label,
                "matched_by": h.matched,
                "confidence": h.confidence,
                "covered": h.covered,
            }
            for h in analysis.topics
        ]
        row = VacancyTest(
            vacancy_title=analysis.title,
            vacancy_text=text,
            specialization=analysis.specialization,
            grade=analysis.grade,
            parser=parser,
            result={
                "topics": topics,
                "items": items,
                "drafts": drafts,
                "explanation": explanation,
            },
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return self.to_dict(row)

    @staticmethod
    def to_dict(row: VacancyTest) -> dict[str, Any]:
        return {
            "id": row.id,
            "vacancy_title": row.vacancy_title,
            "vacancy_text": row.vacancy_text,
            "specialization": row.specialization,
            "grade": row.grade,
            "parser": row.parser,
            "created_at": row.created_at,
            **row.result,
        }

    async def list(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = (
            await self.session.scalars(
                select(VacancyTest).order_by(VacancyTest.id.desc()).limit(limit)
            )
        ).all()
        return [self.to_dict(r) for r in rows]
