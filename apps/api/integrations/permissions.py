"""Matrice capacités × routes × actions du contrat V1 (autoritaire).

Chaque route V1 exige **exactement une** capacité (`Capability`) ou est
authentifiée par credential agent (`AGENT_CREDENTIAL`, hors RBAC utilisateur).
La vérification est toujours faite côté serveur (`require_capability`), fail-closed.
Cette table est exhaustive sur les routes du schéma solution §8 et sert de source
au test de matrice de permissions.
"""
from apps.api.integrations.capabilities import Capability
from apps.api.integrations.errors import PermissionDenied
from apps.api.integrations.host_context import HostContext

# Sentinelle : route authentifiée par credential agent, pas par JWT utilisateur.
# Le tenant/agent est dérivé du credential ; aucune capacité RBAC n'est requise.
AGENT_CREDENTIAL = "agent_credential"

RequiredAuth = Capability | str

# Clé = "METHOD /chemin" ; valeur = capacité requise ou AGENT_CREDENTIAL.
ROUTE_CAPABILITIES: dict[str, RequiredAuth] = {
    # Contexte hôte, capacités et santé
    "GET /agent-control/v1/context": Capability.view,
    "GET /agent-control/v1/capabilities": Capability.view,
    "GET /agent-control/v1/health": Capability.view,
    "POST /agent-control/v1/installations/{id}/activate": Capability.admin,
    # Registre d'agents (lecture = view ; mutation = manage_agents)
    "GET /agent-control/v1/agents": Capability.view,
    "POST /agent-control/v1/agents": Capability.manage_agents,
    "GET /agent-control/v1/agents/{id}": Capability.view,
    "PATCH /agent-control/v1/agents/{id}": Capability.manage_agents,
    "GET /agent-control/v1/agents/{id}/health": Capability.view,
    "POST /agent-control/v1/agents/{id}/credentials": Capability.manage_agents,
    "POST /agent-control/v1/agents/{id}/credentials/{credential_id}/rotate": Capability.manage_agents,
    "DELETE /agent-control/v1/agents/{id}/credentials/{credential_id}": Capability.manage_agents,
    "POST /agent-control/v1/agents/{id}/suspend": Capability.manage_agents,
    "POST /agent-control/v1/agents/{id}/resume": Capability.manage_agents,
    "POST /agent-control/v1/agents/{id}/archive": Capability.manage_agents,
    # Ingest V1 — authentifié par credential agent (pas de JWT utilisateur)
    "POST /agent-control/v1/ingest/events": AGENT_CREDENTIAL,
    "POST /agent-control/v1/ingest/heartbeat": AGENT_CREDENTIAL,
    "GET /agent-control/v1/agent/commands": AGENT_CREDENTIAL,
    "POST /agent-control/v1/agent/commands/{id}/ack": AGENT_CREDENTIAL,
    "POST /agent-control/v1/agent/commands/{id}/result": AGENT_CREDENTIAL,
    # Projets, tâches et runs
    "GET /agent-control/v1/projects": Capability.view,
    "POST /agent-control/v1/projects": Capability.manage_projects,
    "GET /agent-control/v1/projects/{id}": Capability.view,
    "PATCH /agent-control/v1/projects/{id}": Capability.manage_projects,
    "DELETE /agent-control/v1/projects/{id}": Capability.manage_projects,
    "GET /agent-control/v1/projects/{id}/tasks": Capability.view,
    "POST /agent-control/v1/projects/{id}/tasks": Capability.manage_projects,
    "GET /agent-control/v1/tasks/{id}": Capability.view,
    "PATCH /agent-control/v1/tasks/{id}": Capability.manage_projects,
    "POST /agent-control/v1/tasks/{id}/assign": Capability.manage_projects,
    "GET /agent-control/v1/runs": Capability.view,
    "GET /agent-control/v1/runs/{id}": Capability.view,
    "GET /agent-control/v1/runs/{id}/timeline": Capability.view,
    "POST /agent-control/v1/runs/{id}/commands": Capability.operate,
    # Approbations, politiques et alertes
    "GET /agent-control/v1/approvals": Capability.view,
    "GET /agent-control/v1/approvals/{id}": Capability.view,
    "POST /agent-control/v1/approvals/{id}/approve": Capability.approve,
    "POST /agent-control/v1/approvals/{id}/reject": Capability.approve,
    "GET /agent-control/v1/policies": Capability.view,
    "POST /agent-control/v1/policies": Capability.admin,
    "PATCH /agent-control/v1/policies/{id}": Capability.admin,
    "DELETE /agent-control/v1/policies/{id}": Capability.admin,
    "GET /agent-control/v1/alerts": Capability.view,
    "POST /agent-control/v1/alerts/{id}/acknowledge": Capability.operate,
    "POST /agent-control/v1/alerts/{id}/resolve": Capability.operate,
    # Coûts, reporting et audit
    "GET /agent-control/v1/dashboard": Capability.view,
    "GET /agent-control/v1/usage": Capability.view_costs,
    "GET /agent-control/v1/budgets": Capability.view_costs,
    "POST /agent-control/v1/budgets": Capability.view_costs,
    "PATCH /agent-control/v1/budgets/{id}": Capability.view_costs,
    "GET /agent-control/v1/reports/export.csv": Capability.view_costs,
    "GET /agent-control/v1/audit": Capability.view,
}


def require_capability(ctx: HostContext, capability: Capability) -> None:
    """Refuse (fail-closed) si la capacité n'est pas accordée dans le contexte."""
    if capability not in ctx.capabilities:
        raise PermissionDenied(
            f"capacité requise absente : {capability.value}",
            details={"required": capability.value},
        )
