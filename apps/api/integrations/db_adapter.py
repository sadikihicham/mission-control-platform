"""Adaptateur hôte DB-backed — résout le tenant depuis le registre réel.

`DbHostAdapter` implémente les mêmes ports que `LocalHostAdapter` (mêmes
signatures, même `build_context`), mais résout l'installation/tenant contre les
tables `mc_installations` / `mc_user_mappings` au lieu d'un tenant `local` codé
en dur. C'est le point d'extension prévu par le contrat V1 (ADR-0003) : le tenant
est **résolu serveur** depuis l'identité, jamais depuis un body/query client.

Isolation : un utilisateur ne résout QUE l'installation à laquelle il est
rattaché via un mapping actif. Aucune fuite possible d'un tenant vers un autre —
un utilisateur sans mapping actif lève `TenantUnresolved` (fail-closed →
`tenant_required` 403). `LocalHostAdapter` reste inchangé pour les tests purs et
le mode autonome sans DB.
"""
import uuid
from typing import Protocol

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from apps.api.integrations.capabilities import Capability, capabilities_for_role
from apps.api.integrations.errors import IdentityUnresolved, TenantUnresolved
from apps.api.integrations.host_context import (
    HostContext,
    InstallationRef,
    TenantRef,
    UserRef,
)
from apps.api.models import MCInstallation, MCUserMapping


class _UserLike(Protocol):
    """Contrat minimal attendu d'un utilisateur hôte (duck-typing)."""

    id: object
    email: str
    role: str
    is_active: bool


def _as_uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        return None


class DbHostAdapter:
    """Adaptateur hôte résolvant identité/tenant/capacités contre la base.

    Instancié par requête avec la session de la requête. Fail-closed à chaque
    étape : identité absente/inactive → `IdentityUnresolved` ; aucun mapping/
    installation active → `TenantUnresolved` ; rôle inconnu → aucune capacité.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

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
        self, user: UserRef, installation_key: str | None = None
    ) -> tuple[InstallationRef, TenantRef]:
        """Retourne (installation, tenant) de l'installation ACTIVE à laquelle
        l'utilisateur est rattaché par un mapping actif. Fail-closed sinon.

        La résolution passe par le mapping utilisateur : c'est le point unique
        d'isolation — un utilisateur ne peut jamais résoudre l'installation d'un
        autre tenant.
        """
        stmt = (
            select(MCInstallation)
            .join(MCUserMapping, MCUserMapping.installation_id == MCInstallation.id)
            .where(
                MCUserMapping.status == "active",
                MCInstallation.status == "active",
                or_(
                    MCUserMapping.local_user_id == _as_uuid(user.local_user_id),
                    MCUserMapping.external_user_id == user.external_user_id,
                ),
            )
            .order_by(MCInstallation.created_at)
        )
        if installation_key:
            stmt = stmt.where(MCInstallation.installation_key == installation_key)
        inst = self._db.scalars(stmt).first()
        if inst is None:
            raise TenantUnresolved("aucune installation active pour cet utilisateur")
        installation = InstallationRef(
            id=str(inst.id),
            installation_key=inst.installation_key,
            external_tenant_id=inst.external_tenant_id,
            status=inst.status,
        )
        tenant = TenantRef(
            external_tenant_id=inst.external_tenant_id,
            name=inst.installation_key,
            slug=inst.installation_key,
            status=inst.status,
            feature_flags=inst.feature_flags or {},
        )
        return installation, tenant

    def user_belongs_to_tenant(self, user: UserRef, tenant: TenantRef) -> bool:
        row = self._db.scalars(
            select(MCUserMapping.id)
            .join(MCInstallation, MCUserMapping.installation_id == MCInstallation.id)
            .where(
                MCInstallation.external_tenant_id == tenant.external_tenant_id,
                MCInstallation.status == "active",
                MCUserMapping.status == "active",
                or_(
                    MCUserMapping.local_user_id == _as_uuid(user.local_user_id),
                    MCUserMapping.external_user_id == user.external_user_id,
                ),
            )
            .limit(1)
        ).first()
        return row is not None

    # --- HostPermissionPort ----------------------------------------------
    def capabilities_for(
        self, user: UserRef, tenant: TenantRef, role: str
    ) -> frozenset[Capability]:
        return capabilities_for_role(role)

    # --- Composition : construit le HostContext complet -------------------
    def build_context(
        self,
        credential: _UserLike | None,
        *,
        request_id: str,
        installation_key: str | None = None,
        locale: str = "fr",
        timezone: str = "UTC",
    ) -> HostContext:
        """Assemble un `HostContext` fail-closed depuis l'`User` et le registre.

        Ordre : identité → tenant (via mapping) → capacités. Toute étape
        manquante lève une `HostIntegrationError` (jamais d'accès par omission).
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
