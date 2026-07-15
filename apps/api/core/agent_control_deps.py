"""Dépendances FastAPI Agent Control V1 — résolution serveur du `HostContext`.

Construit le `HostContext` de chaque requête V1 à partir du JWT hôte
(`get_current_user`) et de l'adaptateur hôte sélectionné par configuration
(`MC_HOST_ADAPTER`, ADR-0001 — pas de `if embedded` dans le domaine). Fail-closed :
identité/tenant absent → `HostIntegrationError` propagée, traduite en enveloppe
d'erreur V1 par le handler global (`main.py`) — jamais d'accès par omission.

Le tenant n'est JAMAIS lu depuis un query/body : il est dérivé de l'identité
(ADR-0003). Les services V1 reçoivent ce `HostContext` en paramètre explicite.
"""
import uuid

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from apps.api.core.config import settings
from apps.api.core.db import get_db
from apps.api.integrations.db_adapter import DbHostAdapter
from apps.api.integrations.host_context import HostContext
from apps.api.models import User
from apps.api.routers.auth import get_current_user


def request_id_of(request: Request) -> str:
    """Identifiant de requête : en-tête `X-Request-Id` s'il existe, sinon généré."""
    return request.headers.get("x-request-id") or str(uuid.uuid4())


def _build_adapter(db: Session):
    """Sélectionne l'adaptateur hôte par configuration (`MC_HOST_ADAPTER`).

    `local` (défaut) = mode embarqué/autonome résolu contre le registre DB
    (`DbHostAdapter`). Un futur adaptateur `jwt` d'un hôte réel se brancherait
    ici sans toucher au domaine. Fail-closed : toute valeur autre que celles
    reconnues retombe sur `DbHostAdapter` (jamais un accès élargi par défaut).
    """
    # Un seul adaptateur concret est livré en P1. `MC_HOST_ADAPTER` est lu ici
    # pour préparer l'ajout d'un adaptateur `jwt` sans toucher au domaine.
    _ = settings.mc_host_adapter
    return DbHostAdapter(db)


def get_host_context(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HostContext:
    """Résout le `HostContext` complet de la requête, fail-closed.

    Une `HostIntegrationError` (identité/tenant absent) remonte telle quelle et
    est traduite en enveloppe d'erreur V1 + statut HTTP par le handler global.
    """
    adapter = _build_adapter(db)
    return adapter.build_context(user, request_id=request_id_of(request))
