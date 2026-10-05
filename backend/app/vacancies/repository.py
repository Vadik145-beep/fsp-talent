"""Вакансии и отклики. До волны 5a — фикстуры."""

from app.common import fixtures
from app.common.fixtures import Record


class VacancyRepository:
    def all(self) -> list[Record]:
        return fixtures.all_records("vacancies")

    def get(self, vacancy_id: int) -> Record | None:
        return fixtures.by_id("vacancies", vacancy_id)

    def next_id(self) -> int:
        return max((int(v["id"]) for v in fixtures.load("vacancies")), default=0) + 1

    def applications(self) -> list[Record]:
        return fixtures.all_records("applications")

    def application(self, application_id: int) -> Record | None:
        return fixtures.by_id("applications", application_id)

    def next_application_id(self) -> int:
        return max((int(a["id"]) for a in fixtures.load("applications")), default=0) + 1

    def company(self, company_id: int) -> Record | None:
        return fixtures.by_id("companies", company_id)
