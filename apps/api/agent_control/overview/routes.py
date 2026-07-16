"""Routes de la vue d'ensemble V1 — `/health`, `/dashboard`, activation installation.

`GET /health` et `GET /dashboard` : capacité `view`, tenant-scoped.
`POST /installations/{id}/activate` : capacité `admin`. Toutes fail-closed via le
`HostContext` résolu serveur (ADR-0003).
"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.agent_control.overview import service
from apps.api.agent_control.overview.schemas import (
    DashboardOut,
    HealthOut,
    InstallationOut,
)
from apps.api.core.agent_control_deps import get_host_context
from apps.api.core.db import get_db
from apps.api.integrations.capabilities import Capability
from apps.api.integrations.errors import ResourceNotFound
from apps.api.integrations.host_context import HostContext
from apps.api.integrations.permissions import require_capability
from apps.api.models import MCInstallation

router = APIRouter(prefix="/agent-control/v1", tags=["agent-control-overview"])


@router.get("/health", response_model=HealthOut)
def health(
    ctx: HostContext = Depends(get_host_context),
) -> HealthOut:
    require_capability(ctx, Capability.view)
    return HealthOut(
        status="ok",
        installation_id=str(ctx.installation.id),
        installation_status=ctx.installation.status,
        tenant_status=ctx.tenant.status,
        capabilities=service.capabilities_list(ctx),
    )


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> DashboardOut:
    require_capability(ctx, Capability.view)
    return service.dashboard(db, ctx)


@router.post("/installations/{installation_id}/activate", response_model=InstallationOut)
def activate_installation(
    installation_id: str,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> InstallationOut:
    require_capability(ctx, Capability.admin)
    # Un admin ne peut activer que SON installation courante (fail-closed, ADR-0003).
    if str(installation_id) != str(ctx.installation.id):
        raise ResourceNotFound(
            "installation introuvable", details={"installation_id": installation_id}
        )
    try:
        inst_uuid = uuid.UUID(str(installation_id))
    except (ValueError, TypeError):
        inst_uuid = None
    row = (
        db.scalar(select(MCInstallation).where(MCInstallation.id == inst_uuid))
        if inst_uuid is not None
        else None
    )
    if row is not None:
        row.status = "active"
        row.archived_at = None
        db.commit()
        db.refresh(row)
        return InstallationOut(
            id=str(row.id),
            installation_key=row.installation_key,
            external_tenant_id=row.external_tenant_id,
            status=row.status,
        )
    # Mode local déterministe : pas de ligne DB requise (installation synthétique).
    return InstallationOut(
        id=str(ctx.installation.id),
        installation_key=ctx.installation.installation_key,
        external_tenant_id=ctx.installation.external_tenant_id,
        status="active",
    )
