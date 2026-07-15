"""Authentification par credential agent pour l'ingest V1 (ADR-0004, contrat §8).

Le data plane agent (`/ingest/*`, `/agent/commands*`) ne s'authentifie **pas**
par le JWT utilisateur mais par un credential individuel hashé. Le serveur en
**dérive** l'agent et le tenant (jamais depuis un body) et refuse immédiatement
un credential révoqué/expiré. Fail-closed à chaque étape.

Header : `X-Agent-Credential: <key_prefix>.<secret>`. Le préfixe est un
identifiant de lookup public ; l'empreinte du secret complet est comparée en
temps constant à `agent_credentials.secret_hash`.
"""
import secrets
from dataclasses import dataclass

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core.db import get_db
from apps.api.core.security import hash_reset_token, split_agent_credential
from apps.api.integrations.errors import (
    CredentialInvalid,
    CredentialRevoked,
    PermissionDenied,
)
from apps.api.models import Agent, AgentCredential

AGENT_CREDENTIAL_HEADER = "X-Agent-Credential"


@dataclass(frozen=True)
class AgentCredentialContext:
    """Contexte dérivé d'un credential agent valide (résolu serveur, fail-closed).

    `agent` et `installation_id` viennent du credential, jamais d'un body : un
    producteur ne peut agir que pour son propre agent/tenant.
    """

    credential: AgentCredential
    agent: Agent
    installation_id: object | None  # uuid de l'installation (tenant) de l'agent
    scopes: frozenset[str]

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes


def resolve_agent_credential(
    x_agent_credential: str | None = Header(default=None, alias=AGENT_CREDENTIAL_HEADER),
    db: Session = Depends(get_db),
) -> AgentCredentialContext:
    """Résout et valide le credential agent de la requête (dépendance FastAPI).

    Ordre fail-closed : header présent → format valide → credential connu →
    empreinte concordante → non révoqué/expiré → agent chargé. Toute étape
    manquante lève une `HostIntegrationError` (traduite en enveloppe V1).
    """
    if not x_agent_credential:
        raise CredentialInvalid("credential agent absent")
    split = split_agent_credential(x_agent_credential)
    if split is None:
        raise CredentialInvalid("format de credential agent invalide")
    key_prefix, full_secret = split

    cred = db.scalar(select(AgentCredential).where(AgentCredential.key_prefix == key_prefix))
    if cred is None:
        raise CredentialInvalid("credential agent inconnu")
    # Comparaison en temps constant sur l'empreinte du secret complet.
    if not secrets.compare_digest(hash_reset_token(full_secret), cred.secret_hash):
        raise CredentialInvalid("credential agent invalide")
    # Révoqué OU expiré → refus immédiat, sans période de grâce.
    if not cred.is_usable():
        raise CredentialRevoked(f"credential agent {cred.status}")

    agent = db.get(Agent, cred.agent_id)
    if agent is None:
        # Incohérence : credential orphelin — refus fail-closed.
        raise CredentialInvalid("agent du credential introuvable")

    return AgentCredentialContext(
        credential=cred,
        agent=agent,
        installation_id=agent.installation_id,
        scopes=frozenset(cred.scopes or []),
    )


def require_scope(ctx: AgentCredentialContext, scope: str) -> None:
    """Refuse (fail-closed) si le scope requis n'est pas accordé au credential."""
    if not ctx.has_scope(scope):
        raise PermissionDenied(
            f"scope requis absent : {scope}", details={"required_scope": scope}
        )
