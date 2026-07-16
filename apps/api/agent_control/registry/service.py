"""Plan de contrôle du registre d'agents V1 — tenant-scoped, fail-closed.

Toute requête est bornée à `installation_id` du `HostContext` (résolu serveur,
ADR-0003) : jamais de recherche par id seul. Un agent d'un autre tenant est un
404 (pas de fuite d'existence, §11). Les credentials sont hashés : le secret
complet n'existe qu'en transit, renvoyé une seule fois (ADR-0004).
"""
from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime

from sqlalchemy import Select, func, select, tuple_
from sqlalchemy.orm import Session

from apps.api.agent_control.registry.schemas import (
    AgentCreate,
    AgentHealthOut,
    AgentOut,
    AgentUpdate,
    CredentialCreate,
)
from apps.api.core.config import settings
from apps.api.core.security import generate_agent_credential
from apps.api.integrations.errors import Conflict, ResourceNotFound, ValidationFailed
from apps.api.integrations.host_context import HostContext
from apps.api.models import (
    Agent,
    AgentAlert,
    AgentCredential,
    AgentProjectAssignment,
    AgentRun,
)

_REGISTRY_STATUSES = frozenset({"active", "suspended", "revoked", "archived"})
_LIVE_RUN_STATES = frozenset(
    {"queued", "starting", "running", "waiting_approval", "blocked"}
)


def _now() -> datetime:
    return datetime.now(UTC)


def _as_uuid(value) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _scoped(ctx: HostContext) -> uuid.UUID | None:
    return _as_uuid(ctx.installation.id)


def _encode_cursor(*parts) -> str:
    raw = "|".join(str(p) for p in parts)
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> list[str] | None:
    try:
        return base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
    except (ValueError, TypeError):
        return None


def _stale_seconds() -> int:
    return int(getattr(settings, "mc_stale_seconds", 30) or 30)


# --- Sérialisation ------------------------------------------------------------


def _project_ids(db: Session, agent: Agent) -> list[str]:
    """Ids projets liés à l'agent : affectations actives + projet legacy direct."""
    ids: list[str] = []
    seen: set[uuid.UUID] = set()
    if agent.project_id is not None:
        seen.add(agent.project_id)
        ids.append(str(agent.project_id))
    rows = db.scalars(
        select(AgentProjectAssignment.project_id).where(
            AgentProjectAssignment.agent_id == agent.id,
            AgentProjectAssignment.status == "active",
        )
    ).all()
    for pid in rows:
        if pid is not None and pid not in seen:
            seen.add(pid)
            ids.append(str(pid))
    return ids


def serialize_agent(db: Session, agent: Agent) -> AgentOut:
    """Projette un `Agent` ORM vers le DTO de contrat `agent_out`."""
    state = agent.state.value if hasattr(agent.state, "value") else str(agent.state)
    created = agent.registered_at or agent.updated_at
    return AgentOut(
        id=str(agent.id),
        agent_key=agent.agent_key,
        installation_id=str(agent.installation_id) if agent.installation_id else "",
        display_name=agent.display_name,
        description=agent.description,
        runtime=agent.runtime,
        provider=agent.provider,
        client_version=agent.client_version,
        environment=agent.environment,
        capabilities=list(agent.capabilities or []),
        status=agent.status,
        state=state,
        last_heartbeat=agent.last_heartbeat,
        last_sequence=agent.last_sequence or 0,
        registered_by=str(agent.registered_by) if agent.registered_by else None,
        registered_at=agent.registered_at,
        revoked_at=agent.revoked_at,
        project_ids=_project_ids(db, agent),
        created_at=created,
        updated_at=agent.updated_at,
    )


# --- Lecture tenant-scoped ----------------------------------------------------


def list_agents(
    db: Session,
    ctx: HostContext,
    *,
    limit: int = 50,
    cursor: str | None = None,
    status: str | None = None,
    state: str | None = None,
    environment: str | None = None,
    project_id: str | None = None,
) -> tuple[list[Agent], str | None, bool]:
    """Liste paginée (curseur) des agents V1 du tenant, récence décroissante."""
    limit = max(1, min(limit, 200))
    stmt: Select = select(Agent).where(Agent.installation_id == _scoped(ctx))
    if status:
        stmt = stmt.where(Agent.status == status)
    if state:
        stmt = stmt.where(Agent.state == state)
    if environment:
        stmt = stmt.where(Agent.environment == environment)
    pid = _as_uuid(project_id)
    if pid is not None:
        stmt = stmt.where(
            Agent.id.in_(
                select(AgentProjectAssignment.agent_id).where(
                    AgentProjectAssignment.project_id == pid,
                    AgentProjectAssignment.status == "active",
                )
            )
        )
    order_key = func.coalesce(Agent.registered_at, Agent.updated_at)
    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded and len(decoded) == 2:
            c_created, c_id = decoded
            cid = _as_uuid(c_id)
            if cid is not None:
                stmt = stmt.where(
                    tuple_(order_key, Agent.id)
                    < (datetime.fromisoformat(c_created), cid)
                )
    stmt = stmt.order_by(order_key.desc(), Agent.id.desc()).limit(limit + 1)
    rows = list(db.scalars(stmt).all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        key = (last.registered_at or last.updated_at).isoformat()
        next_cursor = _encode_cursor(key, last.id)
    return rows, next_cursor, has_more


def get_agent(db: Session, ctx: HostContext, agent_id: str) -> Agent:
    """Charge un agent borné au tenant. 404 hors tenant/inexistant."""
    aid = _as_uuid(agent_id)
    if aid is None:
        raise ResourceNotFound("agent introuvable", details={"agent_id": agent_id})
    agent = db.scalar(
        select(Agent).where(Agent.id == aid, Agent.installation_id == _scoped(ctx))
    )
    if agent is None:
        raise ResourceNotFound("agent introuvable", details={"agent_id": agent_id})
    return agent


def agent_health(db: Session, ctx: HostContext, agent_id: str) -> AgentHealthOut:
    """Santé dérivée serveur d'un agent (jamais fournie par le client)."""
    agent = get_agent(db, ctx, agent_id)
    now = _now()
    secs = None
    if agent.last_heartbeat is not None:
        secs = int((now - agent.last_heartbeat).total_seconds())
    state = agent.state.value if hasattr(agent.state, "value") else str(agent.state)
    healthy = (
        agent.status == "active"
        and state not in ("stale", "error", "blocked")
        and (secs is None or secs <= _stale_seconds())
    )
    active_runs = db.scalar(
        select(func.count(AgentRun.id)).where(
            AgentRun.agent_id == agent.id,
            AgentRun.installation_id == _scoped(ctx),
            AgentRun.state.in_(_LIVE_RUN_STATES),
        )
    ) or 0
    open_alerts = db.scalar(
        select(func.count(AgentAlert.id)).where(
            AgentAlert.installation_id == _scoped(ctx),
            AgentAlert.target_type == "agent",
            AgentAlert.target_id == agent.id,
            AgentAlert.status != "resolved",
        )
    ) or 0
    return AgentHealthOut(
        agent_key=agent.agent_key,
        status=agent.status,
        state=state,
        last_heartbeat=agent.last_heartbeat,
        seconds_since_heartbeat=secs,
        healthy=healthy,
        active_runs=int(active_runs),
        open_alerts=int(open_alerts),
    )


# --- Mutations (manage_agents) ------------------------------------------------


def register_agent(db: Session, ctx: HostContext, body: AgentCreate) -> Agent:
    """Enregistre un agent V1 dans le tenant courant. `agent_key` dérivé (ADR-0006)."""
    local_key = body.local_key.strip()
    if not local_key or ":" in local_key:
        raise ValidationFailed(
            "local_key invalide (non vide, sans ':')",
            details={"local_key": body.local_key},
        )
    agent_key = f"{ctx.installation.installation_key}:{local_key}"
    if db.scalar(select(Agent.id).where(Agent.agent_key == agent_key)) is not None:
        raise Conflict(
            "un agent porte déjà cette clé", details={"agent_key": agent_key}
        )
    local_user = _as_uuid(ctx.user.local_user_id)
    agent = Agent(
        agent_key=agent_key,
        installation_id=_scoped(ctx),
        display_name=body.display_name or local_key,
        description=body.description,
        runtime=body.runtime,
        provider=body.provider,
        client_version=body.client_version,
        environment=body.environment,
        capabilities=list(body.capabilities or []),
        status="active",
        registered_by=local_user,
        registered_at=_now(),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def update_agent(db: Session, ctx: HostContext, agent_id: str, body: AgentUpdate) -> Agent:
    agent = get_agent(db, ctx, agent_id)
    data = body.model_dump(exclude_unset=True)
    for field in (
        "display_name",
        "description",
        "runtime",
        "provider",
        "client_version",
        "environment",
    ):
        if field in data:
            setattr(agent, field, data[field])
    if "capabilities" in data and data["capabilities"] is not None:
        agent.capabilities = list(data["capabilities"])
    db.commit()
    db.refresh(agent)
    return agent


def set_status(db: Session, ctx: HostContext, agent_id: str, new_status: str) -> Agent:
    """Applique une transition de statut REGISTRE (suspend/resume/archive)."""
    if new_status not in _REGISTRY_STATUSES:
        raise ValidationFailed("statut de registre invalide", details={"status": new_status})
    agent = get_agent(db, ctx, agent_id)
    if new_status == "archived":
        agent.revoked_at = agent.revoked_at or _now()
    if new_status == "active":
        agent.revoked_at = None
    agent.status = new_status
    db.commit()
    db.refresh(agent)
    return agent


# --- Credentials --------------------------------------------------------------


def create_credential(
    db: Session, ctx: HostContext, agent_id: str, body: CredentialCreate
) -> tuple[AgentCredential, str]:
    """Émet un credential agent. Retourne `(credential, secret_complet)`.

    Le secret complet n'est renvoyé qu'ici, une seule fois : seul son hash est
    persisté (ADR-0004).
    """
    agent = get_agent(db, ctx, agent_id)
    if agent.status in ("revoked", "archived"):
        raise Conflict(
            "agent inactif : credential refusé", details={"status": agent.status}
        )
    key_prefix, secret, secret_hash = generate_agent_credential()
    cred = AgentCredential(
        agent_id=agent.id,
        key_prefix=key_prefix,
        secret_hash=secret_hash,
        scopes=list(body.scopes or []),
        expires_at=body.expires_at,
        created_by=_as_uuid(ctx.user.local_user_id),
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    return cred, secret


def _get_credential(
    db: Session, agent: Agent, credential_id: str
) -> AgentCredential:
    cid = _as_uuid(credential_id)
    if cid is None:
        raise ResourceNotFound("credential introuvable", details={"credential_id": credential_id})
    cred = db.scalar(
        select(AgentCredential).where(
            AgentCredential.id == cid, AgentCredential.agent_id == agent.id
        )
    )
    if cred is None:
        raise ResourceNotFound("credential introuvable", details={"credential_id": credential_id})
    return cred


def rotate_credential(
    db: Session, ctx: HostContext, agent_id: str, credential_id: str
) -> tuple[AgentCredential, str]:
    """Rotation : révoque l'ancien credential et en émet un nouveau (ADR-0004)."""
    agent = get_agent(db, ctx, agent_id)
    old = _get_credential(db, agent, credential_id)
    if old.revoked_at is None:
        old.revoked_at = _now()
    key_prefix, secret, secret_hash = generate_agent_credential()
    cred = AgentCredential(
        agent_id=agent.id,
        key_prefix=key_prefix,
        secret_hash=secret_hash,
        scopes=list(old.scopes or []),
        expires_at=old.expires_at,
        created_by=_as_uuid(ctx.user.local_user_id),
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    return cred, secret


def revoke_credential(
    db: Session, ctx: HostContext, agent_id: str, credential_id: str
) -> None:
    """Révoque un credential (terminal immédiat, sans période de grâce)."""
    agent = get_agent(db, ctx, agent_id)
    cred = _get_credential(db, agent, credential_id)
    if cred.revoked_at is None:
        cred.revoked_at = _now()
    db.commit()
