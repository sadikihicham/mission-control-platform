"""Sécurité — hachage de mot de passe + JWT (Contract B).

Hash posé par `db-core` ; JWT ajouté par `auth` (M2).
"""
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import jwt

from apps.api.core.config import settings

# bcrypt limite l'entrée à 72 octets.
_MAX = 72


def generate_reset_token() -> str:
    """Jeton brut de réinitialisation (URL-safe). Ne jamais persister tel quel."""
    return secrets.token_urlsafe(32)


def hash_reset_token(raw: str) -> str:
    """Empreinte SHA-256 (hex) du jeton brut — c'est elle qu'on stocke en base."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# Séparateur du secret de credential agent : `<key_prefix>.<random>`. Le préfixe
# (partie gauche) est un identifiant de lookup public, non secret ; le random
# (partie droite) est le vrai secret. Un point ne peut apparaître ni dans le
# préfixe (`ac_` + hex) ni dans un token_urlsafe → découpage sûr sur le 1er `.`.
AGENT_CREDENTIAL_SEP = "."


def generate_agent_credential() -> tuple[str, str, str]:
    """Génère un credential agent (ADR-0004) sans inventer de primitive crypto.

    Réutilise `generate_reset_token()` (aléa URL-safe) et `hash_reset_token()`
    (SHA-256) — mêmes primitives que l'enrôlement Contract D et les jetons de
    reset. Retourne `(key_prefix, secret, secret_hash)` où :

    - `key_prefix` : identifiant public de lookup (`ac_<8 hex>`), non secret ;
    - `secret` : le secret COMPLET `<key_prefix>.<random>`, **affiché une seule
      fois** (jamais persisté) ;
    - `secret_hash` : empreinte SHA-256 du secret complet, seule valeur stockée.
    """
    key_prefix = "ac_" + secrets.token_hex(4)
    secret = f"{key_prefix}{AGENT_CREDENTIAL_SEP}{generate_reset_token()}"
    return key_prefix, secret, hash_reset_token(secret)


def split_agent_credential(secret: str) -> tuple[str, str] | None:
    """Découpe un secret complet en `(key_prefix, secret)`. None si malformé."""
    prefix, sep, _ = secret.partition(AGENT_CREDENTIAL_SEP)
    if not sep or not prefix:
        return None
    return prefix, secret


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
