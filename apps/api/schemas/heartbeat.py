"""Schéma d'ingest heartbeat (Contract D). Owner : `api` (M3)."""
from pydantic import BaseModel, Field


class HeartbeatIn(BaseModel):
    agent: str = Field(min_length=1)
    state: str  # idle|working|blocked|done|error (stale est dérivé serveur)
    project: str | None = None
    task: str | None = None
    progress: int | None = None
    tasks_done: int | None = None
    tasks_total: int | None = None
    module: str | None = None
    branch: str | None = None
    blocker: str | None = None
    meta: dict | None = None


class AgentDTO(BaseModel):
    """Représentation d'un agent diffusée en temps réel (Contract E)."""
    agent_key: str
    state: str
    task: str | None = None
    progress: int = 0
    module: str | None = None
    branch: str | None = None
    blocker: str | None = None
    project_id: str | None = None
    last_heartbeat: str | None = None
