"""Demandes d'approbation V1 (P5, SP3) — décision versionnée, anti-double décision.

Une commande soumise à `require_approval` reste `queued` non libérée tant qu'une
décision **positive** n'existe pas. La décision (`approve`/`reject`) est protégée
par un **verrou optimiste** : la transition `pending → approved|rejected` passe par
un UPDATE conditionnel atomique `WHERE status='pending' AND version=:expected`.
Deux décisions concurrentes → une seule gagne (rowcount=1), l'autre est refusée
(`state_conflict`). C'est le cœur du Gate P5 (« pas de double décision »).

- **approve** → l'approbation passe `approved` ET la commande liée est **libérée**
  (`released_at` posé) : elle devient livrable à l'agent.
- **reject** → l'approbation passe `rejected` ET la commande liée est **annulée**
  (`queued → cancelled`) : elle ne sera jamais livrée.

Tenant `installation_id` résolu serveur (ADR-0003) ; aucune recherche par ID seul.
Toute mutation écrit l'outbox dans la même transaction (ADR-0005).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Select, select, tuple_, update
from sqlalchemy.orm import Session

from apps.api.agent_control.control.commands import _command_topic, _emit, transition_command
from apps.api.agent_control.control.schemas import ApprovalDecisionIn
from apps.api.agent_control.runs import service as runs_service
from apps.api.integrations.errors import ResourceNotFound, StateConflict
from apps.api.integrations.host_context import HostContext
from apps.api.integrations.state_machines import ApprovalState, CommandState
from apps.api.models import AgentCommand, ApprovalRequest

_encode_cursor = runs_service._encode_cursor
_decode_cursor = runs_service._decode_cursor


def _now() -> datetime:
    return datetime.now(UTC)


def _as_uuid(value):
    return runs_service._as_uuid(value)


def _tenant(ctx: HostContext) -> uuid.UUID | None:
    return _as_uuid(ctx.installation.id)


def list_approvals(
    db: Session,
    ctx: HostContext,
    *,
    limit: int = 50,
    cursor: str | None = None,
    status: str | None = None,
) -> tuple[list[ApprovalRequest], str | None, bool]:
    """Liste paginée (curseur) des approbations du tenant, récence décroissante."""
    limit = max(1, min(limit, 200))
    stmt: Select = select(ApprovalRequest).where(
        ApprovalRequest.installation_id == _tenant(ctx)
    )
    if status:
        stmt = stmt.where(ApprovalRequest.status == status)
    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded and len(decoded) == 2:
            c_created, c_id = decoded
            cid = _as_uuid(c_id)
            if cid is not None:
                stmt = stmt.where(
                    tuple_(ApprovalRequest.created_at, ApprovalRequest.id)
                    < (datetime.fromisoformat(c_created), cid)
                )
    stmt = stmt.order_by(
        ApprovalRequest.created_at.desc(), ApprovalRequest.id.desc()
    ).limit(limit + 1)
    rows = list(db.scalars(stmt).all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = _encode_cursor(last.created_at.isoformat(), last.id)
    return rows, next_cursor, has_more


def get_approval(db: Session, ctx: HostContext, approval_id: str) -> ApprovalRequest:
    """Charge une approbation bornée au tenant. 404 hors tenant/inexistante."""
    aid = _as_uuid(approval_id)
    if aid is None:
        raise ResourceNotFound("approbation introuvable", details={"approval_id": approval_id})
    approval = db.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.id == aid,
            ApprovalRequest.installation_id == _tenant(ctx),
        )
    )
    if approval is None:
        raise ResourceNotFound(
            "approbation introuvable", details={"approval_id": approval_id}
        )
    return approval


def _linked_command(db: Session, approval: ApprovalRequest) -> AgentCommand | None:
    """Commande retenue par cette approbation (lien `approval_request_id`)."""
    return db.scalar(
        select(AgentCommand).where(AgentCommand.approval_request_id == approval.id)
    )


def _decide(
    db: Session,
    ctx: HostContext,
    approval_id: str,
    body: ApprovalDecisionIn,
    *,
    target: ApprovalState,
) -> ApprovalRequest:
    """Applique une décision (`approve`/`reject`) avec verrou optimiste atomique."""
    approval = get_approval(db, ctx, approval_id)

    # Pré-garde rapide (fail-fast) : seule une demande `pending` est décidable.
    if approval.status != ApprovalState.pending.value:
        raise StateConflict(
            "approbation déjà décidée ou clôturée",
            details={"current": approval.status},
        )
    # SLA : une demande expirée ne peut plus être décidée (fail-closed).
    if approval.is_expired():
        _expire(db, approval)
        db.commit()
        raise StateConflict(
            "approbation expirée (SLA dépassé)",
            details={"current": ApprovalState.expired.value},
        )

    now = _now()
    decided_by = _as_uuid(ctx.user.local_user_id)
    # UPDATE conditionnel atomique : la version attendue ET l'état pending doivent
    # tenir. Une décision concurrente aura déjà incrémenté `version` → rowcount 0.
    result = db.execute(
        update(ApprovalRequest)
        .where(
            ApprovalRequest.id == approval.id,
            ApprovalRequest.installation_id == _tenant(ctx),
            ApprovalRequest.status == ApprovalState.pending.value,
            ApprovalRequest.version == body.version,
        )
        .values(
            status=target.value,
            version=ApprovalRequest.version + 1,
            decided_at=now,
            decision_by=decided_by,
            decision_comment=body.comment,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 0:
        # Version périmée ou décision déjà prise par un autre opérateur (concurrence).
        db.rollback()
        raise StateConflict(
            "décision concurrente ou version d'approbation périmée",
            details={"expected_version": body.version},
        )

    # Libère (approve) ou annule (reject) la commande retenue par cette approbation.
    cmd = _linked_command(db, approval)
    if target == ApprovalState.approved:
        if cmd is not None and cmd.status == CommandState.queued.value:
            cmd.released_at = now
            _emit(
                db,
                installation_id=cmd.installation_id,
                event_type="command.queued",
                topic=_command_topic(cmd),
                payload={
                    "command_id": str(cmd.id),
                    "agent_id": str(cmd.agent_id),
                    "released": True,
                },
            )
        event_type = "approval.approved"
    else:
        if cmd is not None and cmd.status == CommandState.queued.value:
            transition_command(cmd, CommandState.cancelled, at=now)
            _emit(
                db,
                installation_id=cmd.installation_id,
                event_type="command.cancelled",
                topic=_command_topic(cmd),
                payload={"command_id": str(cmd.id), "reason": "approval_rejected"},
            )
        event_type = "approval.rejected"

    _emit(
        db,
        installation_id=_tenant(ctx),
        event_type=event_type,
        topic="approvals",
        payload={
            "approval_id": str(approval.id),
            "decision_by": str(decided_by) if decided_by else None,
        },
    )
    db.commit()
    db.refresh(approval)
    return approval


def approve(
    db: Session, ctx: HostContext, approval_id: str, body: ApprovalDecisionIn
) -> ApprovalRequest:
    """Approuve une demande : libère la commande retenue (verrou optimiste)."""
    return _decide(db, ctx, approval_id, body, target=ApprovalState.approved)


def reject(
    db: Session, ctx: HostContext, approval_id: str, body: ApprovalDecisionIn
) -> ApprovalRequest:
    """Rejette une demande : annule la commande retenue (verrou optimiste)."""
    return _decide(db, ctx, approval_id, body, target=ApprovalState.rejected)


def _expire(db: Session, approval: ApprovalRequest) -> None:
    """Marque une demande `expired` et annule la commande retenue (fail-closed)."""
    db.execute(
        update(ApprovalRequest)
        .where(
            ApprovalRequest.id == approval.id,
            ApprovalRequest.status == ApprovalState.pending.value,
        )
        .values(status=ApprovalState.expired.value, version=ApprovalRequest.version + 1)
        .execution_options(synchronize_session=False)
    )
    cmd = _linked_command(db, approval)
    if cmd is not None and cmd.status == CommandState.queued.value:
        transition_command(cmd, CommandState.cancelled)
        _emit(
            db,
            installation_id=cmd.installation_id,
            event_type="command.cancelled",
            topic=_command_topic(cmd),
            payload={"command_id": str(cmd.id), "reason": "approval_expired"},
        )
