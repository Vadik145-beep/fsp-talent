"""Данные кабинета администратора. До волны 2/4c — фикстуры."""

from app.common import fixtures
from app.common.fixtures import Record


class AdminRepository:
    def users(self) -> list[Record]:
        return fixtures.all_records("users")

    def user(self, user_id: int) -> Record | None:
        return fixtures.by_id("users", user_id)

    def companies(self) -> list[Record]:
        return fixtures.all_records("companies")

    def company(self, company_id: int) -> Record | None:
        return fixtures.by_id("companies", company_id)

    def recruiters(self) -> list[Record]:
        return fixtures.all_records("recruiters")

    def invitations(self) -> list[Record]:
        return fixtures.all_records("invitations")

    def test_sessions(self) -> list[Record]:
        return fixtures.all_records("test_sessions")

    def items(self) -> list[Record]:
        return fixtures.all_records("items")

    def item(self, item_id: int) -> Record | None:
        return fixtures.by_id("items", item_id)

    def topics(self) -> list[Record]:
        return fixtures.all_records("topics")

    def reports(self) -> list[Record]:
        return fixtures.all_records("reports")

    def report(self, report_id: int) -> Record | None:
        return fixtures.by_id("reports", report_id)

    def audit(self) -> list[Record]:
        return fixtures.all_records("audit_log")

    def vacancy_tests(self) -> list[Record]:
        return fixtures.all_records("vacancy_tests")

    def skills(self) -> list[Record]:
        return fixtures.all_records("skills")

    def specialization(self, spec_id: str) -> Record | None:
        return fixtures.by_id("specializations", spec_id)

    def grade(self, grade_id: str) -> Record | None:
        return fixtures.by_id("grades", grade_id)

    def settings(self) -> Record:
        return dict(fixtures.by_id("platform_settings", "default") or {})
