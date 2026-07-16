"""DTO du registre d'agents V1 — formes de contrat (§13, `agent_out`, `agent_create`,
`credential_created`). L'argent n'intervient pas ici. Datetimes sérialisés ISO.
"""
from datetime import datetime

from pydantic import BaseModel, Field

from apps.api.integrations.envelopes import PageInfo


class AgentOut(BaseModel):
    """Forme de sortie d'un agent du registre (contrat §13 `agent_out`)."""

    id: str
    agent_key: str
    installation_id: str
    display_name: str | None = None
    description: str | None = None
    runtime: str | None = None
    provider: str | None = None
    client_version: str | None = None
    environment: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    status: str            # registre : active|suspended|revoked|archived
    state: str             # live : idle|working|blocked|stale|done|error
    last_heartbeat: datetime | None = None
    last_sequence: int = 0
    registered_by: str | None = None
    registered_at: datetime | None = None
    revoked_at: datetime | None = None
    project_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AgentListOut(BaseModel):
    items: list[AgentOut]
    page_info: PageInfo


class AgentHealthOut(BaseModel):
    """Santé synthétique d'un agent (dérivée serveur, jamais du client)."""

    agent_key: str
    status: str
    state: str
    last_heartbeat: datetime | None = None
    seconds_since_heartbeat: int | None = None
    healthy: bool
    active_runs: int = 0
    open_alerts: int = 0


class AgentCreate(BaseModel):
    """Enregistrement d'un agent (`agent_create`) — `local_key` → `agent_key` dérivé.

    Le tenant n'est jamais accepté ici : `installation_id`/`installation_key`
    viennent du `HostContext` (résolu serveur, ADR-0003).
    """

    local_key: str = Field(min_length=1, max_length=80)
    display_name: str | None = Field(default=None, max_length=120)
    description: str | None = None
    runtime: str | None = Field(default=None, max_length=60)
    provider: str | None = Field(default=None, max_length=60)
    client_version: str | None = Field(default=None, max_length=60)
    environment: str | None = Field(default=None, max_length=40)
    capabilities: list[str] = Field(default_factory=list)


class AgentUpdate(BaseModel):
    """Mise à jour partielle des métadonnées de registre (jamais l'identité/clé)."""

    display_name: str | None = Field(default=None, max_length=120)
    description: str | None = None
    runtime: str | None = Field(default=None, max_length=60)
    provider: str | None = Field(default=None, max_length=60)
    client_version: str | None = Field(default=None, max_length=60)
    environment: str | None = Field(default=None, max_length=40)
    capabilities: list[str] | None = None


class CredentialCreate(BaseModel):
    """Émission d'un credential agent — scopes bornés, expiration optionnelle."""

    scopes: list[str] = Field(default_factory=lambda: ["ingest"])
    expires_at: datetime | None = None


class CredentialCreated(BaseModel):
    """Credential émis — le `secret` complet n'est renvoyé QU'UNE fois (§13)."""

    id: str
    agent_id: str
    key_prefix: str
    secret: str
    scopes: list[str]
    expires_at: datetime | None = None
    created_by: str | None = None
    created_at: datetime
