"""Contrat exécutable Agent Control V1 — ports d'intégration hôte et primitives.

Ce paquet contient **uniquement** des primitives de contrat (interfaces de ports
hôte, modèles de contexte, enveloppes, machines d'état, matrice de permissions).
Il ne contient **aucune** logique métier des autres spécialistes (données, API,
runtime, coûts, frontend) et n'est monté nulle part dans `main.py` : c'est une
frontière de bounded context que SP2..SP7 consomment sans réinventer de champ,
transition, permission, route ou stratégie tenant.

Source de vérité associée : `.mission-control/CONTRACTS_AGENT_CONTROL_V1.md`.
Compatibilité gelée : `.mission-control/CONTRACTS.md` (contrats V0 A–E, inchangés).
"""
from apps.api.integrations.capabilities import ROLE_CAPABILITIES, Capability
from apps.api.integrations.envelopes import (
    ErrorCode,
    ErrorEnvelope,
    EventEnvelopeV1,
    PageInfo,
    WsMessageV1,
)
from apps.api.integrations.errors import (
    HostIntegrationError,
    IdentityUnresolved,
    PermissionDenied,
    TenantUnresolved,
    UserNotInTenant,
)
from apps.api.integrations.host_context import (
    HostContext,
    InstallationRef,
    TenantRef,
    UserRef,
)
from apps.api.integrations.ports import (
    HostIdentityPort,
    HostNavigationPort,
    HostNotificationPort,
    HostPermissionPort,
    HostTenantPort,
)

__all__ = [
    "Capability",
    "ROLE_CAPABILITIES",
    "ErrorCode",
    "ErrorEnvelope",
    "EventEnvelopeV1",
    "PageInfo",
    "WsMessageV1",
    "HostIntegrationError",
    "IdentityUnresolved",
    "TenantUnresolved",
    "UserNotInTenant",
    "PermissionDenied",
    "HostContext",
    "InstallationRef",
    "TenantRef",
    "UserRef",
    "HostIdentityPort",
    "HostTenantPort",
    "HostPermissionPort",
    "HostNavigationPort",
    "HostNotificationPort",
]
