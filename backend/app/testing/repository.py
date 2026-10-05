"""Банк задач, сессии теста, история грейда. До волны 3a — фикстуры."""

from app.common import fixtures
from app.common.fixtures import Record


class TestingRepository:
    __test__ = False  # не тестовый класс для pytest

    def survey_questions(self) -> list[Record]:
        return fixtures.all_records("survey_questions")

    def items(self) -> list[Record]:
        return fixtures.all_records("items")

    def item(self, item_id: int) -> Record | None:
        return fixtures.by_id("items", item_id)

    def sessions(self, candidate_id: int) -> list[Record]:
        return fixtures.where("test_sessions", candidate_id=candidate_id)

    def session(self, session_id: int) -> Record | None:
        return fixtures.by_id("test_sessions", session_id)

    def next_session_id(self) -> int:
        return max((int(s["id"]) for s in fixtures.load("test_sessions")), default=0) + 1

    def grade_history(self, candidate_id: int) -> list[Record]:
        return fixtures.where("grade_history", candidate_id=candidate_id)

    def topics(self) -> list[Record]:
        return fixtures.all_records("topics")
