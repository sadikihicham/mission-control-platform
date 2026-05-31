"""Router auth + dépendance get_current_user (Contract B). Owner : `auth` (M2)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core.db import get_db
from apps.api.core.roles import Role, has_at_least
from apps.api.core.security import (
    create_access_token,
    decode_token,
    verify_password,
)
from apps.api.models import User

router = APIRouter(tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    user = db.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "identifiants invalides")
    return TokenOut(access_token=create_access_token(user.id, user.role))


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token manquant")
    try:
        payload = decode_token(creds.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token invalide") from exc
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "utilisateur inconnu")
    return user


def require_role(minimum: Role):
    """Dépendance factory : exige un rôle >= `minimum`."""

    def _checker(user: User = Depends(get_current_user)) -> User:
        if not has_at_least(user.role, minimum):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"rôle insuffisant (requis: {minimum.value}, actuel: {user.role})",
            )
        return user

    return _checker


@router.get("/auth/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.get("/auth/users", response_model=list[MeOut])
def list_users(
    _: User = Depends(require_role(Role.admin)),
    db: Session = Depends(get_db),
) -> list[User]:
    """Liste des utilisateurs — réservé au rôle admin (démontre require_role)."""
    return list(db.scalars(select(User)).all())
