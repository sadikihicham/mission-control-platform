"""Agrégats de la vue d'ensemble V1 — tenant-scoped, dérivés serveur.

Aucun compteur n'est fourni par le client : tout est recalculé à la demande
depuis PostgreSQL (source de vérité), borné à `installation_id` du `HostContext`
(ADR-0003). Réutilise l'agrégat de coûts existant (`operations.usage`).
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.agent_control.operations import usage as usage_service
from apps.api.agent_control.overview.schemas import (
    AgentsSummary,
    CostSummary,
    DashboardOut,
    RunsSummary,
)
from apps.api.integrations.capabilities import Capability
from apps.api.integrations.host_context import HostContext
from apps.api.models import Agent, AgentAlert, AgentRun, ApprovalRequest


def _scoped(ctx: HostContext) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(ctx.installation.id))
    except (ValueError, TypeError):
        return None


def _count_by(db: Session, column, where) -> dict[str, int]:
    rows = db.execute(
        select(column, func.count()).where(where).group_by(column)
    ).all()
    out: dict[str, int] = {}
    for key, n in rows:
        k = key.value if hasattr(key, "value") else str(key)
        out[k] = int(n)
    return out


def dashboard(db: Session, ctx: HostContext) -> DashboardOut:
    inst = _scoped(ctx)

    by_status = _count_by(db, Agent.status, Agent.installation_id == inst)
    by_state = _count_by(db, Agent.state, Agent.installation_id == inst)
    agents = AgentsSummary(
        total=sum(by_status.values()),
        active=by_status.get("active", 0),
        suspended=by_status.get("suspended", 0),
        revoked=by_status.get("revoked", 0),
        archived=by_status.get("archived", 0),
        working=by_state.get("working", 0),
        idle=by_state.get("idle", 0),
        blocked=by_state.get("blocked", 0),
        stale=by_state.get("stale", 0),
        done=by_state.get("done", 0),
        error=by_state.get("error", 0),
    )

    runs_by_state = _count_by(db, AgentRun.state, AgentRun.installation_id == inst)
    runs = RunsSummary(
        total=sum(runs_by_state.values()),
        running=runs_by_state.get("running", 0),
        queued=runs_by_state.get("queued", 0),
        starting=runs_by_state.get("starting", 0),
        waiting_approval=runs_by_state.get("waiting_approval", 0),
        blocked=runs_by_state.get("blocked", 0),
        succeeded=runs_by_state.get("succeeded", 0),
        failed=runs_by_state.get("failed", 0),
        cancelled=runs_by_state.get("cancelled", 0),
        timed_out=runs_by_state.get("timed_out", 0),
    )

    approvals_pending = db.scalar(
        select(func.count(ApprovalRequest.id)).where(
            ApprovalRequest.installation_id == inst,
            ApprovalRequest.status == "pending",
        )
    ) or 0
    alerts_open = db.scalar(
        select(func.count(AgentAlert.id)).where(
            AgentAlert.installation_id == inst,
            AgentAlert.status != "resolved",
        )
    ) or 0

    summary = usage_service.aggregate(db, ctx)
    cost = CostSummary(
        total_cost=str(summary.total_cost if summary.total_cost is not None else Decimal("0")),
        currency=summary.currency or "USD",
        record_count=summary.record_count,
    )

    avg_progress = db.scalar(
        select(func.coalesce(func.avg(Agent.progress), 0)).where(
            Agent.installation_id == inst
        )
    ) or 0

    return DashboardOut(
        installation_id=str(ctx.installation.id),
        agents=agents,
        runs=runs,
        approvals_pending=int(approvals_pending),
        alerts_open=int(alerts_open),
        cost=cost,
        overall_progress=int(round(float(avg_progress))),
    )


def capabilities_list(ctx: HostContext) -> list[str]:
    order = [
        Capability.view,
        Capability.operate,
        Capability.manage_projects,
        Capability.manage_agents,
        Capability.approve,
        Capability.view_costs,
        Capability.admin,
    ]
    return [c.value for c in order if c in ctx.capabilities]
