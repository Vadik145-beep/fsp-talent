"""Регулярные задания и ответы. До волны 5b — фикстуры."""

from app.common import fixtures
from app.common.fixtures import Record


class TaskRepository:
    def tasks(self, company_id: int) -> list[Record]:
        return fixtures.where("regular_tasks", company_id=company_id)

    def task(self, task_id: int) -> Record | None:
        return fixtures.by_id("regular_tasks", task_id)

    def next_task_id(self) -> int:
        return max((int(t["id"]) for t in fixtures.load("regular_tasks")), default=0) + 1

    def submissions_by_candidate(self, candidate_id: int) -> list[Record]:
        return fixtures.where("task_submissions", candidate_id=candidate_id)

    def submissions_by_task(self, task_id: int) -> list[Record]:
        return fixtures.where("task_submissions", task_id=task_id)

    def submission(self, submission_id: int) -> Record | None:
        return fixtures.by_id("task_submissions", submission_id)

    def company(self, company_id: int) -> Record | None:
        return fixtures.by_id("companies", company_id)
