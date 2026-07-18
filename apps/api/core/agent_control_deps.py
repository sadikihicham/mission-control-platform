"""Dépendances FastAPI Agent Control V1 — résolution serveur du `HostContext`.

Construit le `HostContext` de chaque requête V1 à partir du credential hôte et
de l'adaptateur hôte sélectionné par configuration (`MC_HOST_ADAPTER`, ADR-0001
— pas de `if embedded` dans le domaine). Fail-closed : identité/tenant absent →
`HostIntegrationError` propagée, traduite en enveloppe d'erreur V1 par le
handler global (`main.py`) — jamais d'accès par omission.

Le tenant n'est JAMAIS lu depuis un query/body : il est dérivé de l'identité
(ADR-0003). Les services V1 reçoivent ce `HostContext` en paramètre explicite.

Deux adaptateurs = deux façons d'obtenir ce credential (ADR-0010) : en mode
`local` (défaut) c'est l'`User` V0 de ce service, via son propre JWT
(`get_current_user`) ; en mode `jwt` (hôte réel, ex. SGI) c'est le jeton brut
de l'hôte, jamais décodé avec le JWT/les utilisateurs V0 de ce service. D'où la
résolution du credential faite ici, pas déclarée en paramètre `Depends` fixe.
"""
import uuid

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from apps.api.core.config import settings
from apps.api.core.db import get_db
from apps.api.integrations.db_adapter import DbHostAdapter
from apps.api.integrations.errors import IdentityUnresolved
from apps.api.integrations.host_context import HostContext
from apps.api.integrations.jwt_adapter import JwtHostAdapter
from apps.api.routers.auth import _bearer, get_current_user


def request_id_of(request: Request) -> str:
    """Identifiant de requête : en-tête `X-Request-Id` s'il existe, sinon généré."""
    return request.headers.get("x-request-id") or str(uuid.uuid4())


def _build_adapter(db: Session):
    """Sélectionne l'adaptateur hôte par configuration (`MC_HOST_ADAPTER`).

    `local` (défaut) = mode embarqué/autonome résolu contre le registre DB
    (`DbHostAdapter`). `jwt` = hôte réel (ADR-0010) dont le JWT est validé
    directement. Fail-closed : toute valeur non reconnue retombe sur
    `DbHostAdapter` (jamais un accès élargi par défaut).
    """
    if settings.mc_host_adapter == "jwt":
        return JwtHostAdapter(db)
    return DbHostAdapter(db)


async def _resolve_credential(request: Request, db: Session) -> object:
    """Obtient le credential attendu par l'adaptateur actif.

    Mode `jwt` : le jeton brut de l'hôte (en-tête `Authorization: Bearer`),
    jamais décodé avec le JWT V0 de ce service. Mode `local` (défaut) :
    inchangé, l'`User` V0 résolu par `get_current_user` (même `HTTPBearer`
    `_bearer`, même erreurs qu'avant l'ajout de l'adaptateur `jwt`).
    """
    if settings.mc_host_adapter == "jwt":
        creds = await _bearer(request)
        if creds is None:
            raise IdentityUnresolved("jeton hôte manquant")
        return creds.credentials
    creds = await _bearer(request)
    return get_current_user(creds=creds, db=db)


async def get_host_context(
    request: Request,
    db: Session = Depends(get_db),
) -> HostContext:
    """Résout le `HostContext` complet de la requête, fail-closed.

    Une `HostIntegrationError` (identité/tenant absent) remonte telle quelle et
    est traduite en enveloppe d'erreur V1 + statut HTTP par le handler global.
    """
    adapter = _build_adapter(db)
    credential = await _resolve_credential(request, db)
    return adapter.build_context(credential, request_id=request_id_of(request))
