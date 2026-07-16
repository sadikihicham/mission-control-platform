"""DTO de la vue d'ensemble V1 — dashboard, santé, activation d'installation."""
from pydantic import BaseModel, Field


class AgentsSummary(BaseModel):
    total: int = 0
    active: int = 0        # statut registre
    suspended: int = 0
    revoked: int = 0
    archived: int = 0
    # États live (dérivés serveur)
    working: int = 0
    idle: int = 0
    blocked: int = 0
    stale: int = 0
    done: int = 0
    error: int = 0


class RunsSummary(BaseModel):
    total: int = 0
    running: int = 0
    queued: int = 0
    starting: int = 0
    waiting_approval: int = 0
    blocked: int = 0
    succeeded: int = 0
    failed: int = 0
    cancelled: int = 0
    timed_out: int = 0


class CostSummary(BaseModel):
    total_cost: str = "0"       # décimal en chaîne (jamais float)
    currency: str = "USD"
    record_count: int = 0


class DashboardOut(BaseModel):
    """Agrégats tenant-scoped réels : santé, runs, validations, budget."""

    installation_id: str
    agents: AgentsSummary
    runs: RunsSummary
    approvals_pending: int = 0
    alerts_open: int = 0
    cost: CostSummary
    overall_progress: int = 0   # moyenne de progression des agents (0..100)


class HealthOut(BaseModel):
    """Santé du module pour le tenant courant (fail-closed si tenant absent)."""

    status: str = "ok"
    installation_id: str
    installation_status: str
    tenant_status: str
    capabilities: list[str] = Field(default_factory=list)


class InstallationOut(BaseModel):
    id: str
    installation_key: str
    external_tenant_id: str
    status: str
