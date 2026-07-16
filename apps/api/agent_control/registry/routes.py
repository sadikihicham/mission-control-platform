"""Routes du registre d'agents V1 — `/agent-control/v1/agents*`.

Lecture (`view`) et mutation (`manage_agents`) selon la matrice figée (§5,
`ROUTE_CAPABILITIES`), toujours bornées au tenant du `HostContext` (ADR-0003).
Les routes ne portent pas de logique métier : elles délèguent au service.
"""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from apps.api.agent_control.registry import service
from apps.api.agent_control.registry.schemas import (
    AgentCreate,
    AgentHealthOut,
    AgentListOut,
    AgentRegistryOut,
    AgentUpdate,
    CredentialCreate,
    CredentialCreated,
)
from apps.api.core.agent_control_deps import get_host_context
from apps.api.core.db import get_db
from apps.api.integrations.capabilities import Capability
from apps.api.integrations.envelopes import PageInfo
from apps.api.integrations.host_context import HostContext
from apps.api.integrations.permissions import require_capability

router = APIRouter(prefix="/agent-control/v1/agents", tags=["agent-control-registry"])


def _credential_created(cred, secret: str) -> CredentialCreated:
    return CredentialCreated(
        id=str(cred.id),
        agent_id=str(cred.agent_id),
        key_prefix=cred.key_prefix,
        secret=secret,
        scopes=list(cred.scopes or []),
        expires_at=cred.expires_at,
        created_by=str(cred.created_by) if cred.created_by else None,
        created_at=cred.created_at,
    )


@router.get("", response_model=AgentListOut)
def list_agents(
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    status: str | None = Query(default=None),
    state: str | None = Query(default=None),
    environment: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
) -> AgentListOut:
    require_capability(ctx, Capability.view)
    rows, next_cursor, has_more = service.list_agents(
        db,
        ctx,
        limit=limit,
        cursor=cursor,
        status=status,
        state=state,
        environment=environment,
        project_id=project_id,
    )
    return AgentListOut(
        items=[service.serialize_agent(db, a) for a in rows],
        page_info=PageInfo(next_cursor=next_cursor, limit=limit, has_more=has_more),
    )


@router.post("", response_model=AgentRegistryOut, status_code=status.HTTP_201_CREATED)
def register_agent(
    body: AgentCreate,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> AgentRegistryOut:
    require_capability(ctx, Capability.manage_agents)
    agent = service.register_agent(db, ctx, body)
    return service.serialize_agent(db, agent)


@router.get("/{agent_id}", response_model=AgentRegistryOut)
def get_agent(
    agent_id: str,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> AgentRegistryOut:
    require_capability(ctx, Capability.view)
    return service.serialize_agent(db, service.get_agent(db, ctx, agent_id))


@router.patch("/{agent_id}", response_model=AgentRegistryOut)
def update_agent(
    agent_id: str,
    body: AgentUpdate,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> AgentRegistryOut:
    require_capability(ctx, Capability.manage_agents)
    return service.serialize_agent(db, service.update_agent(db, ctx, agent_id, body))


@router.get("/{agent_id}/health", response_model=AgentHealthOut)
def get_agent_health(
    agent_id: str,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> AgentHealthOut:
    require_capability(ctx, Capability.view)
    return service.agent_health(db, ctx, agent_id)


@router.post(
    "/{agent_id}/credentials",
    response_model=CredentialCreated,
    status_code=status.HTTP_201_CREATED,
)
def create_credential(
    agent_id: str,
    body: CredentialCreate,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> CredentialCreated:
    require_capability(ctx, Capability.manage_agents)
    cred, secret = service.create_credential(db, ctx, agent_id, body)
    return _credential_created(cred, secret)


@router.post(
    "/{agent_id}/credentials/{credential_id}/rotate",
    response_model=CredentialCreated,
    status_code=status.HTTP_201_CREATED,
)
def rotate_credential(
    agent_id: str,
    credential_id: str,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> CredentialCreated:
    require_capability(ctx, Capability.manage_agents)
    cred, secret = service.rotate_credential(db, ctx, agent_id, credential_id)
    return _credential_created(cred, secret)


@router.delete(
    "/{agent_id}/credentials/{credential_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_credential(
    agent_id: str,
    credential_id: str,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> None:
    require_capability(ctx, Capability.manage_agents)
    service.revoke_credential(db, ctx, agent_id, credential_id)


@router.post("/{agent_id}/suspend", response_model=AgentRegistryOut)
def suspend_agent(
    agent_id: str,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> AgentRegistryOut:
    require_capability(ctx, Capability.manage_agents)
    return service.serialize_agent(db, service.set_status(db, ctx, agent_id, "suspended"))


@router.post("/{agent_id}/resume", response_model=AgentRegistryOut)
def resume_agent(
    agent_id: str,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> AgentRegistryOut:
    require_capability(ctx, Capability.manage_agents)
    return service.serialize_agent(db, service.set_status(db, ctx, agent_id, "active"))


@router.post("/{agent_id}/archive", response_model=AgentRegistryOut)
def archive_agent(
    agent_id: str,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> AgentRegistryOut:
    require_capability(ctx, Capability.manage_agents)
    return service.serialize_agent(db, service.set_status(db, ctx, agent_id, "archived"))
