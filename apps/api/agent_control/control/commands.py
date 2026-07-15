"""File de commandes agent V1 (P5, SP3) — soumission, livraison, ACK, résultat.

Deux points de vue :

1. **Opérateur** (`submit_command`, capacité `operate`) : soumet une commande pour
   un run. La **politique applicable est évaluée** (moteur déterministe) avant
   toute création :
   - `deny` → aucune commande n'est créée (`permission_denied`) ;
   - `allow` → commande `queued` **libérée** (livrable immédiatement) ;
   - `require_approval` → commande `queued` **non libérée** + `approval_request`
     `pending` ; elle n'est livrée qu'après une décision positive (P5, cœur du gate).
   Idempotence par `(installation_id, idempotency_key)`.

2. **Agent** (`poll_commands` / `ack_command` / `submit_result`, credential agent,
   scope `commands`) : récupère ses commandes livrables (long poll borné,
   `queued → delivered`), les acquitte (`→ acknowledged`) et publie leur résultat
   (`→ succeeded|failed`). Machine `command` figée (§9), serveur autoritaire.

Toute mutation écrit l'outbox (`mc_outbox_events`) dans la MÊME transaction
(ADR-0005) — jamais de publication Redis directe avant commit.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, select, tuple_
from sqlalchemy.orm import Session

from apps.api.agent_control.control.policies import evaluate_policy
from apps.api.agent_control.control.schemas import CommandResultIn, CommandSubmit
from apps.api.agent_control.ingest.auth import AgentCredentialContext, require_scope
from apps.api.agent_control.runs import service as runs_service
from apps.api.core.config import settings
from apps.api.integrations.errors import (
    PermissionDenied,
    ResourceNotFound,
    StateConflict,
    ValidationFailed,
)
from apps.api.integrations.host_context import HostContext
from apps.api.integrations.state_machines import (
    CommandState,
    can_transition,
)
from apps.api.models import (
    Agent,
    AgentCommand,
    ApprovalRequest,
    MCOutboxEvent,
)

COMMANDS_SCOPE = "commands"

# Décodage curseur de pagination partagé (même schéma que les runs).
_encode_cursor = runs_service._encode_cursor
_decode_cursor = runs_service._decode_cursor


def _now() -> datetime:
    return datetime.now(UTC)


def _as_uuid(value):
    return runs_service._as_uuid(value)


def _tenant(ctx: HostContext) -> uuid.UUID | None:
    return _as_uuid(ctx.installation.id)


def _emit(
    db: Session,
    *,
    installation_id,
    event_type: str,
    topic: str,
    payload: dict,
) -> None:
    """Écrit un événement diffusable dans l'outbox (persistance avant publication)."""
    db.add(
        MCOutboxEvent(
            installation_id=installation_id,
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            topic=topic,
            payload=payload,
            status="pending",
        )
    )


def _command_topic(cmd: AgentCommand) -> str:
    return f"run:{cmd.run_id}" if cmd.run_id else f"agent:{cmd.agent_id}"


# --- Transition serveur-autoritative (machine `command` figée) ----------------


def transition_command(
    cmd: AgentCommand, new_state: CommandState, *, at: datetime | None = None
) -> None:
    """Applique `cmd.status → new_state` si la machine l'autorise, sinon `StateConflict`."""
    moment = at or _now()
    current = CommandState(cmd.status)
    if current == new_state:
        return  # idempotent : ré-annoncer l'état courant ne fait rien
    if not can_transition("command", current, new_state):
        raise StateConflict(
            f"transition commande interdite : {current.value} → {new_state.value}",
            details={"current": current.value, "requested": new_state.value},
        )
    cmd.status = new_state.value
    cmd.version += 1
    if new_state == CommandState.delivered:
        cmd.delivered_at = moment
    elif new_state == CommandState.acknowledged:
        cmd.acknowledged_at = moment
    elif new_state in (CommandState.succeeded, CommandState.failed):
        cmd.result_at = moment


# --- Soumission opérateur -----------------------------------------------------


@dataclass
class SubmitResult:
    command: AgentCommand
    created: bool  # False = rejeu idempotent d'une commande déjà soumise


def submit_command(
    db: Session, ctx: HostContext, run_id: str, body: CommandSubmit
) -> SubmitResult:
    """Soumet une commande pour un run — évalue la politique puis crée/refuse.

    Le run est borné au tenant (404 hors tenant). L'agent cible est celui du run.
    """
    run = runs_service.get_run(db, ctx, run_id)  # borne tenant + 404
    agent = db.get(Agent, run.agent_id)
    if agent is None:
        raise ResourceNotFound("agent du run introuvable", details={"run_id": run_id})

    tenant = _tenant(ctx)
    idem = body.idempotency_key or str(uuid.uuid4())

    # Idempotence : une soumission rejouée renvoie la commande existante (pas de doublon).
    existing = db.scalar(
        select(AgentCommand).where(
            AgentCommand.installation_id == tenant,
            AgentCommand.idempotency_key == idem,
        )
    )
    if existing is not None:
        return SubmitResult(command=existing, created=False)

    # Évaluation déterministe + auditée de la politique applicable.
    decision = evaluate_policy(
        db,
        ctx,
        agent=agent,
        command_type=body.command_type,
        project_id=run.project_id,
        audit_context={"run_id": str(run.id), "idempotency_key": idem},
    )
    if decision.effect == "deny":
        # Aucune commande n'est créée : la politique bloque à la source.
        db.commit()  # persiste l'audit de la décision
        raise PermissionDenied(
            "action refusée par la politique de gouvernance",
            details={"effect": "deny", "policy_id": str(decision.policy_id or "")},
        )

    now = _now()
    ttl = body.expires_in_seconds or settings.mc_command_default_ttl_seconds
    expires_at = now + timedelta(seconds=ttl)
    risk_level = decision.risk_level or body.risk_level

    cmd = AgentCommand(
        installation_id=tenant,
        agent_id=agent.id,
        run_id=run.id,
        command_type=body.command_type,
        payload=body.payload or {},
        status=CommandState.queued.value,
        idempotency_key=idem,
        requested_by=_as_uuid(ctx.user.local_user_id),
        policy_id=decision.policy_id,
        policy_effect=decision.effect,
        risk_level=risk_level,
        expires_at=expires_at,
    )

    if decision.effect == "require_approval":
        # Commande retenue : NON libérée tant qu'aucune décision positive n'existe.
        approval = ApprovalRequest(
            installation_id=tenant,
            project_id=run.project_id,
            task_id=run.task_id,
            run_id=run.id,
            agent_id=agent.id,
            policy_id=decision.policy_id,
            action_type=body.command_type,
            risk_level=risk_level or "medium",
            title=f"Approbation requise : {body.command_type}",
            context={"command_type": body.command_type, "run_id": str(run.id)},
            requested_by=_as_uuid(ctx.user.local_user_id),
            requested_by_agent=False,
            status="pending",
            expires_at=now + timedelta(seconds=settings.mc_approval_default_ttl_seconds),
        )
        db.add(approval)
        db.flush()  # matérialise l'id d'approbation pour le lier à la commande
        cmd.approval_request_id = approval.id
        cmd.released_at = None
        db.add(cmd)
        _emit(
            db,
            installation_id=tenant,
            event_type="approval.requested",
            topic="approvals",
            payload={
                "approval_id": str(approval.id),
                "run_id": str(run.id),
                "agent_id": str(agent.id),
                "action_type": body.command_type,
                "risk_level": approval.risk_level,
            },
        )
    else:
        # allow (explicite ou défaut) : commande livrable immédiatement.
        cmd.released_at = now
        db.add(cmd)
        _emit(
            db,
            installation_id=tenant,
            event_type="command.queued",
            topic=_command_topic(cmd),
            payload={
                "command_id": str(cmd.id),
                "agent_id": str(agent.id),
                "run_id": str(run.id),
                "command_type": body.command_type,
            },
        )

    db.commit()
    db.refresh(cmd)
    return SubmitResult(command=cmd, created=True)


# --- Lecture opérateur --------------------------------------------------------


def list_commands(
    db: Session,
    ctx: HostContext,
    *,
    limit: int = 50,
    cursor: str | None = None,
    run_id: str | None = None,
    agent_id: str | None = None,
    status: str | None = None,
) -> tuple[list[AgentCommand], str | None, bool]:
    """Liste paginée (curseur) des commandes du tenant, récence décroissante."""
    limit = max(1, min(limit, 200))
    stmt: Select = select(AgentCommand).where(AgentCommand.installation_id == _tenant(ctx))
    rid = _as_uuid(run_id)
    if rid is not None:
        stmt = stmt.where(AgentCommand.run_id == rid)
    aid = _as_uuid(agent_id)
    if aid is not None:
        stmt = stmt.where(AgentCommand.agent_id == aid)
    if status:
        stmt = stmt.where(AgentCommand.status == status)
    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded and len(decoded) == 2:
            c_created, c_id = decoded
            cid = _as_uuid(c_id)
            if cid is not None:
                stmt = stmt.where(
                    tuple_(AgentCommand.created_at, AgentCommand.id)
                    < (datetime.fromisoformat(c_created), cid)
                )
    stmt = stmt.order_by(AgentCommand.created_at.desc(), AgentCommand.id.desc()).limit(
        limit + 1
    )
    rows = list(db.scalars(stmt).all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = _encode_cursor(last.created_at.isoformat(), last.id)
    return rows, next_cursor, has_more


def get_command(db: Session, ctx: HostContext, command_id: str) -> AgentCommand:
    """Charge une commande bornée au tenant. 404 hors tenant/inexistante."""
    cid = _as_uuid(command_id)
    if cid is None:
        raise ResourceNotFound("commande introuvable", details={"command_id": command_id})
    cmd = db.scalar(
        select(AgentCommand).where(
            AgentCommand.id == cid, AgentCommand.installation_id == _tenant(ctx)
        )
    )
    if cmd is None:
        raise ResourceNotFound("commande introuvable", details={"command_id": command_id})
    return cmd


def cancel_command(db: Session, ctx: HostContext, command_id: str) -> AgentCommand:
    """Annule une commande opérateur encore livrable (`queued|delivered → cancelled`)."""
    cmd = get_command(db, ctx, command_id)
    transition_command(cmd, CommandState.cancelled)
    _emit(
        db,
        installation_id=cmd.installation_id,
        event_type="command.cancelled",
        topic=_command_topic(cmd),
        payload={"command_id": str(cmd.id), "reason": "operator_cancel"},
    )
    db.commit()
    db.refresh(cmd)
    return cmd


# --- Point de vue agent (credential, scope `commands`) ------------------------


def _expire_if_needed(db: Session, cmd: AgentCommand, *, now: datetime) -> bool:
    """Marque une commande dépassée `expired` (queued|delivered). Vrai si expirée."""
    if cmd.status in (CommandState.queued.value, CommandState.delivered.value) and cmd.is_expired(
        now=now
    ):
        transition_command(cmd, CommandState.expired, at=now)
        _emit(
            db,
            installation_id=cmd.installation_id,
            event_type="command.expired",
            topic=_command_topic(cmd),
            payload={"command_id": str(cmd.id)},
        )
        return True
    return False


def _deliverable_query(agent: Agent, now: datetime) -> Select:
    """Commandes livrables d'un agent : `queued`, libérées, non expirées."""
    return (
        select(AgentCommand)
        .where(
            AgentCommand.agent_id == agent.id,
            AgentCommand.installation_id == agent.installation_id,
            AgentCommand.status == CommandState.queued.value,
            AgentCommand.released_at.is_not(None),
        )
        .order_by(AgentCommand.created_at.asc(), AgentCommand.id.asc())
    )


def _fetch_and_deliver(db: Session, agent: Agent, limit: int) -> list[AgentCommand]:
    """Sélectionne les commandes livrables, expire les périmées, livre le reste."""
    now = _now()
    candidates = list(db.scalars(_deliverable_query(agent, now)).all())
    delivered: list[AgentCommand] = []
    for cmd in candidates:
        if _expire_if_needed(db, cmd, now=now):
            continue
        transition_command(cmd, CommandState.delivered, at=now)
        _emit(
            db,
            installation_id=cmd.installation_id,
            event_type="command.delivered",
            topic=_command_topic(cmd),
            payload={"command_id": str(cmd.id), "agent_id": str(agent.id)},
        )
        delivered.append(cmd)
        if len(delivered) >= limit:
            break
    if delivered or candidates:
        db.commit()
        for cmd in delivered:
            db.refresh(cmd)
    return delivered


def poll_commands(
    db: Session,
    ctx: AgentCredentialContext,
    *,
    limit: int = 20,
    wait_seconds: int | None = None,
) -> list[AgentCommand]:
    """Long poll borné : renvoie les commandes livrables de l'agent (les livre).

    Attend au plus `min(wait, MC_COMMAND_LONG_POLL_SECONDS)` qu'une commande
    devienne livrable, par petits intervalles. `wait=0` (défaut) → réponse
    immédiate. Le tenant/agent est dérivé du credential (jamais d'un body).
    """
    require_scope(ctx, COMMANDS_SCOPE)
    agent = ctx.agent
    limit = max(1, min(limit, 100))

    cap = settings.mc_command_long_poll_seconds
    budget = cap if wait_seconds is None else min(max(0, wait_seconds), cap)

    delivered = _fetch_and_deliver(db, agent, limit)
    deadline = time.monotonic() + budget
    while not delivered and time.monotonic() < deadline:
        time.sleep(min(0.5, max(0.0, deadline - time.monotonic())))
        db.expire_all()
        delivered = _fetch_and_deliver(db, agent, limit)

    ctx.credential.last_used_at = _now()
    db.commit()
    return delivered


def _agent_command_in_scope(
    db: Session, ctx: AgentCredentialContext, command_id: str
) -> AgentCommand:
    """Charge une commande **bornée à l'agent du credential** (jamais par id seul)."""
    cid = _as_uuid(command_id)
    if cid is None:
        raise ResourceNotFound("commande introuvable", details={"command_id": command_id})
    cmd = db.scalar(
        select(AgentCommand).where(
            AgentCommand.id == cid,
            AgentCommand.agent_id == ctx.agent.id,
            AgentCommand.installation_id == ctx.agent.installation_id,
        )
    )
    if cmd is None:
        raise ResourceNotFound("commande introuvable", details={"command_id": command_id})
    return cmd


def ack_command(
    db: Session, ctx: AgentCredentialContext, command_id: str
) -> AgentCommand:
    """L'agent accuse réception d'une commande (`delivered → acknowledged`)."""
    require_scope(ctx, COMMANDS_SCOPE)
    cmd = _agent_command_in_scope(db, ctx, command_id)
    transition_command(cmd, CommandState.acknowledged)
    _emit(
        db,
        installation_id=cmd.installation_id,
        event_type="command.acknowledged",
        topic=_command_topic(cmd),
        payload={"command_id": str(cmd.id)},
    )
    ctx.credential.last_used_at = _now()
    db.commit()
    db.refresh(cmd)
    return cmd


def submit_result(
    db: Session, ctx: AgentCredentialContext, command_id: str, body: CommandResultIn
) -> AgentCommand:
    """L'agent publie le résultat d'une commande (`acknowledged → succeeded|failed`)."""
    require_scope(ctx, COMMANDS_SCOPE)
    if body.status not in ("success", "failure"):
        raise ValidationFailed(
            f"statut de résultat invalide : {body.status}",
            details={"allowed": ["success", "failure"]},
        )
    cmd = _agent_command_in_scope(db, ctx, command_id)
    target = CommandState.succeeded if body.status == "success" else CommandState.failed
    transition_command(cmd, target)
    cmd.result_status = body.status
    cmd.result_payload = body.result_payload or {}
    cmd.error_message = (body.error_message or None) if body.status == "failure" else None
    _emit(
        db,
        installation_id=cmd.installation_id,
        event_type=f"command.{target.value}",
        topic=_command_topic(cmd),
        payload={"command_id": str(cmd.id), "result_status": body.status},
    )
    ctx.credential.last_used_at = _now()
    db.commit()
    db.refresh(cmd)
    return cmd
