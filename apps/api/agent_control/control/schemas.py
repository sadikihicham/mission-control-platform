"""DTO publics du contrôle P5 : politiques, commandes, approbations (SP3).

Formes de sortie exposées aux routes `/agent-control/v1/{policies,approvals}` et
`/runs/{id}/commands`, et aux routes agent `/agent/commands*`. N'exposent jamais
le tenant interne côté sortie superflue ni de secret. `command_out` /
`approval_out` / `policy_out` respectent le contrat V1 §13.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from apps.api.integrations.envelopes import PageInfo

# --- Effets et portées de politique (valeurs de contrat) ----------------------

POLICY_EFFECTS: frozenset[str] = frozenset({"allow", "deny", "require_approval"})
POLICY_SCOPES: frozenset[str] = frozenset({"installation", "project", "agent"})
RISK_LEVELS: frozenset[str] = frozenset({"low", "medium", "high", "critical"})


# --- Politiques ---------------------------------------------------------------


class PolicyCreate(BaseModel):
    """Création d'une politique de gouvernance."""

    scope_type: str = "installation"
    scope_id: uuid.UUID | None = None
    action_type: str = "*"
    effect: str
    risk_level: str | None = None
    conditions: dict = Field(default_factory=dict)
    priority: int = 100
    description: str | None = None


class PolicyUpdate(BaseModel):
    """Mise à jour partielle d'une politique (verrou optimiste via `version`)."""

    version: int
    scope_type: str | None = None
    scope_id: uuid.UUID | None = None
    action_type: str | None = None
    effect: str | None = None
    risk_level: str | None = None
    conditions: dict | None = None
    priority: int | None = None
    status: str | None = None
    description: str | None = None


class PolicyOut(BaseModel):
    """Politique (portée, effet, priorité, version optimiste)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scope_type: str
    scope_id: uuid.UUID | None = None
    action_type: str
    effect: str
    risk_level: str | None = None
    conditions: dict = {}
    priority: int
    status: str
    description: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime


class PolicyListOut(BaseModel):
    items: list[PolicyOut]
    page_info: PageInfo


# --- Commandes ----------------------------------------------------------------


class CommandSubmit(BaseModel):
    """Soumission d'une commande pour un run (opérateur, capacité `operate`)."""

    command_type: str
    payload: dict = Field(default_factory=dict)
    # Clé d'idempotence optionnelle (sinon générée) — rejouer = pas de doublon.
    idempotency_key: str | None = None
    # TTL de la commande (secondes) ; sinon défaut `MC_COMMAND_DEFAULT_TTL_SECONDS`.
    expires_in_seconds: int | None = Field(default=None, ge=1)
    # Niveau de risque indicatif (peut être surchargé par la politique applicable).
    risk_level: str | None = None


class CommandOut(BaseModel):
    """Commande (machine §9, idempotency_key, approval_request_id) — contrat §13."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    run_id: uuid.UUID | None = None
    command_type: str
    payload: dict = {}
    status: str
    idempotency_key: str
    approval_request_id: uuid.UUID | None = None
    policy_effect: str | None = None
    risk_level: str | None = None
    released_at: datetime | None = None
    expires_at: datetime | None = None
    delivered_at: datetime | None = None
    acknowledged_at: datetime | None = None
    result_at: datetime | None = None
    result_status: str | None = None
    error_message: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime


class CommandListOut(BaseModel):
    items: list[CommandOut]
    page_info: PageInfo


class CommandResultIn(BaseModel):
    """Résultat publié par l'agent : succès/échec + charge/erreur bornées."""

    status: str  # success | failure
    result_payload: dict = Field(default_factory=dict)
    error_message: str | None = None


# --- Approbations -------------------------------------------------------------


class ApprovalOut(BaseModel):
    """Demande d'approbation (risk_level, version, décision auditée) — contrat §13."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    agent_id: uuid.UUID
    policy_id: uuid.UUID | None = None
    action_type: str
    risk_level: str
    title: str
    context: dict = {}
    requested_by: uuid.UUID | None = None
    requested_by_agent: bool = False
    status: str
    assigned_to: uuid.UUID | None = None
    expires_at: datetime | None = None
    decided_at: datetime | None = None
    decision_by: uuid.UUID | None = None
    decision_comment: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime


class ApprovalListOut(BaseModel):
    items: list[ApprovalOut]
    page_info: PageInfo


class ApprovalDecisionIn(BaseModel):
    """Décision d'approbation : `version` attendue (verrou optimiste) + commentaire."""

    version: int
    comment: str | None = None
