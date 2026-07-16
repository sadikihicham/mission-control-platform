"""Consommation et coûts — enregistrement idempotent, agrégats réconciliables (P6).

Un enregistrement de consommation naît d'un événement d'ingest `usage.recorded`
(l'agent rapporte tokens/appels/durée ; le **serveur** fait foi sur le coût, qu'il
calcule en `Decimal` via la grille versionnée — jamais un coût fourni par le
client). Idempotence par `(installation_id, source_event_id)` : rejouer le batch
ne double jamais la consommation. Conséquence directe du Gate P6 : la **somme**
des `agent_usage_records` d'un tenant est toujours cohérente avec les agrégats
exposés par `/usage` (réconciliation), puisqu'ils lisent la même source.

Ce module ne dépend PAS des budgets (évités les imports circulaires) : l'ingest
enchaîne `record_usage` puis l'évaluation budget. `record_usage` ne commit pas.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Select, func, select, tuple_
from sqlalchemy.orm import Session

from apps.api.agent_control.operations import pricing
from apps.api.agent_control.operations.outbox import emit_outbox
from apps.api.integrations.host_context import HostContext
from apps.api.models import AgentUsageRecord


def _as_uuid(value) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def record_usage(
    db: Session,
    *,
    installation_id,
    agent_id,
    source_event_id: str,
    occurred_at: datetime,
    project_id=None,
    run_id=None,
    provider: str | None = None,
    model: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    calls: int = 1,
    duration_ms: int | None = None,
    pricing_version: str | None = None,
) -> tuple[AgentUsageRecord, bool]:
    """Enregistre une consommation et son coût `Decimal`. Idempotent, sans commit.

    Renvoie `(record, created)`. `created=False` = rejeu idempotent (même
    `source_event_id`) → l'enregistrement existant est renvoyé, aucun double
    comptage. Le coût est calculé serveur (grille versionnée), jamais reçu du client.
    """
    inst = _as_uuid(installation_id)
    existing = db.scalar(
        select(AgentUsageRecord).where(
            AgentUsageRecord.installation_id == inst,
            AgentUsageRecord.source_event_id == source_event_id,
        )
    )
    if existing is not None:
        return existing, False

    in_tok = _int(input_tokens)
    out_tok = _int(output_tokens)
    breakdown = pricing.compute_cost(
        input_tokens=in_tok,
        output_tokens=out_tok,
        provider=provider,
        model=model,
        pricing_version=pricing_version,
    )
    record = AgentUsageRecord(
        installation_id=inst,
        agent_id=_as_uuid(agent_id),
        project_id=_as_uuid(project_id),
        run_id=_as_uuid(run_id),
        provider=provider,
        model=model,
        input_tokens=in_tok,
        output_tokens=out_tok,
        total_tokens=in_tok + out_tok,
        calls=_int(calls, 1),
        duration_ms=duration_ms if duration_ms is None else _int(duration_ms),
        currency=breakdown.currency,
        unit_cost_input=breakdown.unit_cost_input,
        unit_cost_output=breakdown.unit_cost_output,
        cost=breakdown.cost,
        pricing_version=breakdown.pricing_version,
        source_event_id=source_event_id,
        occurred_at=occurred_at,
    )
    db.add(record)
    db.flush()
    emit_outbox(
        db,
        installation_id=inst,
        event_type="usage.recorded",
        topic=f"run:{record.run_id}" if record.run_id else f"agent:{record.agent_id}",
        payload={
            "usage_id": str(record.id),
            "agent_id": str(record.agent_id),
            "run_id": str(record.run_id) if record.run_id else None,
            "cost": str(record.cost),
            "currency": record.currency,
            "total_tokens": record.total_tokens,
            "pricing_version": record.pricing_version,
        },
    )
    return record, True


# --- Consommation et agrégats (réconciliables) --------------------------------


def consumption_for(
    db: Session,
    installation_id,
    *,
    scope_type: str = "installation",
    scope_id=None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> Decimal:
    """Somme `Decimal` des coûts d'une portée/fenêtre — source des budgets.

    `installation` : tout le tenant ; `project` : `project_id == scope_id` ;
    `agent` : `agent_id == scope_id`. Toujours borné au tenant. Renvoie `0` si
    aucune consommation (jamais `None`).
    """
    inst = _as_uuid(installation_id)
    stmt = select(func.coalesce(func.sum(AgentUsageRecord.cost), 0)).where(
        AgentUsageRecord.installation_id == inst
    )
    if scope_type == "project" and scope_id is not None:
        stmt = stmt.where(AgentUsageRecord.project_id == _as_uuid(scope_id))
    elif scope_type == "agent" and scope_id is not None:
        stmt = stmt.where(AgentUsageRecord.agent_id == _as_uuid(scope_id))
    if since is not None:
        stmt = stmt.where(AgentUsageRecord.occurred_at >= since)
    if until is not None:
        stmt = stmt.where(AgentUsageRecord.occurred_at < until)
    total = db.scalar(stmt)
    return Decimal(total) if not isinstance(total, Decimal) else total


@dataclass
class UsageAggregate:
    """Agrégat de consommation d'un tenant (réconciliable avec la liste des records)."""

    total_cost: Decimal
    total_tokens: int
    total_calls: int
    currency: str
    record_count: int


def _tenant(ctx: HostContext) -> uuid.UUID | None:
    return _as_uuid(ctx.installation.id)


def aggregate(
    db: Session,
    ctx: HostContext,
    *,
    since: datetime | None = None,
    project_id: str | None = None,
    agent_id: str | None = None,
) -> UsageAggregate:
    """Agrégat tenant-scopé (somme coûts/tokens/appels) — base de la réconciliation."""
    stmt = select(
        func.coalesce(func.sum(AgentUsageRecord.cost), 0),
        func.coalesce(func.sum(AgentUsageRecord.total_tokens), 0),
        func.coalesce(func.sum(AgentUsageRecord.calls), 0),
        func.count(AgentUsageRecord.id),
    ).where(AgentUsageRecord.installation_id == _tenant(ctx))
    pid = _as_uuid(project_id)
    if pid is not None:
        stmt = stmt.where(AgentUsageRecord.project_id == pid)
    aid = _as_uuid(agent_id)
    if aid is not None:
        stmt = stmt.where(AgentUsageRecord.agent_id == aid)
    if since is not None:
        stmt = stmt.where(AgentUsageRecord.occurred_at >= since)
    row = db.execute(stmt).one()
    total_cost = row[0] if isinstance(row[0], Decimal) else Decimal(row[0])
    return UsageAggregate(
        total_cost=total_cost,
        total_tokens=int(row[1]),
        total_calls=int(row[2]),
        currency="USD",
        record_count=int(row[3]),
    )


def _encode_cursor(occurred_at: datetime, record_id: uuid.UUID) -> str:
    import base64

    return base64.urlsafe_b64encode(
        f"{occurred_at.isoformat()}|{record_id}".encode()
    ).decode()


def _decode_cursor(cursor: str) -> tuple[str, str] | None:
    import base64

    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        occurred, _, record_id = raw.partition("|")
        return occurred, record_id
    except (ValueError, TypeError):
        return None


def list_usage(
    db: Session,
    ctx: HostContext,
    *,
    limit: int = 50,
    cursor: str | None = None,
    project_id: str | None = None,
    agent_id: str | None = None,
) -> tuple[list[AgentUsageRecord], str | None, bool]:
    """Liste paginée (curseur) des enregistrements de consommation du tenant."""
    limit = max(1, min(limit, 200))
    stmt: Select = select(AgentUsageRecord).where(
        AgentUsageRecord.installation_id == _tenant(ctx)
    )
    pid = _as_uuid(project_id)
    if pid is not None:
        stmt = stmt.where(AgentUsageRecord.project_id == pid)
    aid = _as_uuid(agent_id)
    if aid is not None:
        stmt = stmt.where(AgentUsageRecord.agent_id == aid)
    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded:
            c_occurred, c_id = decoded
            cid = _as_uuid(c_id)
            if cid is not None:
                stmt = stmt.where(
                    tuple_(AgentUsageRecord.occurred_at, AgentUsageRecord.id)
                    < (datetime.fromisoformat(c_occurred), cid)
                )
    stmt = stmt.order_by(
        AgentUsageRecord.occurred_at.desc(), AgentUsageRecord.id.desc()
    ).limit(limit + 1)
    rows = list(db.scalars(stmt).all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = _encode_cursor(last.occurred_at, last.id)
    return rows, next_cursor, has_more
