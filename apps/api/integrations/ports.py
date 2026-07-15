"""Ports d'intégration hôte (interfaces `Protocol`).

Le domaine Agent Control ne dépend jamais des tables de la plateforme hôte : il
consomme ces cinq ports. Un adaptateur concret (`local` en développement, `jwt`
en production embarquée) implémente ces protocoles. La sélection se fait par
configuration (`MC_HOST_ADAPTER`), pas par des `if embedded` dispersés dans les
services.

Ces `Protocol` définissent la frontière (signatures + docstrings) ; ils ne
contiennent aucune logique. SP1 fournit aussi un adaptateur `local` de référence
(`local_adapter.LocalHostAdapter`).
"""
from typing import Protocol, runtime_checkable

from apps.api.integrations.capabilities import Capability
from apps.api.integrations.host_context import (
    InstallationRef,
    TenantRef,
    UserRef,
)


@runtime_checkable
class HostIdentityPort(Protocol):
    """Résout l'identité de l'utilisateur courant depuis le credential hôte."""

    def resolve_identity(self, credential: object) -> UserRef:
        """Valide le JWT/session hôte et retourne un `UserRef`.

        Ne recopie jamais mot de passe ni secret SSO. Lève `IdentityUnresolved`
        si le credential est absent, invalide, expiré ou l'utilisateur inactif.
        """
        ...


@runtime_checkable
class HostTenantPort(Protocol):
    """Résout le tenant actif et vérifie l'appartenance de l'utilisateur."""

    def resolve_tenant(self, user: UserRef, installation_key: str) -> tuple[InstallationRef, TenantRef]:
        """Retourne (installation, tenant) actif pour cette clé d'installation.

        Lève `TenantUnresolved` si aucun tenant/installation actif, et
        `UserNotInTenant` si l'utilisateur n'appartient pas au tenant.
        """
        ...

    def user_belongs_to_tenant(self, user: UserRef, tenant: TenantRef) -> bool:
        """Vrai si l'utilisateur appartient au tenant (fail-closed sinon)."""
        ...


@runtime_checkable
class HostPermissionPort(Protocol):
    """Traduit les permissions hôte vers les capacités du module."""

    def capabilities_for(self, user: UserRef, tenant: TenantRef) -> frozenset[Capability]:
        """Retourne l'ensemble de capacités accordées. L'UI peut masquer une
        action, mais l'API vérifie toujours cette source côté serveur."""
        ...


@runtime_checkable
class HostNavigationPort(Protocol):
    """Enregistre le module et ouvre ses routes dans le shell hôte."""

    def register_module(self, base_path: str, routes: list[str], badges: dict) -> None:
        """Déclare le module, ses routes et badges auprès du shell hôte."""
        ...

    def open_route(self, path: str) -> None:
        """Ouvre une route du module dans le shell existant (pas de topbar/logout
        dupliqués)."""
        ...


@runtime_checkable
class HostNotificationPort(Protocol):
    """Envoie des notifications via l'infrastructure hôte, de façon idempotente."""

    def notify(self, *, recipient: str, subject: str, body: str, idempotency_key: str) -> str:
        """Envoie une notification in-app/email et retourne un identifiant de
        remise. Un même `idempotency_key` ne doit jamais dupliquer l'envoi."""
        ...
