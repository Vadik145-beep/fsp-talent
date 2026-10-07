"""Разбор PDF-резюме (T3.2): точность по полям на 5 образцах и загрузка через API."""

import io
import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.candidates.resume import (
    ResumeParseResponse,
    parse_resume_pdf,
    parse_resume_text,
    periods_months,
)
from app.nlp.validation import SAMPLES, resume_rows, resume_summary
from app.seed.testkit import sql_sync
from tests.conftest import CANDIDATE, RECRUITER

RESUMES = sorted((SAMPLES / "resumes").glob("*.pdf"))


@pytest.fixture(scope="module")
def summary() -> dict[str, float]:
    return resume_summary(resume_rows())


def test_exact_fields_on_samples(summary: dict[str, float]) -> None:
    for name in ("full_name", "email", "phone", "city", "specialization", "grade"):
        assert summary[name] >= 0.8, name
    assert summary["email"] == 1.0 and summary["phone"] == 1.0
    assert summary["experience_years"] >= 0.8
    assert summary["work_format"] >= 0.8


def test_stack_roles_soft_on_samples(summary: dict[str, float]) -> None:
    assert summary["stack_precision"] >= 0.85 and summary["stack_recall"] >= 0.85
    assert summary["roles_recall"] >= 0.7 and summary["roles_precision"] >= 0.7
    assert summary["soft_skills_recall"] >= 0.7 and summary["soft_skills_precision"] >= 0.7


def test_two_column_resume_is_split() -> None:
    two_col = next(p for p in RESUMES if p.name.startswith("02_"))
    r = parse_resume_pdf(two_col.read_bytes(), date(2026, 10, 1))
    assert r.two_column_pages == [1]
    assert r.value("full_name") == "Колесникова Анна Сергеевна"
    assert r.value("stack")[:3] == ["typescript", "javascript", "react"]
    one_col = next(p for p in RESUMES if p.name.startswith("01_"))
    assert parse_resume_pdf(one_col.read_bytes()).two_column_pages == []


def test_broken_pdf_gives_warning_not_error() -> None:
    r = parse_resume_pdf(b"%PDF-1.4 broken")
    assert r.warnings and r.value("email") is None
    assert r.fields["email"]["confidence"] == 0.0


def test_periods_and_text_rules() -> None:
    text = "Апрель 2021 — Март 2023\n04.2023 — н.в.\n2019 — 2020"
    # 24 мес + (04.2023…10.2026 = 42 мес) + (2019…2020 = 24 мес)
    assert periods_months(text, date(2026, 10, 1)) == 24 + 42 + 24
    r = parse_resume_text(
        "Сидоров Пётр\nJunior Java-разработчик · Пермь\n8 (912) 000-11-22 · p@example.com\n"
        "Навыки: Java, Spring Boot, постгрес, Git\nОпыт работы — 1 год 6 месяцев",
        date(2026, 10, 1),
    )
    assert r.value("full_name") == "Сидоров Пётр"
    assert r.value("phone") == "+79120001122"
    assert r.value("city") == "Пермь"
    assert r.value("grade") == "junior"
    assert r.value("stack") == ["java", "spring", "postgresql"]
    assert r.unmatched_skills == ["Git"]
    assert r.value("experience_years") == 1.5


def test_work_format_and_links_with_scheme() -> None:
    """Образец 01: «готов к гибридному формату» → hybrid; ссылка без схемы → с https://."""
    one = next(p for p in RESUMES if p.name.startswith("01_"))
    r = parse_resume_pdf(one.read_bytes(), date(2026, 10, 1))
    assert r.value("work_formats") == ["hybrid"]
    assert r.value("links") == ["https://github.com/denis-morozov-dev"]
    for path in RESUMES:
        exp = json.loads(path.with_name(path.stem + ".expected.json").read_text(encoding="utf-8"))
        got = parse_resume_pdf(path.read_bytes(), date(2026, 10, 1))
        links = got.value("links") or []
        assert all(url.startswith("https://") for url in links), path.name
        assert sorted(links) == sorted(f"https://{u}" for u in exp["links"].values()), path.name
        if exp["work_format"]:
            assert exp["work_format"] in got.value("work_formats"), path.name
    text = parse_resume_text(
        "Иванов Иван\nhttps://www.github.com/ivanov · github.com/ivanov · t.me/ivanov_dev"
    )
    assert text.value("links") == ["https://github.com/ivanov", "https://t.me/ivanov_dev"]


@pytest.mark.parametrize("path", RESUMES, ids=lambda p: p.name)
def test_upload_each_sample(client: TestClient, path: Path) -> None:
    expected = json.loads(path.with_name(path.stem + ".expected.json").read_text(encoding="utf-8"))
    resp = client.post(
        "/api/candidates/me/resume",
        files={"file": (path.name, path.read_bytes(), "application/pdf")},
        headers=CANDIDATE,
    )
    assert resp.status_code == 200, resp.text
    body = ResumeParseResponse.model_validate(resp.json())
    assert body.parser == "rules" and body.filename == path.name
    assert body.fields["email"].value == expected["email"]
    assert body.fields["phone"].value == expected["phone"]
    assert 0 < body.fields["email"].confidence <= 1
    stored = sql_sync(
        "SELECT candidate_id, parser FROM resumes WHERE id = :id", {"id": body.resume_id}
    )
    assert stored and stored[0][0] == 1


def test_upload_rejects_wrong_type_and_size(client: TestClient) -> None:
    text = client.post(
        "/api/candidates/me/resume",
        files={"file": ("cv.txt", b"hello", "text/plain")},
        headers=CANDIDATE,
    )
    assert text.status_code == 415 and text.json()["code"] == "unsupported_file"
    fake = client.post(
        "/api/candidates/me/resume",
        files={"file": ("cv.pdf", b"not a pdf at all", "application/pdf")},
        headers=CANDIDATE,
    )
    assert fake.status_code == 415
    big = client.post(
        "/api/candidates/me/resume",
        files={
            "file": ("cv.pdf", io.BytesIO(b"%PDF" + b"0" * (5 * 1024 * 1024)), "application/pdf")
        },
        headers=CANDIDATE,
    )
    assert big.status_code == 413 and big.json()["code"] == "file_too_large"
    assert (
        client.post(
            "/api/candidates/me/resume",
            files={"file": ("cv.pdf", b"%PDF-1.4", "application/pdf")},
            headers=RECRUITER,
        ).status_code
        == 403
    )
