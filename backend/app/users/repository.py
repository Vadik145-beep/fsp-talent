"""Пользователи и согласия. До волны 2 — фикстуры `users.json`, `consents.json`."""

from app.common import fixtures
from app.common.fixtures import Record


class UserRepository:
    def all(self) -> list[Record]:
        return fixtures.all_records("users")

    def get(self, user_id: int) -> Record | None:
        return fixtures.by_id("users", user_id)

    def consents(self, user_id: int) -> list[Record]:
        return fixtures.where("consents", user_id=user_id)
