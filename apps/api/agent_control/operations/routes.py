"""Routes opérationnelles P6 (SP6) — usage, budgets, alertes, audit.

Toutes authentifiées par JWT hôte + capacité (matrice figée §8,
`ROUTE_CAPABILITIES`) et bornées au tenant du `HostContext` (résolu serveur,
ADR-0003) :

- `GET /usage` (view_costs) : agrégat + liste des consommations (coûts décimaux).
- `GET|POST /budgets` · `PATCH /budgets/{id}` (view_costs) : gouvernance budget.
- `GET /alerts` (view) · `POST /alerts/{id}/acknowledge|resolve` (operate).
- `GET /audit` (view) : journal append-only redacted, paginé.

Les routes ne portent aucune logique métier : elles délèguent aux services, qui
reçoivent le `HostContext` et appliquent bornage tenant + `require_capability`.
"""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from apps.api.agent_control.operations import alerts as alerts_service
from apps.api.agent_control.operations import audit as audit_service
from apps.api.agent_control.operations import budgets as budgets_service
from apps.api.agent_control.operations import usage as usage_service
from apps.api.agent_control.operations.schemas import (
    AlertListOut,
    AlertOut,
    AuditEntryOut,
    AuditListOut,
    BudgetCreate,
    BudgetListOut,
    BudgetOut,
    BudgetStatusOut,
    BudgetUpdate,
    UsageListOut,
    UsageRecordOut,
    UsageSummaryOut,
)
from apps.api.core.agent_control_deps import get_host_context
from apps.api.core.db import get_db
from apps.api.integrations.capabilities import Capability
from apps.api.integrations.envelopes import PageInfo
from apps.api.integrations.host_context import HostContext
from apps.api.integrations.permissions import require_capability

router = APIRouter(prefix="/agent-control/v1", tags=["agent-control-operations"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _budget_status(db: Session, budget) -> BudgetStatusOut:
    consumed, pct = budgets_service.consumed_and_pct(db, budget)
    base = BudgetOut.model_validate(budget).model_dump()
    return BudgetStatusOut(**base, consumed=consumed, pct=pct)


# --- Usage --------------------------------------------------------------------


@router.get("/usage", response_model=UsageListOut)
def get_usage(
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    agent_id: str | None = Query(default=None),
) -> UsageListOut:
    require_capability(ctx, Capability.view_costs)
    summary = usage_service.aggregate(db, ctx, project_id=project_id, agent_id=agent_id)
    rows, next_cursor, has_more = usage_service.list_usage(
        db, ctx, limit=limit, cursor=cursor, project_id=project_id, agent_id=agent_id
    )
    return UsageListOut(
        summary=UsageSummaryOut(
            total_cost=summary.total_cost,
            total_tokens=summary.total_tokens,
            total_calls=summary.total_calls,
            currency=summary.currency,
            record_count=summary.record_count,
        ),
        items=[UsageRecordOut.model_validate(r) for r in rows],
        page_info=PageInfo(next_cursor=next_cursor, limit=limit, has_more=has_more),
    )


# --- Budgets ------------------------------------------------------------------


@router.get("/budgets", response_model=BudgetListOut)
def list_budgets(
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
) -> BudgetListOut:
    require_capability(ctx, Capability.view_costs)
    rows = budgets_service.list_budgets(db, ctx, limit=limit)
    return BudgetListOut(
        items=[_budget_status(db, b) for b in rows],
        page_info=PageInfo(next_cursor=None, limit=limit, has_more=False),
    )


@router.post("/budgets", response_model=BudgetStatusOut, status_code=201)
def create_budget(
    body: BudgetCreate,
    request: Request,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> BudgetStatusOut:
    require_capability(ctx, Capability.view_costs)
    budget = budgets_service.create_budget(db, ctx, body, ip=_client_ip(request))
    return _budget_status(db, budget)


@router.patch("/budgets/{budget_id}", response_model=BudgetStatusOut)
def update_budget(
    budget_id: str,
    body: BudgetUpdate,
    request: Request,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> BudgetStatusOut:
    require_capability(ctx, Capability.view_costs)
    budget = budgets_service.update_budget(db, ctx, budget_id, body, ip=_client_ip(request))
    return _budget_status(db, budget)


# --- Alertes ------------------------------------------------------------------


@router.get("/alerts", response_model=AlertListOut)
def list_alerts(
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    severity: str | None = Query(default=None),
) -> AlertListOut:
    require_capability(ctx, Capability.view)
    rows, next_cursor, has_more = alerts_service.list_alerts(
        db, ctx, limit=limit, cursor=cursor, status=status_filter, severity=severity
    )
    return AlertListOut(
        items=[AlertOut.model_validate(r) for r in rows],
        page_info=PageInfo(next_cursor=next_cursor, limit=limit, has_more=has_more),
    )


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(
    alert_id: str,
    request: Request,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> AlertOut:
    require_capability(ctx, Capability.operate)
    return AlertOut.model_validate(
        alerts_service.acknowledge_alert(db, ctx, alert_id, ip=_client_ip(request))
    )


@router.post("/alerts/{alert_id}/resolve", response_model=AlertOut)
def resolve_alert(
    alert_id: str,
    request: Request,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> AlertOut:
    require_capability(ctx, Capability.operate)
    return AlertOut.model_validate(
        alerts_service.resolve_alert(db, ctx, alert_id, ip=_client_ip(request))
    )


# --- Audit --------------------------------------------------------------------


@router.get("/audit", response_model=AuditListOut)
def list_audit(
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    action: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
) -> AuditListOut:
    require_capability(ctx, Capability.view)
    rows, next_cursor, has_more = audit_service.list_audit(
        db, ctx, limit=limit, cursor=cursor, action=action, actor_id=actor_id
    )
    return AuditListOut(
        items=[AuditEntryOut.model_validate(r) for r in rows],
        page_info=PageInfo(next_cursor=next_cursor, limit=limit, has_more=has_more),
    )
