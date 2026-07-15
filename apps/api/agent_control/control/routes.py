"""Routes opérateur du contrôle P5 (SP3) — commandes, approbations, politiques.

Toutes authentifiées par JWT hôte + capacité (matrice figée §8, `ROUTE_CAPABILITIES`),
bornées au tenant du `HostContext` (résolu serveur, ADR-0003) :

- `POST /runs/{id}/commands` (operate) : soumet une commande — évalue la politique.
- `GET /approvals` · `GET /approvals/{id}` (view) : file d'approbations du tenant.
- `POST /approvals/{id}/approve|reject` (approve) : décision versionnée.
- `GET /policies` (view) · `POST|PATCH|DELETE /policies*` (admin) : gouvernance.

Les routeurs ne portent aucune logique métier : ils délèguent au service, qui
reçoit le `HostContext` et applique bornage tenant + `require_capability`.
"""
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from apps.api.agent_control.control import approvals as approvals_service
from apps.api.agent_control.control import commands as commands_service
from apps.api.agent_control.control import policies as policies_service
from apps.api.agent_control.control.schemas import (
    ApprovalDecisionIn,
    ApprovalListOut,
    ApprovalOut,
    CommandOut,
    CommandSubmit,
    PolicyCreate,
    PolicyListOut,
    PolicyOut,
    PolicyUpdate,
)
from apps.api.core.agent_control_deps import get_host_context
from apps.api.core.db import get_db
from apps.api.integrations.capabilities import Capability
from apps.api.integrations.envelopes import PageInfo
from apps.api.integrations.host_context import HostContext
from apps.api.integrations.permissions import require_capability

router = APIRouter(prefix="/agent-control/v1", tags=["agent-control-control"])


# --- Commandes (soumission opérateur, capacité operate) -----------------------


@router.post("/runs/{run_id}/commands", response_model=CommandOut)
def submit_command(
    run_id: str,
    body: CommandSubmit,
    response: Response,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> CommandOut:
    require_capability(ctx, Capability.operate)
    result = commands_service.submit_command(db, ctx, run_id, body)
    response.status_code = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    return CommandOut.model_validate(result.command)


# --- Approbations -------------------------------------------------------------


@router.get("/approvals", response_model=ApprovalListOut)
def list_approvals(
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
) -> ApprovalListOut:
    require_capability(ctx, Capability.view)
    rows, next_cursor, has_more = approvals_service.list_approvals(
        db, ctx, limit=limit, cursor=cursor, status=status_filter
    )
    return ApprovalListOut(
        items=[ApprovalOut.model_validate(r) for r in rows],
        page_info=PageInfo(next_cursor=next_cursor, limit=limit, has_more=has_more),
    )


@router.get("/approvals/{approval_id}", response_model=ApprovalOut)
def get_approval(
    approval_id: str,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> ApprovalOut:
    require_capability(ctx, Capability.view)
    return ApprovalOut.model_validate(approvals_service.get_approval(db, ctx, approval_id))


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalOut)
def approve_approval(
    approval_id: str,
    body: ApprovalDecisionIn,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> ApprovalOut:
    require_capability(ctx, Capability.approve)
    return ApprovalOut.model_validate(approvals_service.approve(db, ctx, approval_id, body))


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalOut)
def reject_approval(
    approval_id: str,
    body: ApprovalDecisionIn,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> ApprovalOut:
    require_capability(ctx, Capability.approve)
    return ApprovalOut.model_validate(approvals_service.reject(db, ctx, approval_id, body))


# --- Politiques ---------------------------------------------------------------


@router.get("/policies", response_model=PolicyListOut)
def list_policies(
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
) -> PolicyListOut:
    require_capability(ctx, Capability.view)
    rows = policies_service.list_policies(db, ctx, limit=limit)
    return PolicyListOut(
        items=[PolicyOut.model_validate(r) for r in rows],
        page_info=PageInfo(next_cursor=None, limit=limit, has_more=False),
    )


@router.post("/policies", response_model=PolicyOut, status_code=status.HTTP_201_CREATED)
def create_policy(
    body: PolicyCreate,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> PolicyOut:
    require_capability(ctx, Capability.admin)
    return PolicyOut.model_validate(policies_service.create_policy(db, ctx, body))


@router.patch("/policies/{policy_id}", response_model=PolicyOut)
def update_policy(
    policy_id: str,
    body: PolicyUpdate,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> PolicyOut:
    require_capability(ctx, Capability.admin)
    return PolicyOut.model_validate(policies_service.update_policy(db, ctx, policy_id, body))


@router.delete("/policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_policy(
    policy_id: str,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> Response:
    require_capability(ctx, Capability.admin)
    policies_service.disable_policy(db, ctx, policy_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
