"""Доступ к профилям кандидатов. До волны 2 — фикстуры `data/seed/candidates.json`."""

from app.common import fixtures
from app.common.fixtures import Record


class CandidateRepository:
    def all(self) -> list[Record]:
        return fixtures.all_records("candidates")

    def get(self, candidate_id: int) -> Record | None:
        return fixtures.by_id("candidates", candidate_id)

    def test_sessions(self, candidate_id: int) -> list[Record]:
        return fixtures.where("test_sessions", candidate_id=candidate_id)

    def invitations(self, candidate_id: int) -> list[Record]:
        return fixtures.where("invitations", candidate_id=candidate_id)

    def applications(self, candidate_id: int) -> list[Record]:
        return fixtures.where("applications", candidate_id=candidate_id)

    def submissions(self, candidate_id: int) -> list[Record]:
        return fixtures.where("task_submissions", candidate_id=candidate_id)
