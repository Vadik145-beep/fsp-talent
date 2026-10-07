"""PDF-профиль в стиле ФСП (T3.3): кириллица, разделы, ФСП / «нет данных ФСП»."""

import io
from datetime import date

import pdfplumber
from fastapi.testclient import TestClient

from app.candidates.pdf import ProfileData, build_profile_pdf
from app.common import fixtures
from tests.conftest import CANDIDATE, CANDIDATE_NO_FSP, RECRUITER


def _text(content: bytes) -> tuple[str, int, set[str]]:
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        fonts = {c["fontname"].split("+")[-1] for p in pdf.pages for c in p.chars}
        return text, len(pdf.pages), fonts


def test_profile_pdf_with_fsp(client: TestClient) -> None:
    resp = client.get("/api/candidates/me/profile.pdf", headers=CANDIDATE)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "attachment" in resp.headers["content-disposition"]
    text, pages, fonts = _text(resp.content)
    cand = fixtures.by_id("candidates", 1)
    assert cand is not None
    assert cand["full_name"] in text  # кириллица извлекается — шрифт встроен корректно
    for part in ("Backend · Middle", "Результаты теста по темам", "HTTP и REST API", "Стек"):
        assert part in text, part
    assert "FastAPI" in text and "PostgreSQL" in text
    assert "Достижения ФСП" in text and "подтверждено ФСП" in text.replace("\n", " ")
    assert "FSP-000001" in text
    assert pages <= 2
    assert any("JetBrainsMono" in f for f in fonts) and any("DejaVuSans" in f for f in fonts)


def test_profile_pdf_without_fsp(client: TestClient) -> None:
    resp = client.get("/api/candidates/me/profile.pdf", headers=CANDIDATE_NO_FSP)
    assert resp.status_code == 200
    text, pages, _ = _text(resp.content)
    assert "Нет данных ФСП" in text
    section = text.split("Достижения ФСП")[-1].split("Сформировано")[0]
    assert "подтверждено ФСП" not in section
    assert pages == 1


def test_profile_pdf_only_for_candidate(client: TestClient) -> None:
    assert client.get("/api/candidates/me/profile.pdf", headers=RECRUITER).status_code == 403


def test_build_without_test_results_and_stack() -> None:
    cand = {
        "full_name": "Новый Кандидат",
        "specialization": None,
        "grade": None,
        "topic_scores": [],
        "stack": [],
        "experience_years": 0,
        "work_formats": ["remote"],
        "links": [],
        "fsp_id": None,
    }
    text, pages, _ = _text(build_profile_pdf(ProfileData(cand, [], date(2026, 10, 7))))
    assert "Категория не присвоена" in text
    assert "Тест ещё не пройден" in text
    assert "без коммерческого опыта" in text
    assert pages == 1
