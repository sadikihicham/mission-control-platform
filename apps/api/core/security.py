"""Sécurité — hachage de mot de passe + JWT (Contract B).

Hash posé par `db-core` ; JWT ajouté par `auth` (M2).
"""
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import jwt

from apps.api.core.config import settings

# bcrypt limite l'entrée à 72 octets.
_MAX = 72


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")[:_MAX]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    pw = password.encode("utf-8")[:_MAX]
    try:
        return bcrypt.checkpw(pw, hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(sub: str, role: str, expires_minutes: int | None = None) -> str:
    exp = datetime.now(UTC) + timedelta(
        minutes=expires_minutes or settings.jwt_expire_minutes
    )
    payload = {"sub": str(sub), "role": role, "exp": exp}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Décode/valide un JWT. Lève jose.JWTError si invalide/expiré."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
