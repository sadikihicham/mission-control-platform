"""DTO publics du plan opérationnel P6 (SP6) : usage, budgets, alertes, audit.

Les montants monétaires sont sérialisés en **chaîne** (`str(Decimal)`) et non en
`float` : la précision décimale est préservée de bout en bout (base → API →
client), condition de la réconciliation des coûts. Aucun secret n'est exposé :
les DTO d'alerte/audit ne portent que des champs déjà redacted.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from apps.api.integrations.envelopes import PageInfo

# --- Usage --------------------------------------------------------------------


class UsageRecordOut(BaseModel):
    """Enregistrement de consommation (coût `Decimal` sérialisé en chaîne)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    project_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    provider: str | None = None
    model: str | None = None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    calls: int
    duration_ms: int | None = None
    currency: str
    cost: Decimal
    pricing_version: str
    occurred_at: datetime

    @field_serializer("cost")
    def _ser_cost(self, value: Decimal) -> str:
        return str(value)


class UsageSummaryOut(BaseModel):
    """Agrégat de consommation du tenant — réconciliable avec la somme des records."""

    total_cost: Decimal
    total_tokens: int
    total_calls: int
    currency: str
    record_count: int

    @field_serializer("total_cost")
    def _ser_total(self, value: Decimal) -> str:
        return str(value)


class UsageListOut(BaseModel):
    summary: UsageSummaryOut
    items: list[UsageRecordOut]
    page_info: PageInfo


# --- Budgets ------------------------------------------------------------------


class BudgetCreate(BaseModel):
    scope_type: str = "installation"
    scope_id: uuid.UUID | None = None
    period: str = "monthly"
    currency: str = "USD"
    amount_limit: Decimal = Field(gt=0)
    thresholds: list[int] | None = None
    on_exceed: str = "alert"
    description: str | None = None


class BudgetUpdate(BaseModel):
    version: int
    amount_limit: Decimal | None = Field(default=None, gt=0)
    thresholds: list[int] | None = None
    on_exceed: str | None = None
    period: str | None = None
    status: str | None = None
    description: str | None = None


class BudgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scope_type: str
    scope_id: uuid.UUID | None = None
    period: str
    currency: str
    amount_limit: Decimal
    thresholds: list[int] = []
    on_exceed: str
    status: str
    description: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime

    @field_serializer("amount_limit")
    def _ser_limit(self, value: Decimal) -> str:
        return str(value)


class BudgetStatusOut(BudgetOut):
    """Budget + consommation courante (recalculée depuis les usages)."""

    consumed: Decimal
    pct: Decimal

    @field_serializer("consumed")
    def _ser_consumed(self, value: Decimal) -> str:
        return str(value)

    @field_serializer("pct")
    def _ser_pct(self, value: Decimal) -> str:
        return str(value)


class BudgetListOut(BaseModel):
    items: list[BudgetStatusOut]
    page_info: PageInfo


# --- Alertes ------------------------------------------------------------------


class AlertOut(BaseModel):
    """Alerte (dédupliquée, ACK/résolution) — `details` déjà redacted."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    alert_type: str
    severity: str
    status: str
    target_type: str | None = None
    target_id: uuid.UUID | None = None
    dedup_key: str
    title: str
    details: dict = {}
    opened_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    version: int


class AlertListOut(BaseModel):
    items: list[AlertOut]
    page_info: PageInfo


# --- Audit --------------------------------------------------------------------


class AuditEntryOut(BaseModel):
    """Entrée d'audit (append-only, redacted). Jamais de secret/IP en clair."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_type: str
    actor_id: str | None = None
    actor_label: str | None = None
    action: str
    target_type: str | None = None
    target_id: str | None = None
    before: dict | None = None
    after: dict | None = None
    request_id: str | None = None
    ip_hash: str | None = None
    created_at: datetime


class AuditListOut(BaseModel):
    items: list[AuditEntryOut]
    page_info: PageInfo
