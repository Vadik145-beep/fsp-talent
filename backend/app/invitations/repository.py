"""Приглашения и их события. До волны 2 — фикстуры."""

from app.common import fixtures
from app.common.fixtures import Record


class InvitationRepository:
    def all(self) -> list[Record]:
        return fixtures.all_records("invitations")

    def get(self, invitation_id: int) -> Record | None:
        return fixtures.by_id("invitations", invitation_id)

    def events(self, invitation_id: int) -> list[Record]:
        return fixtures.where("invitation_events", invitation_id=invitation_id)

    def recruiter(self, recruiter_id: int) -> Record | None:
        return fixtures.by_id("recruiters", recruiter_id)

    def company(self, company_id: int) -> Record | None:
        return fixtures.by_id("companies", company_id)

    def next_id(self) -> int:
        return max((int(i["id"]) for i in fixtures.load("invitations")), default=0) + 1
