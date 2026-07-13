"""Ingest heartbeat (Contract D) → DB + publish Redis (Contract E).

Owner : `api` (M3). Producteur : `agent-cli` (M5). Consommateur : `realtime` (M4).
"""
import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core.config import settings
from apps.api.core.db import get_db
from apps.api.core.redis import publish_event
from apps.api.models import ActivityLog, Agent, AgentState, Project
from apps.api.schemas.heartbeat import AgentDTO, HeartbeatIn
from apps.api.services.events import publish_stats

router = APIRouter(tags=["ingest"])


def _to_dto(agent: Agent) -> dict:
    return AgentDTO(
        agent_key=agent.agent_key,
        state=agent.state.value if hasattr(agent.state, "value") else str(agent.state),
        task=agent.task,
        progress=agent.progress or 0,
        module=agent.module,
        branch=agent.branch,
        blocker=agent.blocker,
        project_id=str(agent.project_id) if agent.project_id else None,
        last_heartbeat=agent.last_heartbeat.isoformat() if agent.last_heartbeat else None,
    ).model_dump()


@router.post("/agents/heartbeat", status_code=status.HTTP_202_ACCEPTED)
def heartbeat(
    body: HeartbeatIn,
    x_mc_token: str | None = Header(default=None, alias="X-MC-Token"),
    db: Session = Depends(get_db),
) -> dict:
    if not secrets.compare_digest(x_mc_token or "", settings.mc_ingest_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "token d'ingest invalide")

    try:
        state = AgentState(body.state)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"état invalide: {body.state}") from exc
    if state == AgentState.stale:
        # `stale` est dérivé côté serveur (silence > seuil), jamais ingéré.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "état 'stale' non ingérable (dérivé serveur)")

    # Upsert par agent_key.
    agent = db.scalar(select(Agent).where(Agent.agent_key == body.agent))
    if agent is None:
        agent = Agent(agent_key=body.agent)
        db.add(agent)

    agent.state = state
    if body.task is not None:
        agent.task = body.task
    if body.progress is not None:
        agent.progress = body.progress
    if body.module is not None:
        agent.module = body.module
    if body.branch is not None:
        agent.branch = body.branch
    agent.blocker = body.blocker  # remis à None quand débloqué
    # tasks_done/total (hors Contract A) stockés dans meta, comme le sync mc.
    meta = dict(body.meta or {})
    if body.tasks_done is not None:
        meta["tasks_done"] = body.tasks_done
    if body.tasks_total is not None:
        meta["tasks_total"] = body.tasks_total
    if meta:
        agent.meta = meta
    agent.last_heartbeat = datetime.now(UTC)

    # Liaison projet par slug (optionnelle).
    if body.project:
        project = db.scalar(select(Project).where(Project.slug == body.project))
        if project:
            agent.project_id = project.id

    db.flush()  # assigne agent.id avant le log
    db.add(
        ActivityLog(
            agent_id=agent.id,
            project_id=agent.project_id,
            type="heartbeat",
            payload=body.model_dump(exclude_none=True),
        )
    )
    db.commit()
    db.refresh(agent)

    publish_event("agent.update", _to_dto(agent))
    publish_stats()
    return {"ok": True, "agent": agent.agent_key, "state": agent.state.value}
