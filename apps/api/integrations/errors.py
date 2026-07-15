"""Exceptions d'intégration hôte — fail-closed.

Ces exceptions sont levées par les adaptateurs et le domaine V1 quand l'identité,
le tenant ou une capacité manque. Elles portent un code machine stable
(`ErrorCode`) que la couche HTTP (SP3) traduit en enveloppe d'erreur V1 +
statut HTTP. Le défaut est toujours de refuser : jamais d'accès par omission.
"""
from apps.api.integrations.envelopes import ErrorCode


class HostIntegrationError(Exception):
    """Base des erreurs d'intégration hôte. Porte un code machine stable."""

    code: ErrorCode = ErrorCode.internal_error
    http_status: int = 500

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class IdentityUnresolved(HostIntegrationError):
    """Aucune identité valide n'a pu être dérivée du credential/JWT hôte."""

    code = ErrorCode.unauthenticated
    http_status = 401


class TenantUnresolved(HostIntegrationError):
    """Aucun tenant/installation actif n'a pu être résolu côté serveur."""

    code = ErrorCode.tenant_required
    http_status = 403


class UserNotInTenant(HostIntegrationError):
    """L'utilisateur résolu n'appartient pas au tenant demandé (fail-closed)."""

    code = ErrorCode.tenant_forbidden
    http_status = 403


class PermissionDenied(HostIntegrationError):
    """La capacité requise est absente de l'ensemble accordé à l'utilisateur."""

    code = ErrorCode.permission_denied
    http_status = 403


class CredentialInvalid(HostIntegrationError):
    """Credential agent absent, malformé ou empreinte non concordante (fail-closed)."""

    code = ErrorCode.credential_invalid
    http_status = 401


class CredentialRevoked(HostIntegrationError):
    """Credential agent révoqué ou expiré — refusé immédiatement, sans grâce."""

    code = ErrorCode.credential_revoked
    http_status = 403


class ValidationFailed(HostIntegrationError):
    """Corps/paramètres V1 invalides (ex. batch d'événements trop grand)."""

    code = ErrorCode.validation_error
    http_status = 422


class ResourceNotFound(HostIntegrationError):
    """Ressource absente DANS le tenant courant — jamais de fuite d'existence.

    Un accès cross-tenant retourne le même 404 qu'une ressource inexistante
    (pas de 403 distinct) : l'appelant ne peut pas distinguer « n'existe pas » de
    « existe dans un autre tenant » (fail-closed, anti-énumération)."""

    code = ErrorCode.not_found
    http_status = 404


class StateConflict(HostIntegrationError):
    """Transition d'état interdite par la machine figée (§9) — le serveur fait foi.

    Un état terminal est immuable ; une transition non listée est refusée. Un
    retry crée une nouvelle entité liée, il ne rouvre jamais un état terminal."""

    code = ErrorCode.state_conflict
    http_status = 409
