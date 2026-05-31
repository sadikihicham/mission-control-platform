"""Schémas projet → tâche → sous-tâche, avec agents.

Vue hiérarchique : la structure (projets/tâches/sous-tâches/affectations) vient
d'un seed issu de l'orchestration ; les TAUX et ÉTATS sont superposés en live
depuis les statuts du skill mission-control.
"""
from pydantic import BaseModel

from apps.api.schemas.agent import AgentOut


class SubTask(BaseModel):
    title: str
    progress: int            # 0..100, dérivé de tasks_done/total de l'agent
    state: str               # done|working|idle
    agent: str | None = None


class Task(BaseModel):
    id: str
    title: str
    module: str | None = None
    progress: int            # taux de réalisation de la tâche (= progress agent)
    state: str               # état dominant (= état de l'agent porteur)
    agents: list[AgentOut] = []   # agents affectés à la tâche
    subtasks: list[SubTask] = []


class ProjectSummary(BaseModel):
    id: str
    name: str
    description: str | None = None
    status: str              # in_dev|done|...
    progress: int            # taux global de réalisation
    tasks_total: int
    tasks_done: int
    agents_total: int
    agents_active: int
    agents_blocked: int
    editable: bool = False        # vrai pour les projets DB (CRUD), faux pour le seed
    repo: str | None = None       # dépôt GitHub "owner/name"


class ProjectDetail(ProjectSummary):
    tasks: list[Task] = []
    agents: list[AgentOut] = []   # tous les agents du projet (vue par agent)


class ProjectCreate(BaseModel):
    name: str
    slug: str | None = None
    description: str | None = None
    status: str = "proposed"
    repo: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    progress: int | None = None
    repo: str | None = None
