"""Router agents — lecture DB-backed (source unifiée).

Les agents proviennent de la table `agents`, alimentée par :
- le sync des fichiers du skill mission-control (services/mc_sync) ;
- les heartbeats `mc-platform` (routers/heartbeat).
"""
from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from apps.api.core.db import get_db
from apps.api.core.roles import Role
from apps.api.models import ActivityLog, Agent
from apps.api.routers.auth import require_role
from apps.api.schemas.agent import ActivityOut, AgentOut, DashboardStats
from apps.api.services import agents_db

# Lecture protégée : tout utilisateur authentifié (viewer minimum).
router = APIRouter(tags=["agents"], dependencies=[Depends(require_role(Role.viewer))])


@router.get("/agents", response_model=list[AgentOut])
def get_agents() -> list[AgentOut]:
    return agents_db.list_agents()


@router.get("/stats/dashboard", response_model=DashboardStats)
def get_dashboard_stats() -> DashboardStats:
    return agents_db.dashboard_stats()


@router.get("/agents/{agent_key}/activity", response_model=list[ActivityOut])
def get_agent_activity(agent_key: str, db: Session = Depends(get_db)) -> list[ActivityOut]:
    """Historique d'activité (heartbeats) d'un agent, le plus récent en premier."""
    agent = db.scalar(select(Agent).where(Agent.agent_key == agent_key))
    if not agent:
        return []
    rows = db.scalars(
        select(ActivityLog)
        .where(ActivityLog.agent_id == agent.id)
        .order_by(desc(ActivityLog.created_at))
        .limit(60)
    ).all()
    out: list[ActivityOut] = []
    for r in rows:
        p = r.payload or {}
        out.append(
            ActivityOut(
                type=r.type,
                state=p.get("state"),
                task=p.get("task"),
                progress=p.get("progress"),
                created_at=r.created_at.isoformat() if r.created_at else None,
            )
        )
    return out
