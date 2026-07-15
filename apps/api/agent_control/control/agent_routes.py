"""Routes agent du contrôle P5 (SP3) — récupération de commandes, ACK, résultat.

Hors RBAC utilisateur : authentifiées par **credential agent** (matrice figée §8,
`AGENT_CREDENTIAL`, scope `commands`). Le tenant/agent est dérivé du credential,
jamais d'un body. Distinctes du data plane d'ingest (`/ingest/*`).

- `GET /agent/commands` : long poll borné (`MC_COMMAND_LONG_POLL_SECONDS`) — renvoie
  les commandes livrables de l'agent et les passe `queued → delivered`.
- `POST /agent/commands/{id}/ack` : `delivered → acknowledged`.
- `POST /agent/commands/{id}/result` : `acknowledged → succeeded|failed`.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.agent_control.control import commands as commands_service
from apps.api.agent_control.control.schemas import CommandListOut, CommandOut, CommandResultIn
from apps.api.agent_control.ingest.auth import (
    AgentCredentialContext,
    resolve_agent_credential,
)
from apps.api.core.db import get_db
from apps.api.integrations.envelopes import PageInfo

router = APIRouter(prefix="/agent-control/v1/agent", tags=["agent-control-agent-commands"])


@router.get("/commands", response_model=CommandListOut)
def poll_commands(
    ctx: AgentCredentialContext = Depends(resolve_agent_credential),
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    wait: int | None = Query(default=None, ge=0, le=60),
) -> CommandListOut:
    rows = commands_service.poll_commands(db, ctx, limit=limit, wait_seconds=wait)
    return CommandListOut(
        items=[CommandOut.model_validate(c) for c in rows],
        page_info=PageInfo(next_cursor=None, limit=limit, has_more=False),
    )


@router.post("/commands/{command_id}/ack", response_model=CommandOut)
def ack_command(
    command_id: str,
    ctx: AgentCredentialContext = Depends(resolve_agent_credential),
    db: Session = Depends(get_db),
) -> CommandOut:
    return CommandOut.model_validate(commands_service.ack_command(db, ctx, command_id))


@router.post("/commands/{command_id}/result", response_model=CommandOut)
def submit_result(
    command_id: str,
    body: CommandResultIn,
    ctx: AgentCredentialContext = Depends(resolve_agent_credential),
    db: Session = Depends(get_db),
) -> CommandOut:
    return CommandOut.model_validate(
        commands_service.submit_result(db, ctx, command_id, body)
    )
