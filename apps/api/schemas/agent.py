"""Schémas Pydantic exposés au front (sous-ensemble du Contract C/D).

Fast-path : ces formes sont servies à partir des fichiers de statut du skill
`mission-control`. Quand l'agent `api` (M3) livrera la version base de données,
ces schémas seront réutilisés tels quels.
"""
from pydantic import BaseModel


class AgentOut(BaseModel):
    agent: str
    state: str  # idle|working|blocked|done|error|stale
    task: str | None = None
    module: str | None = None
    label: str | None = None
    branch: str | None = None
    blocker: str | None = None
    progress: int = 0
    tasks_done: int | None = None
    tasks_total: int | None = None
    updated_at: str | None = None
    age_seconds: float | None = None


class ActivityOut(BaseModel):
    type: str
    state: str | None = None
    task: str | None = None
    progress: int | None = None
    created_at: str | None = None


class DashboardStats(BaseModel):
    agents_total: int = 0
    agents_active: int = 0   # working
    agents_blocked: int = 0
    agents_stale: int = 0
    agents_done: int = 0
    agents_error: int = 0
    overall_progress: int = 0
