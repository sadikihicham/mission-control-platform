"""Adaptateur hôte `jwt` — valide directement le JWT d'un hôte réel (ADR-0010).

Contrairement à `DbHostAdapter` (identité résolue via l'`User`/JWT propres à ce
service), ici la requête porte le JWT de la plateforme hôte elle-même (ex. SGI) :
`resolve_identity` reçoit le jeton brut, pas un objet `User` local. Le tenant
(`company_id` de l'hôte) est un claim du jeton, pas une résolution via
`mc_user_mappings` — un JWT hôte valide pour un `company_id` prouve à lui seul
l'appartenance à ce tenant (ADR-0003 : jamais accepté d'un body/query, ici il
vient d'un jeton signé par l'hôte).

Fail-closed à chaque étape, comme `DbHostAdapter` : jeton absent/invalide/expiré
→ `IdentityUnresolved` ; aucune installation active pour ce `company_id` →
`TenantUnresolved` ; rôle hôte non mappé → aucune capacité.
"""
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core.config import settings
from apps.api.integrations.capabilities import Capability, capabilities_for_role
from apps.api.integrations.errors import IdentityUnresolved, TenantUnresolved
from apps.api.integrations.host_context import (
    HostContext,
    InstallationRef,
    TenantRef,
    UserRef,
)
from apps.api.models import MCInstallation

# Traduction rôle hôte (SGI) → rôle Mission Control, pour réutiliser le même
# barème de capacités que l'adaptateur local (décision ADR-0010 §3 : mapping
# grossier par rôle en V1, pas de nouvelle clé de permission côté SGI). Un rôle
# SGI absent d'ici (personas portail owner/tenant/client/technician comprises)
# tombe sur `frozenset()` via `capabilities_for_role` — fail-closed par défaut,
# pas une omission.
_SGI_ROLE_TO_MC_ROLE: dict[str, str] = {
    "agent": "developer",
    "manager": "pm",
    "admin": "admin",
}


class JwtHostAdapter:
    """Adaptateur hôte résolvant identité/tenant/capacités depuis un JWT hôte.

    Instancié par requête avec la session de la requête (pour le lookup
    `mc_installations`, seule donnée encore résolue localement). `credential`
    est le jeton brut (`str`), pas un `User` — ce service ne connaît jamais le
    JWT ni les utilisateurs de l'hôte au-delà de ce que le jeton affirme.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._claims: dict | None = None

    # --- HostIdentityPort -------------------------------------------------
    def resolve_identity(self, credential: str | None) -> UserRef:
        if not credential:
            raise IdentityUnresolved("jeton hôte manquant")
        try:
            claims = jwt.decode(
                credential,
                settings.sgi_jwt_secret,
                algorithms=[settings.sgi_jwt_algorithm],
                options={"require_exp": True},
            )
        except JWTError as exc:
            raise IdentityUnresolved("jeton hôte invalide, expiré ou sans expiration") from exc
        user_id = claims.get("sub")
        if not user_id:
            raise IdentityUnresolved("jeton hôte sans sujet (sub)")
        self._claims = claims
        # L'hôte (SGI) ne porte ni email ni nom affiché dans son JWT (ADR-0010
        # §1) : `None` ici tant que l'endpoint `/me` promis côté SGI n'existe
        # pas, pas une valeur par défaut arbitraire.
        return UserRef(
            external_user_id=str(user_id),
            local_user_id=None,
            email=None,
            display_name=None,
            status="active",
        )

    # --- HostTenantPort ---------------------------------------------------
    def resolve_tenant(
        self, user: UserRef, installation_key: str | None = None
    ) -> tuple[InstallationRef, TenantRef]:
        company_id = (self._claims or {}).get("company_id")
        if not company_id:
            raise TenantUnresolved("company_id absent du jeton hôte")
        stmt = select(MCInstallation).where(
            MCInstallation.external_tenant_id == str(company_id),
            MCInstallation.status == "active",
        )
        if installation_key:
            stmt = stmt.where(MCInstallation.installation_key == installation_key)
        inst = self._db.scalars(stmt).first()
        if inst is None:
            raise TenantUnresolved("aucune installation active pour ce tenant hôte")
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
        return (
            self._claims is not None
            and str(self._claims.get("company_id")) == tenant.external_tenant_id
        )

    # --- HostPermissionPort ------------------------------------------------
    def capabilities_for(
        self, user: UserRef, tenant: TenantRef, role: str
    ) -> frozenset[Capability]:
        return capabilities_for_role(_SGI_ROLE_TO_MC_ROLE.get(role, ""))

    # --- Composition : construit le HostContext complet --------------------
    def build_context(
        self,
        credential: str | None,
        *,
        request_id: str,
        installation_key: str | None = None,
        locale: str = "fr",
        timezone: str = "UTC",
    ) -> HostContext:
        user_ref = self.resolve_identity(credential)
        installation, tenant = self.resolve_tenant(user_ref, installation_key)
        role_claim = (self._claims or {}).get("role")
        # Un claim `role` non-string (liste/objet) ne doit jamais faire planter
        # la résolution en 500 : fail-closed vers aucune capacité, pas une erreur.
        role = role_claim if isinstance(role_claim, str) else ""
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
