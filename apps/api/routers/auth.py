"""Router auth + dépendance get_current_user (Contract B). Owner : `auth` (M2)."""
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from apps.api.core.config import settings
from apps.api.core.db import get_db
from apps.api.core.ratelimit import check_and_increment
from apps.api.core.roles import Role, has_at_least
from apps.api.core.security import (
    create_access_token,
    decode_token,
    generate_reset_token,
    hash_password,
    hash_reset_token,
    verify_password,
)
from apps.api.models import PasswordResetToken, User

# Durée de vie d'un jeton de réinitialisation.
_RESET_TTL_MINUTES = 30

# Anti brute-force sur /auth/login — actif en prod uniquement (même garde que le
# seed démo / --reload, cf. infra/api-entrypoint.sh) : le harness de test appelle
# /auth/login des dizaines de fois via les fixtures admin_token/pm_token/viewer_token,
# ça casserait les tests si actif hors prod.
_LOGIN_RATE_LIMIT = 10
_LOGIN_RATE_WINDOW_SECONDS = 600


def _client_ip(request: Request) -> str:
    """IP à utiliser pour le rate-limit. Le peer TCP direct par défaut ;
    `X-Forwarded-For` n'est honoré que si ce peer est un proxy de confiance
    (`settings.trusted_proxies`), sinon n'importe quel client peut forger
    l'en-tête pour obtenir un nouveau compteur à chaque requête. Quand il est
    honoré, on prend le dernier maillon de la chaîne : c'est celui ajouté par
    notre proxy de confiance, tout ce qui précède peut avoir été forgé plus
    loin en amont."""
    peer = request.client.host if request.client else None
    if peer and peer in settings.trusted_proxies:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            hops = [h.strip() for h in forwarded.split(",") if h.strip()]
            if hops:
                return hops[-1]
    return peer or "unknown"

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
    full_name: str | None = None
    civility: str | None = None


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)) -> TokenOut:
    if settings.environment.lower().startswith("prod"):
        # Deux clés indépendantes : l'IP seule est contournable par rotation
        # (via un proxy de confiance légitime qui honore des IPs client
        # changeantes) ; l'email seul serait contournable si un attaquant visait
        # des comptes différents. Les deux ensemble bornent chaque axe.
        ip_ok = check_and_increment(
            f"ratelimit:login:ip:{_client_ip(request)}",
            limit=_LOGIN_RATE_LIMIT,
            window_seconds=_LOGIN_RATE_WINDOW_SECONDS,
        )
        email_ok = check_and_increment(
            f"ratelimit:login:email:{body.email.strip().lower()}",
            limit=_LOGIN_RATE_LIMIT,
            window_seconds=_LOGIN_RATE_WINDOW_SECONDS,
        )
        if not ip_ok or not email_ok:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS, "trop de tentatives, réessayez plus tard"
            )
    user = db.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "identifiants invalides")
    return TokenOut(access_token=create_access_token(user.id, user.role))


class ForgotPasswordIn(BaseModel):
    email: str


class ForgotPasswordOut(BaseModel):
    # Réponse volontairement générique : on ne révèle jamais si l'email existe.
    message: str = "Si un compte existe pour cet email, un lien de réinitialisation a été envoyé."
    # En dehors de la production (pas de SMTP), on renvoie le jeton pour la démo.
    dev_token: str | None = None


class ResetPasswordIn(BaseModel):
    token: str
    new_password: str = Field(min_length=6, max_length=128)


class MessageOut(BaseModel):
    message: str


@router.post("/auth/forgot-password", response_model=ForgotPasswordOut)
def forgot_password(body: ForgotPasswordIn, db: Session = Depends(get_db)) -> ForgotPasswordOut:
    """Initie une réinitialisation. Réponse identique que l'email existe ou non
    (anti-énumération). En dev, renvoie le jeton brut faute de SMTP configuré."""
    user = db.scalar(select(User).where(User.email == body.email))
    if not user:
        return ForgotPasswordOut()

    # Invalide les jetons précédents encore actifs pour cet utilisateur.
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=datetime.now(UTC))
    )

    raw = generate_reset_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_reset_token(raw),
            expires_at=datetime.now(UTC) + timedelta(minutes=_RESET_TTL_MINUTES),
        )
    )
    db.commit()

    # TODO(prod) : envoyer `raw` par email (lien). Hors prod on le renvoie tel quel.
    is_prod = settings.environment.lower().startswith("prod")
    return ForgotPasswordOut(dev_token=None if is_prod else raw)


@router.post("/auth/reset-password", response_model=MessageOut)
def reset_password(body: ResetPasswordIn, db: Session = Depends(get_db)) -> MessageOut:
    """Consomme un jeton valide (non utilisé, non expiré) et change le mot de passe."""
    row = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_reset_token(body.token)
        )
    )
    now = datetime.now(UTC)
    expires = row.expires_at if row else None
    # Comparaison robuste aux datetimes naïfs renvoyés par certains backends.
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if row is None or row.used_at is not None or expires is None or expires < now:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "jeton invalide ou expiré")

    user = db.get(User, row.user_id)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "jeton invalide ou expiré")

    user.hashed_password = hash_password(body.new_password)
    row.used_at = now
    db.commit()
    return MessageOut(message="Mot de passe réinitialisé. Vous pouvez vous connecter.")


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
