"""Adaptateur hôte `local` — réutilise `User`, le JWT local et le RBAC existant.

En développement / mode autonome, la plateforme hôte n'est autre que Mission
Control lui-même : cet adaptateur mappe l'`User` local, son rôle et un tenant
implicite unique « local » vers un `HostContext`. Il est sélectionné par
configuration (`MC_HOST_ADAPTER=local`) et implémente les mêmes ports que
l'adaptateur `jwt` d'un hôte réel — aucun `if embedded` ne fuit dans le domaine.

Le multi-tenant réel étant reporté (colonne `company_id` retirée en migration
0007), le mode local expose un seul tenant `local`. Fail-closed conservé :
identité absente/inactive → `IdentityUnresolved` ; installation désactivée →
`TenantUnresolved` ; rôle inconnu → aucune capacité.
"""
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from apps.api.integrations.capabilities import Capability, capabilities_for_role
from apps.api.integrations.errors import IdentityUnresolved, TenantUnresolved
from apps.api.integrations.host_context import (
    HostContext,
    InstallationRef,
    TenantRef,
    UserRef,
)

# Identité stable de l'installation locale (déterministe, pas de ligne DB requise).
LOCAL_INSTALLATION_KEY = "local"
LOCAL_INSTALLATION_ID = str(uuid5(NAMESPACE_URL, "agent-control/installation/local"))


class _UserLike(Protocol):
    """Contrat minimal attendu d'un utilisateur hôte (duck-typing, sans DB)."""

    id: object
    email: str
    role: str
    is_active: bool


class LocalHostAdapter:
    """Adaptateur local de référence implémentant les cinq ports hôte.

    Instancié par requête ; `installation_active=False` simule une installation
    désactivée (utile pour les tests fail-closed « tenant absent »).
    """

    def __init__(self, *, installation_active: bool = True) -> None:
        self._installation_active = installation_active

    # --- HostIdentityPort -------------------------------------------------
    def resolve_identity(self, credential: _UserLike | None) -> UserRef:
        user = credential
        if user is None or not getattr(user, "is_active", False):
            raise IdentityUnresolved("utilisateur absent ou inactif")
        return UserRef(
            external_user_id=str(user.id),
            local_user_id=str(user.id),
            email=user.email,
            display_name=getattr(user, "full_name", None),
            status="active",
        )

    # --- HostTenantPort ---------------------------------------------------
    def resolve_tenant(
        self, user: UserRef, installation_key: str = LOCAL_INSTALLATION_KEY
    ) -> tuple[InstallationRef, TenantRef]:
        if not self._installation_active or installation_key != LOCAL_INSTALLATION_KEY:
            raise TenantUnresolved("aucune installation active pour cette clé")
        installation = InstallationRef(
            id=LOCAL_INSTALLATION_ID,
            installation_key=LOCAL_INSTALLATION_KEY,
            external_tenant_id=LOCAL_INSTALLATION_KEY,
            status="active",
        )
        tenant = TenantRef(
            external_tenant_id=LOCAL_INSTALLATION_KEY,
            name="Local",
            slug=LOCAL_INSTALLATION_KEY,
            status="active",
        )
        return installation, tenant

    def user_belongs_to_tenant(self, user: UserRef, tenant: TenantRef) -> bool:
        # En mode local, tout utilisateur résolu appartient au tenant unique.
        return tenant.external_tenant_id == LOCAL_INSTALLATION_KEY

    # --- HostPermissionPort ----------------------------------------------
    def capabilities_for(self, user: UserRef, tenant: TenantRef, role: str) -> frozenset[Capability]:
        # Le rôle vient du RBAC hôte local ; traduction unique en capacités.
        return capabilities_for_role(role)

    # --- Composition : construit le HostContext complet -------------------
    def build_context(
        self,
        credential: _UserLike | None,
        *,
        request_id: str,
        installation_key: str = LOCAL_INSTALLATION_KEY,
        locale: str = "fr",
        timezone: str = "UTC",
    ) -> HostContext:
        """Assemble un `HostContext` fail-closed depuis un `User` local.

        Ordre : identité → tenant → capacités. Toute étape manquante lève une
        `HostIntegrationError` (jamais d'accès par omission).
        """
        user_ref = self.resolve_identity(credential)
        installation, tenant = self.resolve_tenant(user_ref, installation_key)
        role = getattr(credential, "role", "") or ""
        capabilities = self.capabilities_for(user_ref, tenant, role)
        return HostContext(
            request_id=request_id,
            installation=installation,
            tenant=tenant,
            user=user_ref,
            capabilities=capabilities,
            locale=locale,
            timezone=timezone,
        )
