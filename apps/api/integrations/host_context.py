"""`HostContext` — contexte résolu côté serveur pour chaque requête V1.

Le contexte est construit par l'adaptateur hôte (jamais depuis un body client).
Il porte l'installation, le tenant, l'utilisateur, les capacités accordées, la
locale, le fuseau et l'identifiant de requête. Un service V1 reçoit ce contexte
en paramètre explicite et ne consulte jamais le JWT ni le RBAC hôte directement.
"""
from pydantic import BaseModel, ConfigDict, Field

from apps.api.integrations.capabilities import Capability


class InstallationRef(BaseModel):
    """Installation du module dans un tenant hôte (`mc_installations`)."""

    model_config = ConfigDict(frozen=True)

    id: str                      # uuid de l'installation (mode local : uuid stable "local")
    installation_key: str        # préfixe des clés d'agent `<installation_key>:<local_key>`
    external_tenant_id: str      # identifiant tenant côté plateforme hôte
    status: str = "active"       # active|suspended|archived


class TenantRef(BaseModel):
    """Tenant résolu côté serveur (`HostTenantPort`)."""

    model_config = ConfigDict(frozen=True)

    external_tenant_id: str
    name: str
    slug: str
    status: str = "active"
    feature_flags: dict = Field(default_factory=dict)


class UserRef(BaseModel):
    """Utilisateur résolu (`HostIdentityPort`). Aucun secret/mot de passe ici."""

    model_config = ConfigDict(frozen=True)

    external_user_id: str
    local_user_id: str | None = None  # renseigné en mode local (mapping User.id)
    email: str | None = None
    display_name: str | None = None
    status: str = "active"


class HostContext(BaseModel):
    """Contexte hôte immuable d'une requête V1 (résolu serveur, fail-closed)."""

    model_config = ConfigDict(frozen=True)

    request_id: str
    installation: InstallationRef
    tenant: TenantRef
    user: UserRef
    capabilities: frozenset[Capability]
    locale: str = "fr"           # fr|en|ar
    timezone: str = "UTC"        # IANA (ex. Asia/Dubai)

    def has(self, capability: Capability) -> bool:
        """Vrai si la capacité est accordée dans ce contexte."""
        return capability in self.capabilities
