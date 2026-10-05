"""Пользователи и согласия."""

from datetime import datetime
from typing import Any

from app.common.enums import ConsentType
from app.common.fixtures import Record
from app.users.repository import UserRepository


class UserService:
    def __init__(self, repo: UserRepository | None = None) -> None:
        self.repo = repo or UserRepository()

    def consents(self, user_id: int) -> list[Record]:
        return self.repo.consents(user_id)

    def update_consent(
        self, user_id: int, consent_type: ConsentType, granted: bool, version: str
    ) -> dict[str, Any]:
        """Заглушка: возвращает новое состояние согласия, не сохраняя его."""
        current = next((c for c in self.repo.consents(user_id) if c["type"] == consent_type), None)
        now = datetime.now().astimezone().isoformat()
        return {
            "id": current["id"] if current else 0,
            "user_id": user_id,
            "type": consent_type,
            "version": version,
            "granted": granted,
            "granted_at": now if granted else (current or {}).get("granted_at"),
            "revoked_at": None if granted else now,
        }
