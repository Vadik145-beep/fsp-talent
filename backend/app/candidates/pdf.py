"""Стандартизированный PDF-профиль кандидата в стиле ФСП (T3.3).

reportlab + свободные шрифты с кириллицей из `fonts/`: JetBrains Mono (OFL) — заголовки,
DejaVu Sans (Bitstream Vera / public domain) — текст. Цвета брендбука ФСП:
#402FFF — основной, #EC1D35 — только акцент, #1B1C21 — текст, #EDEDED / #C8C9CA — линии и фон.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

# у reportlab нет аннотаций типов (types-reportlab не в зависимостях проекта)
from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.lib.enums import TA_RIGHT  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
from reportlab.lib.styles import ParagraphStyle  # type: ignore[import-untyped]
from reportlab.lib.units import mm  # type: ignore[import-untyped]
from reportlab.pdfbase import pdfmetrics  # type: ignore[import-untyped]
from reportlab.pdfbase.ttfonts import TTFont  # type: ignore[import-untyped]
from reportlab.pdfgen.canvas import Canvas  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    Flowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.nlp.skills_lexicon import label as skill_label
from app.nlp.text_rules import GRADE_LABELS, SPEC_LABELS

FONTS_DIR = Path(__file__).with_name("fonts")

BLUE = colors.HexColor("#402FFF")
RED = colors.HexColor("#EC1D35")
INK = colors.HexColor("#1B1C21")
LIGHT = colors.HexColor("#EDEDED")
GREY = colors.HexColor("#C8C9CA")
MUTED = colors.HexColor("#5B5C66")
FRAME_PAD = 6  # pt, внутренний отступ Frame в SimpleDocTemplate
MAX_ACHIEVEMENTS = 5


def _ru_num(value: float) -> str:
    """0.42 → «0,42», -1.98 → «-1,98» (десятичная запятая, как во всём интерфейсе)."""
    return f"{value:.2f}".replace(".", ",")


LEVEL_LABELS = {"strong": "сильная сторона", "ok": "в пределах уровня", "weak": "зона роста"}
FORMAT_LABELS = {"office": "офис", "hybrid": "гибрид", "remote": "удалённо"}
DISCIPLINE_LABELS = {
    "product": "продуктовое программирование",
    "algorithmic": "алгоритмическое программирование",
    "cybersecurity": "программирование систем ИБ",
    "security": "программирование систем ИБ",
    "robotics": "программирование робототехники",
    "uas": "программирование БАС",
    "uav": "программирование БАС",
}
COMP_LEVEL_LABELS = {
    "regional": "региональное",
    "national": "всероссийское",
    "international": "международное",
}


@lru_cache
def register_fonts() -> None:
    for name, file in (
        ("FspMono", "JetBrainsMono-Regular.ttf"),
        ("FspMono-Bold", "JetBrainsMono-Bold.ttf"),
        ("FspSans", "DejaVuSans.ttf"),
        ("FspSans-Bold", "DejaVuSans-Bold.ttf"),
    ):
        pdfmetrics.registerFont(TTFont(name, str(FONTS_DIR / file)))
    pdfmetrics.registerFontFamily(
        "FspSans",
        normal="FspSans",
        bold="FspSans-Bold",
        italic="FspSans",
        boldItalic="FspSans-Bold",
    )
    pdfmetrics.registerFontFamily(
        "FspMono",
        normal="FspMono",
        bold="FspMono-Bold",
        italic="FspMono",
        boldItalic="FspMono-Bold",
    )


@lru_cache
def styles() -> dict[str, ParagraphStyle]:
    register_fonts()
    base = ParagraphStyle("base", fontName="FspSans", fontSize=9.5, leading=13.5, textColor=INK)
    return {
        "base": base,
        "muted": ParagraphStyle("muted", parent=base, textColor=MUTED, fontSize=8.5, leading=12),
        "name": ParagraphStyle(
            "name", parent=base, fontName="FspSans-Bold", fontSize=20, leading=24
        ),
        "category": ParagraphStyle(
            "category",
            parent=base,
            fontName="FspMono-Bold",
            fontSize=13,
            leading=17,
            textColor=BLUE,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base,
            fontName="FspMono-Bold",
            fontSize=10.5,
            leading=14,
            textColor=BLUE,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "cell": ParagraphStyle("cell", parent=base, fontSize=9, leading=12),
        "cell_right": ParagraphStyle(
            "cell_right", parent=base, fontSize=9, leading=12, alignment=TA_RIGHT
        ),
        "chip": ParagraphStyle("chip", parent=base, fontName="FspMono", fontSize=8.5, leading=11),
        "badge": ParagraphStyle("badge", parent=base, fontSize=9, leading=12),
    }


def esc(text: Any) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Bar(Flowable):  # type: ignore[misc]
    """Полоса результата 0..1."""

    def __init__(self, value: float, width: float = 52 * mm, height: float = 3.2 * mm) -> None:
        super().__init__()
        self.value = max(0.0, min(1.0, value))
        self.width, self.height = width, height

    def draw(self) -> None:
        c = self.canv
        c.setFillColor(LIGHT)
        c.roundRect(0, 0, self.width, self.height, self.height / 2, stroke=0, fill=1)
        if self.value > 0:
            c.setFillColor(BLUE)
            w = max(self.height, self.width * self.value)
            c.roundRect(0, 0, w, self.height, self.height / 2, stroke=0, fill=1)


class Rule(Flowable):  # type: ignore[misc]
    def __init__(self, width: float, color: colors.Color = GREY, thickness: float = 0.6) -> None:
        super().__init__()
        self.width, self.height = width, thickness + 2
        self.color, self.thickness = color, thickness

    def draw(self) -> None:
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 1, self.width, 1)


@dataclass
class ProfileData:
    candidate: dict[str, Any]
    achievements: list[dict[str, Any]]
    generated: date


def _fmt_date(value: Any) -> str:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, str) and len(value) >= 10:
        y, m, d = value[:10].split("-")
        return f"{d}.{m}.{y}"
    return ""


def _years(value: float | None) -> str:
    if value is None:
        return "—"
    v = float(value)
    if v == 0:
        return "без коммерческого опыта"
    whole = int(v)
    if v != whole:
        return f"{str(round(v, 1)).replace('.', ',')} года"
    if whole % 10 == 1 and whole % 100 != 11:
        return f"{whole} год"
    if whole % 10 in (2, 3, 4) and whole % 100 not in (12, 13, 14):
        return f"{whole} года"
    return f"{whole} лет"


def _on_page(canvas: Canvas, doc: Any, footer: str) -> None:
    w, h = A4
    canvas.saveState()
    # шапка: синяя линия + подпись платформы, красная точка — единственный акцент
    canvas.setStrokeColor(BLUE)
    canvas.setLineWidth(1.2)
    canvas.line(18 * mm, h - 14 * mm, w - 18 * mm, h - 14 * mm)
    canvas.setFillColor(RED)
    canvas.circle(18 * mm + 1.6 * mm, h - 10 * mm, 1.6 * mm, stroke=0, fill=1)
    canvas.setFillColor(BLUE)
    canvas.setFont("FspMono-Bold", 9)
    canvas.drawString(18 * mm + 5 * mm, h - 11.2 * mm, "ФСП · ПРОФИЛЬ IT-СПЕЦИАЛИСТА")
    canvas.setFont("FspMono", 8)
    canvas.drawRightString(w - 18 * mm, h - 11.2 * mm, "fsp-talent")
    # подвал
    canvas.setStrokeColor(GREY)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, 14 * mm, w - 18 * mm, 14 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("FspSans", 7.5)
    canvas.drawString(18 * mm, 9.5 * mm, footer)
    canvas.drawRightString(w - 18 * mm, 9.5 * mm, f"стр. {doc.page}")
    canvas.restoreState()


def build_profile_pdf(data: ProfileData) -> bytes:
    """Профиль → PDF (байты). Одна-две страницы A4."""
    st = styles()
    cand = data.candidate
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        # у рамки platypus внутренний отступ 6 pt: текст встаёт ровно под линию шапки (18 мм)
        leftMargin=18 * mm - FRAME_PAD,
        rightMargin=18 * mm - FRAME_PAD,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=f"Профиль: {cand.get('full_name') or 'кандидат'}",
        author="fsp-talent",
        subject="Стандартизированный профиль IT-специалиста",
    )
    width = doc.width - 2 * FRAME_PAD
    story: list[Flowable] = []

    # ---------- имя, категория, контакты
    story.append(Paragraph(esc(cand.get("full_name") or "Кандидат"), st["name"]))
    spec, grade = cand.get("specialization"), cand.get("grade")
    if grade and spec:
        cat = f"{SPEC_LABELS.get(spec, spec)} · {GRADE_LABELS.get(grade, grade)}"
        theta = cand.get("theta")
        extra = (
            f"  <font name='FspSans' size='9' color='#5B5C66'>θ = {_ru_num(theta)}</font>"
            if (theta is not None)
            else ""
        )
        story.append(Paragraph(f"{esc(cat)}{extra}", st["category"]))
        # дата пройденного теста, давшего грейд (не последней попытки: она могла быть
        # неудачной); нет даты — пишем без неё
        when = _fmt_date(cand.get("grade_confirmed_at"))
        story.append(
            Paragraph(
                "Категория и грейд подтверждены адаптивным тестом платформы"
                + (f" ({when})" if when else ""),
                st["muted"],
            )
        )
    else:
        story.append(Paragraph("Категория не присвоена — тест ещё не пройден", st["category"]))

    facts = []
    if cand.get("city"):
        facts.append(esc(cand["city"]))
    formats = [FORMAT_LABELS.get(f, f) for f in cand.get("work_formats") or []]
    if formats:
        facts.append("формат: " + ", ".join(formats))
    facts.append("опыт: " + _years(cand.get("experience_years")))
    contacts = [c for c in (cand.get("email"), cand.get("phone"), cand.get("telegram")) if c]
    links = [
        str(link.get("url", "")).replace("https://", "")
        for link in cand.get("links") or []
        if link.get("url")
    ]
    story.append(Spacer(1, 4))
    story.append(Paragraph(" · ".join(facts), st["base"]))
    if contacts or links:
        story.append(Paragraph(esc(" · ".join([*contacts, *links])), st["muted"]))
    story.append(Spacer(1, 6))
    story.append(Rule(width))

    # ---------- результаты теста по темам
    scores = cand.get("topic_scores") or []
    story.append(Paragraph("Результаты теста по темам", st["h2"]))
    if scores:
        rows = []
        for s in scores:
            value = float(s.get("score") or 0)
            level = LEVEL_LABELS.get(s.get("level", ""), s.get("level", ""))
            level_html = (
                f"<font color='#402FFF'>{esc(level)}</font>"
                if s.get("level") == "strong"
                else esc(level)
            )
            rows.append(
                [
                    Paragraph(esc(s.get("label") or s.get("topic")), st["cell"]),
                    Bar(value),
                    Paragraph(f"{round(value * 100)}%", st["cell_right"]),
                    Paragraph(level_html, st["cell"]),
                ]
            )
        table = Table(
            rows, colWidths=[width - 52 * mm - 16 * mm - 34 * mm, 54 * mm, 14 * mm, 34 * mm]
        )
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.4, LIGHT),
                    ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        story.append(table)
    else:
        story.append(Paragraph("Тест ещё не пройден — результатов по темам нет.", st["muted"]))

    # ---------- стек
    stack = [skill_label(code) for code in cand.get("stack") or []]
    story.append(Paragraph("Стек", st["h2"]))
    if stack:
        chips = "  ".join(f"<font backColor='#EDEDED'>&nbsp;{esc(s)}&nbsp;</font>" for s in stack)
        story.append(Paragraph(chips, ParagraphStyle("chips", parent=st["chip"], leading=15)))
    else:
        story.append(Paragraph("Не указан", st["muted"]))

    # ---------- опыт
    exp_block: list[Flowable] = [Paragraph("Опыт и роли", st["h2"])]
    exp_rows = [
        ["Стаж", _years(cand.get("experience_years"))],
        ["Роли в команде", ", ".join(cand.get("roles_in_team") or []) or "—"],
        ["Софт-скиллы", ", ".join(cand.get("soft_skills") or []) or "—"],
    ]
    exp_table = Table(
        [[Paragraph(k, st["muted"]), Paragraph(esc(v), st["cell"])] for k, v in exp_rows],
        colWidths=[34 * mm, width - 34 * mm],
    )
    exp_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    exp_block.append(exp_table)
    if cand.get("about"):
        exp_block += [Spacer(1, 4), Paragraph(esc(cand["about"]), st["base"])]
    story.append(KeepTogether(exp_block))

    # ---------- ФСП
    fsp_block: list[Flowable] = [Paragraph("Достижения ФСП", st["h2"])]
    fsp_tail: list[Flowable] = []
    if cand.get("fsp_id") and (data.achievements or cand.get("fsp_badges")):
        score = cand.get("fsp_score")
        head = f"ФСП ID {esc(cand['fsp_id'])}"
        if score is not None:
            head += f" · ФСП-скор {float(score):.0f} из 100"
        fsp_block.append(Paragraph(head, st["base"]))
        for b in cand.get("fsp_badges") or []:
            mark = (
                " <font color='#402FFF' name='FspSans-Bold' size='7.5'>✓ ПОДТВЕРЖДЕНО ФСП</font>"
                if b.get("verified")
                else ""
            )
            fsp_block.append(
                Paragraph(
                    f"<font color='#EC1D35'>●</font> {esc(b.get('title', ''))}{mark}", st["badge"]
                )
            )
        achs = sorted(data.achievements, key=lambda a: str(a.get("date", "")), reverse=True)[
            :MAX_ACHIEVEMENTS
        ]
        if achs:
            rows = []
            for a in achs:
                place = f"{a['place']} место" if a.get("place") else (a.get("diploma") or "участие")
                level = COMP_LEVEL_LABELS.get(a.get("level", ""), a.get("level", ""))
                discipline = DISCIPLINE_LABELS.get(a.get("discipline", ""), a.get("discipline", ""))
                what = (
                    f"{esc(a.get('competition', ''))}<br/><font color='#5B5C66' size='7.5'>"
                    f"{esc(level)} · {esc(discipline)}"
                    + (f" · {esc(a['role'])}" if a.get("role") else "")
                    + "</font>"
                )
                ok = (
                    "<br/><font color='#402FFF' size='7.5'>подтверждено ФСП</font>"
                    if a.get("verified")
                    else ""
                )
                rows.append(
                    [
                        Paragraph(_fmt_date(a.get("date")), st["cell"]),
                        Paragraph(what, st["cell"]),
                        Paragraph(esc(place) + ok, st["cell"]),
                    ]
                )
            t = Table(rows, colWidths=[22 * mm, width - 22 * mm - 34 * mm, 34 * mm])
            t.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LINEBELOW", (0, 0), (-1, -2), 0.4, LIGHT),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ]
                )
            )
            fsp_tail = [Spacer(1, 4), t]
            more = len(data.achievements) - len(achs)
            if more > 0:
                fsp_tail.append(Paragraph(f"…и ещё участий: {more}", st["muted"]))
    else:
        text = (
            "Нет данных ФСП: ФСП ID привязан, но участий в соревнованиях в реестре пока нет."
            if cand.get("fsp_id")
            else "Нет данных ФСП: профиль не привязан к ФСП ID."
        )
        fsp_block.append(Paragraph(text, st["muted"]))
    # заголовок и бейджи — вместе, таблица участий может перейти на следующую страницу
    story.append(KeepTogether(fsp_block))
    story += fsp_tail

    footer = (
        f"Сформировано {data.generated.strftime('%d.%m.%Y')} на платформе fsp-talent · "
        "«подтверждено ФСП» — данные реестра ФСП"
    )
    doc.build(
        story,
        onFirstPage=lambda c, d: _on_page(c, d, footer),
        onLaterPages=lambda c, d: _on_page(c, d, footer),
    )
    return buf.getvalue()


def _achievement_dict(a: Any) -> dict[str, Any]:
    return {
        "competition": a.competition,
        "discipline": a.discipline,
        "level": a.level,
        "date": a.date,
        "place": a.place,
        "diploma": a.diploma,
        "team": a.team,
        "role": a.role,
        "verified": a.verified,
    }


async def profile_pdf(session: AsyncSession, candidate_id: int, today: date | None = None) -> bytes:
    """Собрать данные кандидата из БД и сгенерировать PDF."""
    from starlette.concurrency import run_in_threadpool

    from app.candidates.service import CandidateProfileService
    from app.fsp.service import FspService

    cand = await CandidateProfileService(session).get_or_404(candidate_id)
    achievements = [
        _achievement_dict(a) for a in await FspService(session).achievements(candidate_id)
    ]
    data = ProfileData(cand, achievements, today or date.today())
    return await run_in_threadpool(build_profile_pdf, data)
