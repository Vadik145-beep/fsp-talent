"""Одноразовые и refresh-токены: случайная строка у пользователя, sha256 — в БД.

Поиск идёт по хешу (уникальный индекс), поэтому время ответа БД не зависит от того,
насколько присланный токен «похож» на настоящий; найденный хеш дополнительно сверяем
`hmac.compare_digest` — сравнение за постоянное время.
"""

import hashlib
import hmac
import secrets


def new_token() -> str:
    """256 бит случайности, URL-safe (для ссылок в письмах и cookie)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def same_hash(stored: str, token: str) -> bool:
    return hmac.compare_digest(stored, hash_token(token))
