"""Validation des primitives et exemples du contrat Agent Control V1 — Gate P0.

- les exemples JSON livrés (`docs/agent-control/examples/v1/examples.json`) sont
  valides contre les schémas (enveloppes Pydantic livrées + modèles de référence
  déclarés ici pour les DTO de domaine, propriété de SP2/SP3) ;
- les machines d'état gèlent les transitions et les états terminaux ;
- le catalogue d'événements et les topics WS sont cohérents.

Les modèles de domaine déclarés dans ce fichier sont des schémas de VALIDATION
d'exemples (rôle « JSON Schema »), pas les DTO de production : ils listent les
champs de contrat que les exemples doivent respecter, sans préempter
l'implémentation des autres spécialistes.
"""
import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import BaseModel

from apps.api.integrations.envelopes import (
    ErrorEnvelope,
    EventEnvelopeV1,
    PageInfo,
    WsMessageV1,
)
from apps.api.integrations.events_catalog import (
    EVENT_TYPES,
    is_valid_topic,
)
from apps.api.integrations.host_context import HostContext
from apps.api.integrations.state_machines import (
    ApprovalState,
    CommandState,
    RunState,
    can_transition,
    terminal_states,
)

_EXAMPLES_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs" / "agent-control" / "examples" / "v1" / "examples.json"
)


def _examples() -> dict:
    return json.loads(_EXAMPLES_PATH.read_text())


# --- Modèles de référence pour valider les exemples de DTO de domaine ---------

class _AgentOutV1(BaseModel):
    id: str
    agent_key: str
    installation_id: str
    display_name: str | None
    description: str | None
    runtime: str | None
    provider: str | None
    client_version: str | None
    environment: str | None
    capabilities: list[str]
    status: str
    state: str
    last_heartbeat: str | None
    last_sequence: int
    registered_by: str | None
    registered_at: str | None
    revoked_at: str | None
    project_ids: list[str]
    created_at: str
    updated_at: str


class _CredentialCreatedV1(BaseModel):
    id: str
    agent_id: str
    key_prefix: str
    secret: str
    scopes: list[str]
    expires_at: str | None
    created_by: str
    created_at: str


class _RunOutV1(BaseModel):
    id: str
    installation_id: str
    project_id: str | None
    task_id: str | None
    agent_id: str
    external_run_key: str | None
    objective: str | None
    state: str
    started_at: str | None
    finished_at: str | None
    heartbeat_at: str | None
    result_summary: str | None
    error_code: str | None
    error_message: str | None
    retry_of_run_id: str | None
    version: int
    created_at: str
    updated_at: str


class _CommandOutV1(BaseModel):
    id: str
    installation_id: str
    agent_id: str
    run_id: str | None
    command_type: str
    payload: dict
    status: str
    requested_by: str | None
    approval_request_id: str | None
    idempotency_key: str
    expires_at: str | None
    delivered_at: str | None
    acknowledged_at: str | None
    result_at: str | None
    result: dict | None
    created_at: str


class _ApprovalOutV1(BaseModel):
    id: str
    installation_id: str
    project_id: str | None
    task_id: str | None
    run_id: str | None
    agent_id: str | None
    action_type: str
    risk_level: str
    title: str
    context: dict
    requested_by_agent: str | None
    status: str
    assigned_to: str | None
    expires_at: str | None
    decided_at: str | None
    decision_by: str | None
    decision_comment: str | None
    version: int
    created_at: str


class _BudgetOutV1(BaseModel):
    id: str
    installation_id: str
    scope: str
    scope_id: str | None
    period: str
    amount: str
    currency: str
    thresholds: list[int]
    projected_consumption: str
    on_exceed: str
    created_at: str
    updated_at: str


class _UsageRecordV1(BaseModel):
    id: str
    installation_id: str
    agent_id: str
    project_id: str | None
    run_id: str | None
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_tokens: int
    tool_calls: int
    duration_ms: int
    quantity: int
    currency: str
    cost: str
    occurred_at: str
    source_event_id: str | None
    pricing_version: str


# --- Enveloppes livrées -------------------------------------------------------

def test_error_envelope_example_valid():
    ErrorEnvelope.model_validate(_examples()["error_envelope"])


def test_page_info_example_valid_and_bounded():
    page = PageInfo.model_validate(_examples()["page_info"])
    assert 1 <= page.limit <= 200


def test_page_info_rejects_limit_over_max():
    with pytest.raises(ValueError):
        PageInfo(limit=201)


def test_event_envelope_example_valid():
    ev = EventEnvelopeV1.model_validate(_examples()["event_envelope"])
    assert ev.sequence >= 0
    assert ev.event_type in EVENT_TYPES


def test_ws_message_example_valid_and_tenant_stamped():
    msg = WsMessageV1.model_validate(_examples()["ws_message"])
    assert msg.tenant_id  # jamais diffusé sans tenant
    assert is_valid_topic(msg.topic)


def test_host_context_example_valid():
    ctx = HostContext.model_validate(_examples()["context_response"])
    assert ctx.tenant.external_tenant_id
    assert ctx.capabilities  # au moins une capacité


# --- Exemples de DTO de domaine ----------------------------------------------

@pytest.mark.parametrize(
    ("key", "model"),
    [
        ("agent_out", _AgentOutV1),
        ("credential_created", _CredentialCreatedV1),
        ("run_out", _RunOutV1),
        ("command_out", _CommandOutV1),
        ("approval_out", _ApprovalOutV1),
        ("budget_out", _BudgetOutV1),
        ("usage_record", _UsageRecordV1),
    ],
)
def test_domain_example_valid(key, model):
    model.model_validate(_examples()[key])


def test_money_examples_are_decimal_strings_not_floats():
    ex = _examples()
    for field, value in [
        ("amount", ex["budget_out"]["amount"]),
        ("projected_consumption", ex["budget_out"]["projected_consumption"]),
        ("cost", ex["usage_record"]["cost"]),
    ]:
        assert isinstance(value, str), f"{field} doit être une chaîne décimale"
        Decimal(value)  # parse sans perte


def test_agent_key_is_installation_namespaced():
    # `<installation_key>:<local_key>` — unicité Contract A préservée.
    key = _examples()["agent_out"]["agent_key"]
    assert ":" in key and key.split(":", 1)[0]


# --- Machines d'état ----------------------------------------------------------

def test_run_terminal_states_are_immutable():
    assert terminal_states("run") == frozenset(
        {RunState.succeeded, RunState.failed, RunState.cancelled, RunState.timed_out}
    )
    # Aucun état terminal ne transitionne.
    assert not can_transition("run", RunState.succeeded, RunState.running)


def test_run_happy_path_transitions():
    assert can_transition("run", RunState.queued, RunState.starting)
    assert can_transition("run", RunState.starting, RunState.running)
    assert can_transition("run", RunState.running, RunState.waiting_approval)
    assert can_transition("run", RunState.waiting_approval, RunState.running)
    assert can_transition("run", RunState.running, RunState.succeeded)


def test_command_transitions_and_terminals():
    assert can_transition("command", CommandState.queued, CommandState.delivered)
    assert can_transition("command", CommandState.delivered, CommandState.acknowledged)
    assert can_transition("command", CommandState.acknowledged, CommandState.succeeded)
    assert can_transition("command", CommandState.queued, CommandState.cancelled)
    assert not can_transition("command", CommandState.succeeded, CommandState.failed)


def test_approval_is_pending_then_final():
    assert terminal_states("approval") == frozenset(
        {
            ApprovalState.approved,
            ApprovalState.rejected,
            ApprovalState.expired,
            ApprovalState.cancelled,
        }
    )
    assert can_transition("approval", ApprovalState.pending, ApprovalState.approved)
    assert not can_transition("approval", ApprovalState.approved, ApprovalState.rejected)


def test_alert_and_credential_machines():
    assert can_transition("alert", "open", "acknowledged")
    assert can_transition("alert", "acknowledged", "resolved")
    assert can_transition("alert", "open", "resolved")
    assert terminal_states("alert") == frozenset({"resolved"})
    assert can_transition("credential", "active", "revoked")
    assert not can_transition("credential", "revoked", "active")


# --- Catalogue d'événements et topics ----------------------------------------

def test_event_catalog_has_no_v0_type_collision():
    v0_types = {"agent.update", "agent.stale", "stats.update", "refresh"}
    assert EVENT_TYPES.isdisjoint(v0_types)


def test_topic_validation():
    assert is_valid_topic("fleet")
    assert is_valid_topic("approvals")
    assert is_valid_topic("run:abc")
    assert is_valid_topic("project:xyz")
    assert not is_valid_topic("run")          # famille paramétrée sans identifiant
    assert not is_valid_topic("unknown:1")    # famille inconnue
    assert not is_valid_topic("fleet:1")      # fleet est scalaire, pas paramétré
