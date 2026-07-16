"""Alertes opérables, dédupliquées, ACK/résolution — P6, SP6.

Une alerte matérialise une **condition** identifiée par `dedup_key`. Tant qu'une
alerte de même clé n'est pas résolue, une re-détection **ne crée pas** de doublon
et **ne re-notifie pas** (invariant Gate P6 : « alertes dédupliquées »). Garanti
applicativement (recherche préalable) ET en base (index unique partiel
`WHERE status <> 'resolved'`, migration 0015).

`details` est **redacted** en amont (`open_alert` re-redacte par sécurité) : une
alerte est « opérable sans exposer de données sensibles » (Gate P6).

Machine simple : `open → acknowledged → resolved` (résolution possible aussi
directement depuis `open`). ACK/résolution sont des actions opérateur (capacité
`operate`), auditées et diffusées via l'outbox.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Select, select, tuple_
from sqlalchemy.orm import Session

from apps.api.agent_control.operations import audit as audit_service
from apps.api.agent_control.operations.outbox import emit_outbox
from apps.api.agent_control.operations.redaction import redact_dict
from apps.api.integrations.errors import ResourceNotFound, StateConflict
from apps.api.integrations.host_context import HostContext
from apps.api.models import AgentAlert

ACTIVE_STATUSES = ("open", "acknowledged")


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


def _tenant(ctx: HostContext) -> uuid.UUID | None:
    return _as_uuid(ctx.installation.id)


def find_active_alert(
    db: Session, installation_id, dedup_key: str
) -> AgentAlert | None:
    """Alerte non résolue (open|acknowledged) pour cette condition, s'il en existe."""
    return db.scalar(
        select(AgentAlert).where(
            AgentAlert.installation_id == _as_uuid(installation_id),
            AgentAlert.dedup_key == dedup_key,
            AgentAlert.status.in_(ACTIVE_STATUSES),
        )
    )


def open_alert(
    db: Session,
    *,
    installation_id,
    alert_type: str,
    dedup_key: str,
    title: str,
    severity: str = "warning",
    target_type: str | None = None,
    target_id=None,
    details: dict | None = None,
) -> tuple[AgentAlert, bool]:
    """Ouvre une alerte si la condition n'a pas déjà une alerte active (dédup).

    Renvoie `(alerte, created)`. `created=False` = doublon supprimé : l'alerte
    active existante est renvoyée telle quelle, **sans** nouvelle notification.
    Ne commit pas (transaction métier appelante) — l'alerte est atomique avec la
    condition qui la déclenche (ex. franchissement de seuil budget).
    """
    existing = find_active_alert(db, installation_id, dedup_key)
    if existing is not None:
        return existing, False

    alert = AgentAlert(
        installation_id=_as_uuid(installation_id),
        alert_type=alert_type,
        severity=severity,
        status="open",
        target_type=target_type,
        target_id=_as_uuid(target_id),
        dedup_key=dedup_key,
        title=title,
        details=redact_dict(details),
    )
    db.add(alert)
    db.flush()  # matérialise l'id pour l'outbox
    emit_outbox(
        db,
        installation_id=_as_uuid(installation_id),
        event_type="alert.opened",
        topic="fleet",
        payload={
            "alert_id": str(alert.id),
            "alert_type": alert_type,
            "severity": severity,
            "title": title,
            "target_type": target_type,
            "target_id": str(target_id) if target_id else None,
        },
    )
    return alert, True


# --- Lecture ------------------------------------------------------------------


def _encode_cursor(opened_at: datetime, alert_id: uuid.UUID) -> str:
    import base64

    return base64.urlsafe_b64encode(
        f"{opened_at.isoformat()}|{alert_id}".encode()
    ).decode()


def _decode_cursor(cursor: str) -> tuple[str, str] | None:
    import base64

    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        opened, _, alert_id = raw.partition("|")
        return opened, alert_id
    except (ValueError, TypeError):
        return None


def list_alerts(
    db: Session,
    ctx: HostContext,
    *,
    limit: int = 50,
    cursor: str | None = None,
    status: str | None = None,
    severity: str | None = None,
) -> tuple[list[AgentAlert], str | None, bool]:
    """Liste paginée (curseur) des alertes du tenant, récence décroissante."""
    limit = max(1, min(limit, 200))
    stmt: Select = select(AgentAlert).where(AgentAlert.installation_id == _tenant(ctx))
    if status:
        stmt = stmt.where(AgentAlert.status == status)
    if severity:
        stmt = stmt.where(AgentAlert.severity == severity)
    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded:
            c_opened, c_id = decoded
            cid = _as_uuid(c_id)
            if cid is not None:
                stmt = stmt.where(
                    tuple_(AgentAlert.opened_at, AgentAlert.id)
                    < (datetime.fromisoformat(c_opened), cid)
                )
    stmt = stmt.order_by(AgentAlert.opened_at.desc(), AgentAlert.id.desc()).limit(limit + 1)
    rows = list(db.scalars(stmt).all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = _encode_cursor(last.opened_at, last.id)
    return rows, next_cursor, has_more


def get_alert(db: Session, ctx: HostContext, alert_id: str) -> AgentAlert:
    """Charge une alerte bornée au tenant. 404 hors tenant/inexistante."""
    aid = _as_uuid(alert_id)
    if aid is None:
        raise ResourceNotFound("alerte introuvable", details={"alert_id": alert_id})
    alert = db.scalar(
        select(AgentAlert).where(
            AgentAlert.id == aid, AgentAlert.installation_id == _tenant(ctx)
        )
    )
    if alert is None:
        raise ResourceNotFound("alerte introuvable", details={"alert_id": alert_id})
    return alert


# --- Actions opérateur (capacité operate) -------------------------------------


def acknowledge_alert(
    db: Session, ctx: HostContext, alert_id: str, *, ip: str | None = None
) -> AgentAlert:
    """Acquitte une alerte (`open → acknowledged`). Idempotent si déjà acquittée."""
    alert = get_alert(db, ctx, alert_id)
    if alert.status == "resolved":
        raise StateConflict(
            "alerte déjà résolue", details={"current": alert.status}
        )
    if alert.status == "acknowledged":
        return alert  # idempotent
    alert.status = "acknowledged"
    alert.acknowledged_at = _now()
    alert.acknowledged_by = _as_uuid(ctx.user.local_user_id)
    alert.version += 1
    emit_outbox(
        db,
        installation_id=alert.installation_id,
        event_type="alert.acknowledged",
        topic="fleet",
        payload={"alert_id": str(alert.id)},
    )
    audit_service.audit_from_context(
        db,
        ctx,
        action="alert.acknowledged",
        target_type="alert",
        target_id=str(alert.id),
        after={"status": "acknowledged", "alert_type": alert.alert_type},
        ip=ip,
    )
    db.commit()
    db.refresh(alert)
    return alert


def resolve_alert(
    db: Session, ctx: HostContext, alert_id: str, *, ip: str | None = None
) -> AgentAlert:
    """Résout une alerte (`open|acknowledged → resolved`). Libère la clé de dédup."""
    alert = get_alert(db, ctx, alert_id)
    if alert.status == "resolved":
        return alert  # idempotent
    alert.status = "resolved"
    alert.resolved_at = _now()
    alert.resolved_by = _as_uuid(ctx.user.local_user_id)
    alert.version += 1
    emit_outbox(
        db,
        installation_id=alert.installation_id,
        event_type="alert.resolved",
        topic="fleet",
        payload={"alert_id": str(alert.id)},
    )
    audit_service.audit_from_context(
        db,
        ctx,
        action="alert.resolved",
        target_type="alert",
        target_id=str(alert.id),
        after={"status": "resolved", "alert_type": alert.alert_type},
        ip=ip,
    )
    db.commit()
    db.refresh(alert)
    return alert
