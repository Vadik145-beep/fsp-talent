"""Счёт кандидата для потребности и объяснение «почему в подборке» (T6.3).

Формула повторяет прототип рекрутера (одобрен пользователем):
счёт = Σ value(фактор) × weight(фактор), веса — `platform_settings.ranking_weights`
(нормируются к сумме 1, чтобы счёт был в 0..1 и сумма вкладов точно равнялась счёту).

Факторы (value в 0..1):
- stack — `app.nlp.similarity.stack_match` (обязательный стек 0,75, желательный 0,25);
- theta — Φ(θ): доля специалистов с уровнем ниже (θ ~ N(0, 1)); без теста — 0;
- fsp — ФСП-скор / 100, если кандидат показывает достижения; без ФСП — 0 (нет бонуса,
  штрафа нет: остальные факторы не меняются). Скор считается под специализацию потребности:
  очки каждого достижения умножаются на релевантность дисциплины
  (`app.fsp.scoring.fsp_score_for`, таблица `DISCIPLINE_RELEVANCE`);
- freshness — свежесть профиля (регулярные задания);
- salary — 1, если минимум кандидата ≤ «от» вилки; 0,7 — если ≤ «до»; иначе 0;
- work_format — 1 при совпадении формата; 0,5 — кандидат на гибриде, а нужна удалёнка; иначе 0.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.fsp.scoring import fsp_reason_for, fsp_score_for
from app.nlp.similarity import matched_skills, stack_match

DEFAULT_WEIGHTS: dict[str, float] = {
    "stack": 0.3,
    "theta": 0.25,
    "fsp": 0.15,
    "freshness": 0.1,
    "salary": 0.1,
    "work_format": 0.1,
}
FACTOR_LABELS = {
    "stack": "Стек",
    "theta": "Результат теста",
    "fsp": "Достижения ФСП",
    "freshness": "Свежесть профиля",
    "salary": "Зарплата",
    "work_format": "Формат работы",
}
WORK_FORMAT_LABELS = {"office": "офис", "hybrid": "гибрид", "remote": "удалённо"}


def normal_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def clip(value: float) -> float:
    return max(0.0, min(1.0, value))


def weights_from(settings: dict[str, Any]) -> dict[str, float]:
    """Веса из настроек платформы; незаданные — по умолчанию; нормировка к сумме 1."""
    raw = {**DEFAULT_WEIGHTS, **(settings.get("ranking_weights") or {})}
    weights = {f: max(0.0, float(raw.get(f, 0.0))) for f in FACTOR_LABELS}
    total = sum(weights.values())
    if total <= 0:
        return {f: 1 / len(weights) for f in weights}
    return {f: w / total for f, w in weights.items()}


@dataclass
class NeedLike:
    skills_required: list[str]
    skills_desired: list[str]
    salary_from: int
    salary_to: int
    work_format: str
    # специализация потребности: от неё зависит релевантность дисциплин ФСП
    specialization: str | None = None


def salary_value(min_salary: int | None, salary_from: int, salary_to: int) -> float:
    minimum = min_salary or 0
    if minimum <= salary_from:
        return 1.0
    return 0.7 if minimum <= salary_to else 0.0


def format_value(need_format: str, candidate_formats: list[str]) -> float:
    if need_format in candidate_formats:
        return 1.0
    if need_format != "office" and "hybrid" in candidate_formats:
        return 0.5
    return 0.0


def score_candidate(
    cand: dict[str, Any],
    need: NeedLike,
    weights: dict[str, float],
    label: Callable[[str], str],
    fsp_reason: str | None = None,
) -> dict[str, Any]:
    """Счёт, разбивка и причины для кандидата (запись профиля + ФСП из `fsp_summaries`).

    В `cand` ожидаются: stack, theta, topic_scores, fsp_id, fsp_score, fsp_badges, privacy,
    freshness, min_salary, work_formats, category_label. `label` — подпись технологии по коду.
    Если есть `fsp_achievements` (достижения из `fsp_summaries`) и у потребности задана
    специализация, ФСП-фактор и причина считаются с учётом релевантности дисциплин;
    иначе берётся общий `fsp_score` (так считает валидация на синтетике без дисциплин).
    """
    stack = list(cand.get("stack") or [])
    req, des = list(need.skills_required), list(need.skills_desired)
    req_hit = matched_skills(req, stack)
    des_hit = matched_skills(des, stack)
    show_fsp = bool(cand.get("fsp_id")) and (cand.get("privacy") or {}).get(
        "show_fsp_achievements", True
    )
    theta = cand.get("theta")
    achievements = cand.get("fsp_achievements") or []
    fsp_score = cand.get("fsp_score")
    if achievements and need.specialization:
        fsp_score = fsp_score_for(achievements, need.specialization)
        fsp_reason = fsp_reason_for(achievements, need.specialization)
    values = {
        "stack": stack_match(req, des, stack),
        "theta": 0.0 if theta is None else normal_cdf(float(theta)),
        "fsp": min(1.0, float(fsp_score) / 100) if show_fsp and fsp_score else 0.0,
        "freshness": float(cand.get("freshness") or 0),
        "salary": salary_value(cand.get("min_salary"), need.salary_from, need.salary_to),
        "work_format": format_value(need.work_format, list(cand.get("work_formats") or [])),
    }
    breakdown: list[dict[str, Any]] = []
    contrib: dict[str, float] = {}
    for factor, value in values.items():
        v = round(clip(value), 4)
        w = round(weights.get(factor, 0.0), 4)
        contrib[factor] = round(v * w, 4)
        breakdown.append(
            {
                "factor": factor,
                "label": FACTOR_LABELS[factor],
                "value": v,
                "weight": w,
                "contribution": contrib[factor],
            }
        )
    score = round(min(1.0, sum(contrib.values())), 4)

    # «Почему в подборке»: причины по самым весомым факторам, 2–4 штуки
    reasons: list[tuple[str, float]] = []
    if req_hit:
        extra = f", плюс {', '.join(map(label, des_hit))}" if des_hit else ""
        reasons.append(
            (
                f"Стек: {len(req_hit)} из {len(req)} обязательных "
                f"({', '.join(map(label, req_hit))}){extra}",
                contrib["stack"],
            )
        )
    elif des_hit:
        reasons.append(
            (f"Есть желательные технологии: {', '.join(map(label, des_hit))}", contrib["stack"])
        )
    if theta is not None:
        strong = [t["label"] for t in cand.get("topic_scores") or [] if t.get("level") == "strong"]
        pct = min(99, max(1, round(values["theta"] * 100)))  # как на карточке: 1–99 %
        topics = f"; сильные темы: {', '.join(strong[:2])}" if strong else ""
        reasons.append(
            (f"Тест сильнее, чем у {pct} % специалистов{topics}", contrib["theta"] + 0.01)
        )
    if values["fsp"] > 0:
        badges = cand.get("fsp_badges") or []
        detail = fsp_reason or (badges[0].get("title") if badges else None)
        reasons.append(
            (f"Подтверждено ФСП: {detail}" if detail else "Подтверждено ФСП", contrib["fsp"])
        )
    if values["freshness"] >= 0.6:
        reasons.append(("Профиль свежий: недавно решал задания", contrib["freshness"]))
    if values["salary"] == 1:
        reasons.append(("Ожидания по зарплате укладываются в вилку", contrib["salary"]))
    if values["work_format"] == 1:
        fmt = WORK_FORMAT_LABELS.get(need.work_format, need.work_format)
        reasons.append((f"Готов работать: {fmt}", contrib["work_format"] * 0.9))
    reasons.sort(key=lambda r: -r[1])
    top = [text for text, _ in reasons[:4]]
    if len(top) < 2:
        top.append(f"Категория по тесту: {cand.get('category_label') or '—'}")
    if len(top) < 2:
        top.append("Подходит по категории потребности")
    return {
        "score": score,
        "breakdown": breakdown,
        "reasons": top,
        "salary_fit": (cand.get("min_salary") or 0) <= need.salary_to,
    }
