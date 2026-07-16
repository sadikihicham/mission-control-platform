"""DTO des projets & tâches V1 (P8).

Formes de sortie/entrée des routes `/agent-control/v1/projects*` et `/tasks*`.
Le tenant (`installation_id`) n'est **jamais** accepté en entrée : il vient du
`HostContext` (résolu serveur, ADR-0003). Noms préfixés `Ac*` pour ne pas entrer
en collision avec les DTO V0 (`ProjectCreate`/`ProjectUpdate`/`Task`/`SubTask`),
qui restent la surface V0 intacte.
"""
from datetime import datetime

from pydantic import BaseModel, Field

from apps.api.integrations.envelopes import PageInfo


class AcProjectOut(BaseModel):
    """Projet V1 tenant-scoped (contrat P8). `installation_id` = tenant courant."""

    id: str
    installation_id: str
    slug: str
    name: str
    description: str | None = None
    status: str
    progress: int = 0
    repo: str | None = None
    is_seed: bool = False
    task_count: int = 0
    created_at: datetime
    updated_at: datetime


class AcProjectListOut(BaseModel):
    items: list[AcProjectOut]
    page_info: PageInfo


class AcProjectCreate(BaseModel):
    """Création d'un projet V1. Le `slug` est dérivé serveur si absent (unicité
    globale garantie) ; le tenant vient du contexte, jamais du body."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    slug: str | None = Field(default=None, max_length=120)
    status: str | None = Field(default=None)
    repo: str | None = Field(default=None, max_length=255)


class AcProjectUpdate(BaseModel):
    """Mise à jour partielle d'un projet V1 (jamais l'identité/tenant)."""

    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    status: str | None = None
    progress: int | None = Field(default=None, ge=0, le=100)
    repo: str | None = Field(default=None, max_length=255)


class AcTaskOut(BaseModel):
    """Tâche/sous-tâche V1 tenant-scoped. `parent_id` non nul = sous-tâche."""

    id: str
    installation_id: str
    project_id: str
    parent_id: str | None = None
    agent_id: str | None = None
    code: str | None = None
    title: str
    module: str | None = None
    status: str
    progress: int = 0
    position: int = 0
    agent_key: str | None = None
    created_at: datetime
    updated_at: datetime


class AcTaskListOut(BaseModel):
    items: list[AcTaskOut]
    page_info: PageInfo


class AcTaskCreate(BaseModel):
    """Création d'une tâche/sous-tâche dans un projet du tenant courant."""

    title: str = Field(min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=40)
    module: str | None = Field(default=None, max_length=120)
    parent_id: str | None = None
    agent_key: str | None = Field(default=None, max_length=120)
    status: str | None = Field(default=None, max_length=50)
    position: int | None = Field(default=None, ge=0)


class AcTaskUpdate(BaseModel):
    """Mise à jour partielle d'une tâche V1 (jamais le projet/tenant)."""

    title: str | None = Field(default=None, max_length=255)
    module: str | None = Field(default=None, max_length=120)
    status: str | None = Field(default=None, max_length=50)
    progress: int | None = Field(default=None, ge=0, le=100)
    position: int | None = Field(default=None, ge=0)
    agent_key: str | None = Field(default=None, max_length=120)


class AcTaskAssign(BaseModel):
    """Affectation d'un agent (du tenant) à une tâche. `agent_id` OU `agent_key`."""

    agent_id: str | None = None
    agent_key: str | None = Field(default=None, max_length=120)
