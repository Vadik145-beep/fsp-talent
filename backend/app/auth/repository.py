"""Учётные записи и токены. До волны 2 — фикстуры `users.json` и `demo_accounts.json`."""

from app.common import fixtures
from app.common.fixtures import Record


class AuthRepository:
    def user(self, user_id: int) -> Record | None:
        return fixtures.by_id("users", user_id)

    def user_by_email(self, email: str) -> Record | None:
        return next((u for u in fixtures.load("users") if u["email"] == email.lower()), None)

    def next_user_id(self) -> int:
        return max((int(u["id"]) for u in fixtures.load("users")), default=0) + 1

    def candidate(self, candidate_id: int) -> Record | None:
        return fixtures.by_id("candidates", candidate_id)

    def demo_accounts(self) -> list[Record]:
        return fixtures.all_records("demo_accounts")

    def demo_account(self, email: str) -> Record | None:
        return next(
            (a for a in fixtures.load("demo_accounts") if a["email"] == email.lower()), None
        )
