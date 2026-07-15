"""Matrice de permissions exhaustive capacités × routes V1 — Gate P0.

Vérifie que : (1) chaque route V1 documentée a une entrée ; (2) chaque entrée
exige une capacité valide ou l'auth par credential agent ; (3) l'autorisation
par rôle (via l'adaptateur local) correspond à la matrice attendue, fail-closed.
"""
import pytest

from apps.api.integrations.capabilities import Capability, capabilities_for_role
from apps.api.integrations.errors import PermissionDenied
from apps.api.integrations.host_context import (
    HostContext,
    InstallationRef,
    TenantRef,
    UserRef,
)
from apps.api.integrations.permissions import (
    AGENT_CREDENTIAL,
    ROUTE_CAPABILITIES,
    require_capability,
)

# Ensemble documenté des routes V1 (schéma solution §8). Doit égaler exactement
# les clés de ROUTE_CAPABILITIES : ni route oubliée, ni route en trop.
EXPECTED_ROUTES = {
    "GET /agent-control/v1/context",
    "GET /agent-control/v1/capabilities",
    "GET /agent-control/v1/health",
    "POST /agent-control/v1/installations/{id}/activate",
    "GET /agent-control/v1/agents",
    "POST /agent-control/v1/agents",
    "GET /agent-control/v1/agents/{id}",
    "PATCH /agent-control/v1/agents/{id}",
    "GET /agent-control/v1/agents/{id}/health",
    "POST /agent-control/v1/agents/{id}/credentials",
    "POST /agent-control/v1/agents/{id}/credentials/{credential_id}/rotate",
    "DELETE /agent-control/v1/agents/{id}/credentials/{credential_id}",
    "POST /agent-control/v1/agents/{id}/suspend",
    "POST /agent-control/v1/agents/{id}/resume",
    "POST /agent-control/v1/agents/{id}/archive",
    "POST /agent-control/v1/ingest/events",
    "POST /agent-control/v1/ingest/heartbeat",
    "GET /agent-control/v1/agent/commands",
    "POST /agent-control/v1/agent/commands/{id}/ack",
    "POST /agent-control/v1/agent/commands/{id}/result",
    "GET /agent-control/v1/projects",
    "POST /agent-control/v1/projects",
    "GET /agent-control/v1/projects/{id}",
    "PATCH /agent-control/v1/projects/{id}",
    "DELETE /agent-control/v1/projects/{id}",
    "GET /agent-control/v1/projects/{id}/tasks",
    "POST /agent-control/v1/projects/{id}/tasks",
    "GET /agent-control/v1/tasks/{id}",
    "PATCH /agent-control/v1/tasks/{id}",
    "POST /agent-control/v1/tasks/{id}/assign",
    "GET /agent-control/v1/runs",
    "GET /agent-control/v1/runs/{id}",
    "GET /agent-control/v1/runs/{id}/timeline",
    "POST /agent-control/v1/runs/{id}/commands",
    "GET /agent-control/v1/approvals",
    "GET /agent-control/v1/approvals/{id}",
    "POST /agent-control/v1/approvals/{id}/approve",
    "POST /agent-control/v1/approvals/{id}/reject",
    "GET /agent-control/v1/policies",
    "POST /agent-control/v1/policies",
    "PATCH /agent-control/v1/policies/{id}",
    "DELETE /agent-control/v1/policies/{id}",
    "GET /agent-control/v1/alerts",
    "POST /agent-control/v1/alerts/{id}/acknowledge",
    "POST /agent-control/v1/alerts/{id}/resolve",
    "GET /agent-control/v1/dashboard",
    "GET /agent-control/v1/usage",
    "GET /agent-control/v1/budgets",
    "POST /agent-control/v1/budgets",
    "PATCH /agent-control/v1/budgets/{id}",
    "GET /agent-control/v1/reports/export.csv",
    "GET /agent-control/v1/audit",
}


def _ctx(role: str) -> HostContext:
    return HostContext(
        request_id="req-1",
        installation=InstallationRef(
            id="i", installation_key="local", external_tenant_id="local"
        ),
        tenant=TenantRef(external_tenant_id="local", name="Local", slug="local"),
        user=UserRef(external_user_id="u", email="u@mc.local"),
        capabilities=capabilities_for_role(role),
    )


def test_matrix_is_exhaustive_over_documented_routes():
    assert set(ROUTE_CAPABILITIES.keys()) == EXPECTED_ROUTES


def test_every_entry_is_valid_capability_or_agent_credential():
    for route, required in ROUTE_CAPABILITIES.items():
        assert required == AGENT_CREDENTIAL or isinstance(required, Capability), route


def test_ingest_routes_use_agent_credential_not_user_rbac():
    for route, required in ROUTE_CAPABILITIES.items():
        if "/ingest/" in route or "/agent/commands" in route:
            assert required == AGENT_CREDENTIAL, route


def test_require_capability_is_fail_closed():
    ctx = _ctx("viewer")  # {view}
    require_capability(ctx, Capability.view)  # ne lève pas
    with pytest.raises(PermissionDenied):
        require_capability(ctx, Capability.manage_projects)


@pytest.mark.parametrize(
    ("role", "granted", "denied"),
    [
        ("viewer", {Capability.view}, {Capability.operate, Capability.admin}),
        (
            "developer",
            {Capability.view, Capability.operate},
            {Capability.manage_projects, Capability.approve, Capability.admin},
        ),
        (
            "pm",
            {
                Capability.view,
                Capability.operate,
                Capability.manage_projects,
                Capability.approve,
                Capability.view_costs,
            },
            {Capability.manage_agents, Capability.admin},
        ),
        (
            "cto",
            {
                Capability.view,
                Capability.operate,
                Capability.manage_projects,
                Capability.manage_agents,
                Capability.approve,
                Capability.view_costs,
            },
            {Capability.admin},
        ),
        ("admin", set(Capability), set()),
    ],
)
def test_role_capability_mapping(role, granted, denied):
    caps = capabilities_for_role(role)
    assert set(caps) == granted
    for cap in denied:
        assert cap not in caps


def test_unknown_role_has_no_capabilities():
    assert capabilities_for_role("root") == frozenset()
    assert capabilities_for_role(None) == frozenset()


def test_capabilities_are_monotone_with_host_hierarchy():
    order = ["viewer", "developer", "pm", "cto", "admin"]
    for lower, higher in zip(order, order[1:], strict=False):
        assert capabilities_for_role(lower) <= capabilities_for_role(higher)


def test_route_authorization_matches_role_for_representative_routes():
    # Vérifie l'accès effectif (route → capacité → rôle), hors routes credential agent.
    cases = [
        ("GET /agent-control/v1/agents", "viewer", True),
        ("POST /agent-control/v1/agents", "pm", False),          # manage_agents ≥ cto
        ("POST /agent-control/v1/agents", "cto", True),
        ("PATCH /agent-control/v1/projects/{id}", "developer", False),
        ("PATCH /agent-control/v1/projects/{id}", "pm", True),
        ("POST /agent-control/v1/approvals/{id}/approve", "developer", False),
        ("POST /agent-control/v1/approvals/{id}/approve", "pm", True),
        ("GET /agent-control/v1/usage", "developer", False),
        ("GET /agent-control/v1/usage", "pm", True),
        ("POST /agent-control/v1/policies", "cto", False),        # admin only
        ("POST /agent-control/v1/policies", "admin", True),
        ("POST /agent-control/v1/runs/{id}/commands", "developer", True),  # operate
    ]
    for route, role, allowed in cases:
        required = ROUTE_CAPABILITIES[route]
        assert isinstance(required, Capability), route
        ctx = _ctx(role)
        if allowed:
            require_capability(ctx, required)
        else:
            with pytest.raises(PermissionDenied):
                require_capability(ctx, required)
