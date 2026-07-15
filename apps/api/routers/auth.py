"""Router auth + dépendance get_current_user (Contract B). Owner : `auth` (M2)."""
import socket
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


def _is_trusted_proxy(peer: str) -> bool:
    """`settings.trusted_proxies` accepte des IP littérales ou des noms résolvables par
    DNS (ex. `caddy`, le service Docker Compose de l'hôte SGI qui reverse-proxy ce
    service en prod co-hébergée — cf. docs/DEPLOY_FRONTED.md). Résolu à CHAQUE appel,
    jamais mis en cache : ce Caddy est recréé indépendamment de ag-api
    (`--force-recreate`, même doc §5) lors des changements de Caddyfile, ce qui peut lui
    réattribuer une IP différente sur le réseau externe partagé `caddy_net` — une IP
    figée casserait silencieusement la confiance au prochain redéploiement de Caddy."""
    for entry in settings.trusted_proxies:
        if entry == peer:
            return True
        try:
            if socket.gethostbyname(entry) == peer:
                return True
        except OSError:
            continue
    return False


def _client_ip(request: Request) -> str:
    """IP à utiliser pour le rate-limit. Le peer TCP direct par défaut ;
    `X-Forwarded-For` n'est honoré que si ce peer est un proxy de confiance
    (`settings.trusted_proxies`), sinon n'importe quel client peut forger
    l'en-tête pour obtenir un nouveau compteur à chaque requête. Quand il est
    honoré, on prend le dernier maillon de la chaîne : c'est celui ajouté par
    notre proxy de confiance, tout ce qui précède peut avoir été forgé plus
    loin en amont."""
    peer = request.client.host if request.client else None
    if peer and _is_trusted_proxy(peer):
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
    is_active: bool = True


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
    # Même message que "mot de passe faux" — ne pas révéler qu'un compte désactivé existe.
    if not user or not verify_password(body.password, user.hashed_password) or not user.is_active:
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


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=128)


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
    # Un JWT existant reste valide jusqu'à expiration ; on coupe quand même l'accès
    # dès la requête suivante si le compte a été désactivé entre-temps.
    if not user or not user.is_active:
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


@router.post("/auth/change-password", response_model=MessageOut)
def change_password(
    body: ChangePasswordIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageOut:
    """Self-service : l'utilisateur connecté change SON PROPRE mot de passe."""
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "mot de passe actuel incorrect")
    user.hashed_password = hash_password(body.new_password)
    db.commit()
    return MessageOut(message="Mot de passe modifié.")


@router.get("/auth/users", response_model=list[MeOut])
def list_users(
    _: User = Depends(require_role(Role.admin)),
    db: Session = Depends(get_db),
) -> list[User]:
    """Liste des utilisateurs — réservé au rôle admin (démontre require_role)."""
    return list(db.scalars(select(User)).all())


class UserCreateIn(BaseModel):
    email: str
    password: str = Field(min_length=6, max_length=128)
    role: Role = Role.viewer
    full_name: str | None = None
    civility: str | None = None


class UserUpdateIn(BaseModel):
    role: Role | None = None
    full_name: str | None = None
    civility: str | None = None
    is_active: bool | None = None


@router.post("/auth/users", response_model=MeOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreateIn,
    _: User = Depends(require_role(Role.admin)),
    db: Session = Depends(get_db),
) -> User:
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "email déjà utilisé")
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role.value,
        full_name=body.full_name,
        civility=body.civility,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/auth/users/{user_id}", response_model=MeOut)
def update_user(
    user_id: uuid.UUID,
    body: UserUpdateIn,
    admin: User = Depends(require_role(Role.admin)),
    db: Session = Depends(get_db),
) -> User:
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "utilisateur introuvable")
    # Anti-auto-lockout : un admin ne peut pas se désactiver ni se rétrograder
    # lui-même — avec un seul admin réel aujourd'hui, l'erreur serait irréversible
    # sans accès DB direct.
    demoting_self = target.id == admin.id and body.role is not None and body.role != Role.admin
    deactivating_self = target.id == admin.id and body.is_active is False
    if demoting_self or deactivating_self:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "impossible de se rétrograder ou se désactiver soi-même"
        )
    if body.role is not None:
        target.role = body.role.value
    if body.full_name is not None:
        target.full_name = body.full_name
    if body.civility is not None:
        target.civility = body.civility
    if body.is_active is not None:
        target.is_active = body.is_active
    db.commit()
    db.refresh(target)
    return target
