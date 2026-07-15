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
