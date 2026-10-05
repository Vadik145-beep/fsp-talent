"""Хеширование паролей — общая точка для входа (auth) и загрузчика демо-данных (seed).

scrypt из стандартной библиотеки (рекомендация OWASP наряду с argon2id): соль на пароль,
параметры хранятся в самом хеше, поэтому их можно усилить без миграции старых хешей.
Формат: scrypt$<n>$<r>$<p>$<salt_b64>$<hash_b64>.
"""

import base64
import hashlib
import hmac
import secrets

_N, _R, _P, _DKLEN = 2**14, 8, 1, 32


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def hash_password(plain: str) -> str:
    """Хеш пароля для хранения в БД."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(plain.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(digest)}"


def verify_password(plain: str, stored: str) -> bool:
    """Проверка пароля; на любой испорченный хеш — False, без исключений."""
    try:
        scheme, n, r, p, salt_b64, hash_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(hash_b64)
        digest = hashlib.scrypt(
            plain.encode("utf-8"),
            salt=base64.b64decode(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest, expected)
