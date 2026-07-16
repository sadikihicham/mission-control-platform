"""Service d'audit append-only et redacted — P6, SP6.

Journal métier tenant-scopé (`mc_audit_logs`) couvrant les décisions sensibles :
policy, approbations, budgets, credentials, exports. Complète l'audit minimal P5
(`ActivityLog type="policy.evaluated"`), qui reste écrit pour compat, en ajoutant
un journal dédié **immuable**.

Deux invariants du Gate P6, garantis ici :

- **redacted** : `before` / `after` / `metadata` passent par la redaction
  centralisée AVANT écriture — un secret/token/mot de passe/PII n'atteint jamais
  la base. L'IP éventuelle n'est stockée que **hashée** (`ip_hash`).
- **append-only** : ce service n'expose QUE l'écriture et la lecture ; aucune
  mise à jour ni suppression. La base le garantit aussi (trigger, migration 0015).

`write_audit` **ne commit pas** : il écrit dans la session de la transaction
métier appelante (l'audit est atomique avec le fait qu'il trace). Un helper
`audit_from_context` extrait acteur + tenant du `HostContext`.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime

from sqlalchemy import Select, select, tuple_
from sqlalchemy.orm import Session

from apps.api.agent_control.operations.redaction import redact
from apps.api.integrations.errors import ResourceNotFound
from apps.api.integrations.host_context import HostContext
from apps.api.models import MCAuditLog


def _as_uuid(value) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def hash_ip(ip: str | None) -> str | None:
    """Empreinte SHA-256 d'une IP (jamais l'IP en clair). `None` → `None`."""
    if not ip:
        return None
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()


def write_audit(
    db: Session,
    *,
    installation_id,
    action: str,
    actor_type: str = "system",
    actor_id: str | None = None,
    actor_label: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
    request_id: str | None = None,
    ip: str | None = None,
    metadata: dict | None = None,
) -> MCAuditLog:
    """Écrit une ligne d'audit (redacted). Ne commit pas (transaction appelante).

    Tout contenu structuré (`before`/`after`/`metadata`) est redacted ; l'IP est
    hashée. `installation_id` est le tenant résolu serveur, jamais un body.
    """
    entry = MCAuditLog(
        installation_id=_as_uuid(installation_id),
        actor_type=actor_type,
        actor_id=actor_id,
        actor_label=actor_label,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        before=redact(before) if before is not None else None,
        after=redact(after) if after is not None else None,
        request_id=request_id,
        ip_hash=hash_ip(ip),
        audit_metadata=redact(metadata) if metadata else {},
    )
    db.add(entry)
    return entry


def audit_from_context(
    db: Session,
    ctx: HostContext,
    *,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
    ip: str | None = None,
    metadata: dict | None = None,
) -> MCAuditLog:
    """Écrit un audit avec l'acteur humain et le tenant dérivés du `HostContext`."""
    return write_audit(
        db,
        installation_id=ctx.installation.id,
        action=action,
        actor_type="user",
        actor_id=ctx.user.external_user_id,
        actor_label=ctx.user.display_name or ctx.user.email,
        target_type=target_type,
        target_id=target_id,
        before=before,
        after=after,
        request_id=ctx.request_id,
        ip=ip,
        metadata=metadata,
    )


# --- Lecture (tenant-scopée, paginée) -----------------------------------------


def _tenant(ctx: HostContext) -> uuid.UUID | None:
    return _as_uuid(ctx.installation.id)


def _encode_cursor(created_at: datetime, entry_id: uuid.UUID) -> str:
    import base64

    raw = f"{created_at.isoformat()}|{entry_id}".encode()
    return base64.urlsafe_b64encode(raw).decode()


def _decode_cursor(cursor: str) -> tuple[str, str] | None:
    import base64

    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        created, _, entry_id = raw.partition("|")
        return created, entry_id
    except (ValueError, TypeError):
        return None


def list_audit(
    db: Session,
    ctx: HostContext,
    *,
    limit: int = 50,
    cursor: str | None = None,
    action: str | None = None,
    actor_id: str | None = None,
) -> tuple[list[MCAuditLog], str | None, bool]:
    """Liste paginée (curseur) du journal d'audit du tenant, récence décroissante."""
    limit = max(1, min(limit, 200))
    stmt: Select = select(MCAuditLog).where(MCAuditLog.installation_id == _tenant(ctx))
    if action:
        stmt = stmt.where(MCAuditLog.action == action)
    if actor_id:
        stmt = stmt.where(MCAuditLog.actor_id == actor_id)
    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded:
            c_created, c_id = decoded
            cid = _as_uuid(c_id)
            if cid is not None:
                stmt = stmt.where(
                    tuple_(MCAuditLog.created_at, MCAuditLog.id)
                    < (datetime.fromisoformat(c_created), cid)
                )
    stmt = stmt.order_by(MCAuditLog.created_at.desc(), MCAuditLog.id.desc()).limit(limit + 1)
    rows = list(db.scalars(stmt).all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = _encode_cursor(last.created_at, last.id)
    return rows, next_cursor, has_more


def get_audit_entry(db: Session, ctx: HostContext, entry_id: str) -> MCAuditLog:
    """Charge une entrée d'audit bornée au tenant. 404 hors tenant/inexistante."""
    eid = _as_uuid(entry_id)
    if eid is None:
        raise ResourceNotFound("entrée d'audit introuvable", details={"id": entry_id})
    entry = db.scalar(
        select(MCAuditLog).where(
            MCAuditLog.id == eid, MCAuditLog.installation_id == _tenant(ctx)
        )
    )
    if entry is None:
        raise ResourceNotFound("entrée d'audit introuvable", details={"id": entry_id})
    return entry
