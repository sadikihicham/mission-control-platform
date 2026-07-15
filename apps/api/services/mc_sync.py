"""Sync des statuts du skill mission-control (fichiers) → table `agents` (DB).

Unifie les deux sources d'agents : les fichiers `mc` (agents d'orchestration)
et les heartbeats `mc-platform` écrivent désormais dans la MÊME table. Les champs
hors Contract A (`label`, `tasks_done`, `tasks_total`) sont stockés dans `meta`.
"""
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from apps.api.core.config import settings
from apps.api.models import ActivityLog, Agent, AgentState

# Sentinelle de provenance stockée dans `meta.source` (hors Contract A, jamais exposée par
# AgentOut) : distingue les agents synchronisés depuis les fichiers `mc` des agents DB-natifs
# créés par POST /agents/heartbeat (jamais taggués "mc-file" — heartbeat.py retire explicitement
# toute valeur "source" fournie par le client). Point de vérité unique plutôt qu'un literal
# dupliqué à l'écriture (sync_once) et à la lecture (purge, ci-dessous).
AGENT_SOURCE_MC_FILE = "mc-file"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def sync_once(db: Session) -> int:
    """Upsert chaque fichier de statut dans la DB, et purge les agents issus de
    fichiers `mc` désormais disparus. Renvoie le nb d'agents vus."""
    d = Path(settings.mc_status_dir)
    if not d.is_dir():
        return 0
    count = 0
    seen: set[str] = set()
    for f in sorted(d.glob("*.json")):
        try:
            raw = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        key = raw.get("agent")
        if not key:
            continue
        try:
            state = AgentState(raw.get("state", "idle"))
        except ValueError:
            state = AgentState.idle

        agent = db.scalar(select(Agent).where(Agent.agent_key == key))
        if agent is None:
            agent = Agent(agent_key=key)
            db.add(agent)

        agent.state = state
        agent.task = raw.get("task")
        agent.progress = int(raw.get("progress") or 0)
        agent.module = raw.get("module")
        agent.branch = raw.get("branch")
        agent.blocker = raw.get("blocker")
        agent.meta = {
            k: v
            for k, v in {
                "label": raw.get("label"),
                "tasks_done": raw.get("tasks_done"),
                "tasks_total": raw.get("tasks_total"),
                "source": AGENT_SOURCE_MC_FILE,
            }.items()
            if v is not None
        }
        hb = _parse_dt(raw.get("updated_at"))
        if hb:
            agent.last_heartbeat = hb
        seen.add(key)
        count += 1

    # Purge : agents issus d'un fichier mc qui n'existe plus (pas les agents
    # DB-natifs créés par heartbeat, dont meta.source != "mc-file").
    db.flush()
    for agent in db.scalars(select(Agent)).all():
        if (agent.meta or {}).get("source") == AGENT_SOURCE_MC_FILE and agent.agent_key not in seen:
            db.execute(
                update(ActivityLog).where(ActivityLog.agent_id == agent.id).values(agent_id=None)
            )
            db.delete(agent)

    db.commit()
    return count
