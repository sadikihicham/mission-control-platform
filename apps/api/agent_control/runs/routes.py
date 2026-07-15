"""Routes de lecture des runs V1 (P4, SP3) — `/agent-control/v1/runs*`.

Trois routes, toutes en lecture (capacité `view` — cf. matrice figée §8) et
bornées au tenant du `HostContext` (résolu serveur, ADR-0003) :

- `GET /agent-control/v1/runs` : liste paginée (curseur), filtrable.
- `GET /agent-control/v1/runs/{id}` : détail du run + ses étapes.
- `GET /agent-control/v1/runs/{id}/timeline` : timeline d'audit paginée (redacted).

Les runs ne se **créent pas** par une route utilisateur : le contrat V1 figé (§8,
`ROUTE_CAPABILITIES`) n'expose aucun `POST /runs`. Un run naît de la **projection
des événements d'ingest** (`run.*` / `run.step.*`, agent authentifié par
credential) — le serveur fait foi sur les transitions. Ces routes exposent la
lecture auditable ; les commandes opérateur (`POST /runs/{id}/commands`) sont P5.

Les routes ne portent aucune logique métier : elles délèguent au service, qui
reçoit le `HostContext` et applique le bornage tenant + `require_capability`.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.agent_control.runs import service
from apps.api.agent_control.runs.schemas import (
    RunDetailOut,
    RunListOut,
    RunOut,
    RunTimelineOut,
    TimelineEntryOut,
)
from apps.api.core.agent_control_deps import get_host_context
from apps.api.core.db import get_db
from apps.api.integrations.capabilities import Capability
from apps.api.integrations.envelopes import PageInfo
from apps.api.integrations.host_context import HostContext
from apps.api.integrations.permissions import require_capability

router = APIRouter(prefix="/agent-control/v1/runs", tags=["agent-control-runs"])


@router.get("", response_model=RunListOut)
def list_runs(
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    agent_id: str | None = Query(default=None),
    state: str | None = Query(default=None),
) -> RunListOut:
    require_capability(ctx, Capability.view)
    rows, next_cursor, has_more = service.list_runs(
        db,
        ctx,
        limit=limit,
        cursor=cursor,
        project_id=project_id,
        agent_id=agent_id,
        state=state,
    )
    return RunListOut(
        items=[RunOut.model_validate(r) for r in rows],
        page_info=PageInfo(next_cursor=next_cursor, limit=limit, has_more=has_more),
    )


@router.get("/{run_id}", response_model=RunDetailOut)
def get_run(
    run_id: str,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
) -> RunDetailOut:
    require_capability(ctx, Capability.view)
    run = service.get_run(db, ctx, run_id)
    return RunDetailOut.model_validate(run)


@router.get("/{run_id}/timeline", response_model=RunTimelineOut)
def get_run_timeline(
    run_id: str,
    ctx: HostContext = Depends(get_host_context),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
) -> RunTimelineOut:
    require_capability(ctx, Capability.view)
    run, items, next_cursor, has_more = service.run_timeline(
        db, ctx, run_id, limit=limit, cursor=cursor
    )
    return RunTimelineOut(
        run_id=run.id,
        items=[TimelineEntryOut(**item) for item in items],
        page_info=PageInfo(next_cursor=next_cursor, limit=limit, has_more=has_more),
    )
