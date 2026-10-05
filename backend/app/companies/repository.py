"""Компании и рекрутеры. До волны 2 — фикстуры."""

from app.common import fixtures
from app.common.fixtures import Record


class CompanyRepository:
    def all(self) -> list[Record]:
        return fixtures.all_records("companies")

    def get(self, company_id: int) -> Record | None:
        return fixtures.by_id("companies", company_id)

    def recruiters(self, company_id: int) -> list[Record]:
        return fixtures.where("recruiters", company_id=company_id)

    def needs(self, company_id: int) -> list[Record]:
        return fixtures.where("needs", company_id=company_id)

    def invitations(self, company_id: int) -> list[Record]:
        return fixtures.where("invitations", company_id=company_id)

    def applications(self, company_id: int) -> list[Record]:
        return fixtures.where("applications", company_id=company_id)

    def reports(self, company_id: int) -> list[Record]:
        return fixtures.where("reports", company_id=company_id)
