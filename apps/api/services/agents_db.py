"""Lecture des agents depuis la DB (source unifiée). Remplace mc_source (fichiers)
pour alimenter le dashboard. Renvoie le même schéma AgentOut.
"""
from datetime import UTC, datetime

from sqlalchemy import select

from apps.api.core.db import get_sessionmaker
from apps.api.models import Agent
from apps.api.schemas.agent import AgentOut, DashboardStats

_ORDER = {"error": 0, "blocked": 1, "stale": 2, "working": 3, "idle": 4, "done": 5}


def _to_out(agent: Agent) -> AgentOut:
    meta = agent.meta or {}
    age = None
    if agent.last_heartbeat:
        lh = agent.last_heartbeat
        if lh.tzinfo is None:
            lh = lh.replace(tzinfo=UTC)
        age = (datetime.now(UTC) - lh).total_seconds()
    state = agent.state.value if hasattr(agent.state, "value") else str(agent.state)
    return AgentOut(
        agent=agent.agent_key,
        state=state,
        task=agent.task,
        module=agent.module,
        label=meta.get("label"),
        branch=agent.branch,
        blocker=agent.blocker,
        progress=agent.progress or 0,
        tasks_done=meta.get("tasks_done"),
        tasks_total=meta.get("tasks_total"),
        updated_at=agent.last_heartbeat.isoformat() if agent.last_heartbeat else None,
        age_seconds=age,
        token_issued_at=agent.token_issued_at.isoformat() if agent.token_issued_at else None,
    )


def list_agents() -> list[AgentOut]:
    session_factory = get_sessionmaker()
    with session_factory() as db:
        agents = [_to_out(a) for a in db.scalars(select(Agent)).all()]
    agents.sort(key=lambda a: (_ORDER.get(a.state, 9), a.agent))
    return agents


def dashboard_stats() -> DashboardStats:
    agents = list_agents()
    if not agents:
        return DashboardStats()
    by = lambda s: sum(1 for a in agents if a.state == s)  # noqa: E731
    return DashboardStats(
        agents_total=len(agents),
        agents_active=by("working"),
        agents_blocked=by("blocked"),
        agents_stale=by("stale"),
        agents_done=by("done"),
        agents_error=by("error"),
        overall_progress=round(sum(a.progress for a in agents) / len(agents)),
    )
