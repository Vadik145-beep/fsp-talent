"""Регулярные задания: раздача, ответ, оценка 0–3. Заглушки до волны 5b."""

from datetime import datetime
from typing import Any

from app.candidates.service import CandidateService, to_card
from app.catalog.repository import CatalogRepository
from app.common.enums import SubmissionStatus, TaskStatus
from app.common.fixtures import Record
from app.core.errors import AppError, not_found
from app.tasks.repository import TaskRepository
from app.tasks.schemas import RegularTaskCreate, SubmissionAnswer, SubmissionGrade


def _now() -> str:
    return datetime.now().astimezone().isoformat()


class TaskService:
    def __init__(
        self,
        repo: TaskRepository | None = None,
        candidates: CandidateService | None = None,
        catalog: CatalogRepository | None = None,
    ) -> None:
        self.repo = repo or TaskRepository()
        self.candidates = candidates or CandidateService()
        self.catalog = catalog or CatalogRepository()

    def inbox(self, candidate_id: int) -> dict[str, Any]:
        cand = self.candidates.get_or_404(candidate_id)
        subs = sorted(
            self.repo.submissions_by_candidate(candidate_id),
            key=lambda s: s["assigned_at"],
            reverse=True,
        )
        active = next((s for s in subs if s["status"] == SubmissionStatus.assigned), None)
        history = [s for s in subs if s is not active]
        return {"active": active, "history": history, "freshness": cand["freshness"]}

    def answer(
        self, submission_id: int, candidate_id: int, body: SubmissionAnswer
    ) -> dict[str, Any]:
        sub = self.repo.submission(submission_id)
        if sub is None or sub["candidate_id"] != candidate_id:
            raise not_found("task_submission", submission_id)
        if sub["status"] != SubmissionStatus.assigned:
            raise AppError(
                409, "invalid_transition", "Ответ на это задание уже отправлен или срок истёк"
            )
        data = dict(sub)
        data.update(
            status=SubmissionStatus.submitted,
            answer_kind=body.answer_kind,
            answer_text=body.answer_text,
            submitted_at=_now(),
        )
        return data

    def list_tasks(self, company_id: int) -> list[Record]:
        return sorted(self.repo.tasks(company_id), key=lambda t: t["created_at"], reverse=True)

    def create_task(
        self, body: RegularTaskCreate, company_id: int, recruiter_id: int
    ) -> dict[str, Any]:
        cat = self.catalog.category(body.category)
        if cat is None:
            raise AppError(
                422, "unknown_category", "Неизвестная категория", {"category": body.category}
            )
        company = self.repo.company(company_id) or {}
        return {
            **body.model_dump(),
            "id": self.repo.next_task_id(),
            "company_id": company_id,
            "company_name": company.get("name", ""),
            "recruiter_id": recruiter_id,
            "category_label": cat["label"],
            "status": TaskStatus.active,
            "submissions_count": 0,
            "created_at": _now(),
        }

    def _with_card(self, sub: Record) -> dict[str, Any]:
        data = dict(sub)
        cand = self.candidates.repo.get(sub["candidate_id"])
        data["candidate"] = to_card(cand) if cand else None
        return data

    def task_submissions(self, task_id: int, company_id: int) -> list[dict[str, Any]]:
        task = self.repo.task(task_id)
        if task is None or task["company_id"] != company_id:
            raise not_found("regular_task", task_id)
        return [self._with_card(s) for s in self.repo.submissions_by_task(task_id)]

    def grade(self, submission_id: int, company_id: int, body: SubmissionGrade) -> dict[str, Any]:
        sub = self.repo.submission(submission_id)
        task = self.repo.task(sub["task_id"]) if sub else None
        if sub is None or task is None or task["company_id"] != company_id:
            raise not_found("task_submission", submission_id)
        if sub["status"] not in (SubmissionStatus.submitted, SubmissionStatus.graded):
            raise AppError(409, "invalid_transition", "Оценить можно только отправленный ответ")
        data = self._with_card(sub)
        data.update(
            status=SubmissionStatus.graded,
            score=body.score,
            grader_comment=body.comment,
            graded_at=_now(),
        )
        return data
