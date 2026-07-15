"""Capacités du module Agent Control et mapping RBAC hôte → capacités.

Les capacités sont la seule unité d'autorisation exposée au domaine V1. Le RBAC
global de la plateforme hôte (rôles `viewer < developer < pm < cto < admin`) n'est
jamais consulté directement par un service métier : il est traduit une seule fois
en un ensemble de capacités par l'adaptateur hôte (`HostPermissionPort`).

Décision : voir `docs/agent-control/adr/0008-mapping-rbac-hote-vers-capacites.md`.
Le mapping local ci-dessous est le défaut de l'adaptateur `local` ; un adaptateur
`jwt` d'un hôte réel peut fournir un mapping différent sans changer le domaine.
"""
import enum


class Capability(str, enum.Enum):
    """Capacités minimales du module (schéma solution §4 `HostPermissionPort`)."""

    view = "view"                     # lecture dashboard, agents, projets, runs, audit
    operate = "operate"              # acquitter alerte, relancer, pause/reprise/cancel
    manage_agents = "manage_agents"  # registre, credentials, suspension/révocation
    manage_projects = "manage_projects"  # CRUD projet/tâche, affectation, priorités
    approve = "approve"              # décision sur demandes d'approbation
    view_costs = "view_costs"        # usage, budgets, exports coûts
    admin = "admin"                  # politiques, installations, intégrations, tout


# Mapping du rôle hôte (chaîne libre) vers l'ensemble de capacités du module.
# Additif et monotone avec la hiérarchie existante : un rôle plus élevé possède au
# moins les capacités du rôle inférieur. Un rôle inconnu → aucune capacité
# (fail-closed). Ce mapping vit ici pour rester la seule source de la traduction.
ROLE_CAPABILITIES: dict[str, frozenset[Capability]] = {
    "viewer": frozenset({Capability.view}),
    "developer": frozenset({Capability.view, Capability.operate}),
    "pm": frozenset(
        {
            Capability.view,
            Capability.operate,
            Capability.manage_projects,
            Capability.approve,
            Capability.view_costs,
        }
    ),
    "cto": frozenset(
        {
            Capability.view,
            Capability.operate,
            Capability.manage_projects,
            Capability.manage_agents,
            Capability.approve,
            Capability.view_costs,
        }
    ),
    "admin": frozenset(Capability),  # toutes les capacités
}


def capabilities_for_role(role: str | None) -> frozenset[Capability]:
    """Traduit un rôle hôte en capacités. Rôle inconnu/absent → ensemble vide."""
    if not role:
        return frozenset()
    return ROLE_CAPABILITIES.get(role, frozenset())
