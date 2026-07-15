"""Routes d'ingest V1 (contrat §8) — authentifiées par credential agent.

`POST /agent-control/v1/ingest/events` : batch borné, séquencé, idempotent.
`POST /agent-control/v1/ingest/heartbeat` : projection agent monotone, tenant-aware.

Ces routes sont hors RBAC utilisateur : l'auth est le credential agent
(`AGENT_CREDENTIAL` dans la matrice de permissions). Le tenant/agent est dérivé
du credential. Les erreurs suivent l'enveloppe V1 (`HostIntegrationError` →
handler global). Distinct du heartbeat V0 `POST /agents/heartbeat` (Contract D),
qui reste inchangé.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.agent_control.ingest import service
from apps.api.agent_control.ingest.auth import (
    AgentCredentialContext,
    resolve_agent_credential,
)
from apps.api.agent_control.ingest.schemas import (
    IngestEventsRequest,
    IngestEventsResponse,
    IngestHeartbeatResponse,
    IngestHeartbeatV1,
)
from apps.api.core.db import get_db

router = APIRouter(prefix="/agent-control/v1/ingest", tags=["agent-control-ingest"])


@router.post("/events", response_model=IngestEventsResponse)
def ingest_events(
    request: IngestEventsRequest,
    ctx: AgentCredentialContext = Depends(resolve_agent_credential),
    db: Session = Depends(get_db),
) -> IngestEventsResponse:
    return service.ingest_events(db, ctx, request)


@router.post("/heartbeat", response_model=IngestHeartbeatResponse)
def ingest_heartbeat(
    body: IngestHeartbeatV1,
    ctx: AgentCredentialContext = Depends(resolve_agent_credential),
    db: Session = Depends(get_db),
) -> IngestHeartbeatResponse:
    return service.ingest_heartbeat_v1(db, ctx, body)
