"""Logique d'ingest V1 : événements séquencés/idempotents + heartbeat monotone.

Invariants (contrat V1 §8/§10, ADR-0005) :

- l'agent et le tenant sont **dérivés du credential**, jamais d'un body ; un
  `agent_key` divergent est refusé (`permission_denied`) ;
- idempotence par `(agent_id, event_id)` : rejouer un batch ne duplique rien ;
- séquence monotone par agent (`agents.last_sequence`) : une séquence ancienne
  est rejetée, un heartbeat ancien ne fait pas régresser l'état ;
- **persistance avant publication** : chaque événement accepté écrit `agent_events`
  ET une ligne `mc_outbox_events` dans la MÊME transaction ; aucune publication
  Redis synchrone dans la requête (un relais consomme l'outbox).
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.agent_control.ingest.auth import AgentCredentialContext, require_scope
from apps.api.agent_control.ingest.schemas import (
    IngestEventsRequest,
    IngestEventsResponse,
    IngestHeartbeatResponse,
    IngestHeartbeatV1,
)
from apps.api.core.config import settings
from apps.api.integrations.envelopes import EventEnvelopeV1
from apps.api.integrations.errors import PermissionDenied, ValidationFailed
from apps.api.integrations.events_catalog import EVENT_TYPES
from apps.api.models import Agent, AgentEvent, AgentState, MCOutboxEvent

INGEST_SCOPE = "ingest"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # Python 3.11+ : fromisoformat accepte l'offset et le suffixe "Z".
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _as_uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        return None


def _topic_for_event(ev: EventEnvelopeV1, agent: Agent) -> str:
    """Dérive le topic WS V1 (validé serveur) depuis le contexte de l'événement."""
    if ev.run_id:
        return f"run:{ev.run_id}"
    if ev.event_type.startswith("agent."):
        return f"agent:{agent.id}"
    if ev.project_id:
        return f"project:{ev.project_id}"
    return "fleet"


def ingest_events(
    db: Session, ctx: AgentCredentialContext, request: IngestEventsRequest
) -> IngestEventsResponse:
    """Ingest batch borné, séquencé, idempotent. Persiste avant publication (outbox)."""
    require_scope(ctx, INGEST_SCOPE)
    agent = ctx.agent
    events = request.events

    if len(events) > settings.mc_event_batch_max:
        raise ValidationFailed(
            f"batch trop grand ({len(events)} > {settings.mc_event_batch_max})",
            details={"max": settings.mc_event_batch_max},
        )

    # Sécurité : un producteur ne publie QUE pour son propre agent. Un seul
    # agent_key divergent invalide tout le batch (jamais d'injection cross-agent).
    for ev in events:
        if ev.agent_key != agent.agent_key:
            raise PermissionDenied(
                "agent_key du body différent de l'identité du credential",
                details={"expected": agent.agent_key},
            )

    # Déduplication : event_id déjà persistés pour cet agent (idempotence replay).
    batch_ids = [ev.event_id for ev in events]
    existing: set[str] = set()
    if batch_ids:
        existing = set(
            db.scalars(
                select(AgentEvent.event_id).where(
                    AgentEvent.agent_id == agent.id, AgentEvent.event_id.in_(batch_ids)
                )
            ).all()
        )

    accepted = duplicates = rejected = 0
    seen_in_batch: set[str] = set()
    last_seq = agent.last_sequence or 0

    # Ordre croissant de séquence pour appliquer la monotonie au sein du batch.
    for ev in sorted(events, key=lambda e: e.sequence):
        if ev.event_id in existing or ev.event_id in seen_in_batch:
            duplicates += 1
            continue
        if ev.event_type not in EVENT_TYPES:
            rejected += 1
            continue
        occurred = _parse_dt(ev.occurred_at)
        if occurred is None:
            rejected += 1
            continue
        if ev.sequence <= last_seq:
            # Séquence ancienne/dupliquée avec un event_id neuf → rejet (§8).
            rejected += 1
            continue

        seen_in_batch.add(ev.event_id)
        db.add(
            AgentEvent(
                installation_id=agent.installation_id,
                agent_id=agent.id,
                event_id=ev.event_id,
                sequence=ev.sequence,
                event_type=ev.event_type,
                payload=ev.payload,
                occurred_at=occurred,
                request_id=ctx.credential.key_prefix,
                run_id=_as_uuid(ev.run_id),
                project_id=_as_uuid(ev.project_id),
                task_id=_as_uuid(ev.task_id),
                trace_id=ev.trace_id,
                client_version=ev.client_version,
            )
        )
        # Outbox écrit DANS la même transaction (ADR-0005) — jamais de publish direct.
        db.add(
            MCOutboxEvent(
                installation_id=agent.installation_id,
                event_id=ev.event_id,
                event_type=ev.event_type,
                topic=_topic_for_event(ev, agent),
                sequence=ev.sequence,
                payload=ev.payload,
                status="pending",
            )
        )
        last_seq = ev.sequence
        accepted += 1

    agent.last_sequence = last_seq
    ctx.credential.last_used_at = datetime.now(UTC)
    db.commit()

    return IngestEventsResponse(
        accepted=accepted,
        duplicates=duplicates,
        rejected=rejected,
        last_sequence=agent.last_sequence,
    )


def ingest_heartbeat_v1(
    db: Session, ctx: AgentCredentialContext, body: IngestHeartbeatV1
) -> IngestHeartbeatResponse:
    """Heartbeat V1 tenant-aware : projection agent monotone (pas de régression)."""
    require_scope(ctx, INGEST_SCOPE)
    agent = ctx.agent

    if body.agent_key != agent.agent_key:
        raise PermissionDenied(
            "agent_key du body différent de l'identité du credential",
            details={"expected": agent.agent_key},
        )

    try:
        state = AgentState(body.state)
    except ValueError as exc:
        raise ValidationFailed(f"état invalide : {body.state}") from exc
    if state == AgentState.stale:
        # `stale` est dérivé serveur (silence > seuil), jamais ingéré (cf. Contract D).
        raise ValidationFailed("état 'stale' non ingérable (dérivé serveur)")

    last_seq = agent.last_sequence or 0
    # Un heartbeat plus ancien que la dernière séquence connue ne régresse pas
    # l'état (§10) ; il prouve toutefois la liveness (last_heartbeat rafraîchi).
    is_stale = body.sequence is not None and body.sequence < last_seq
    now = datetime.now(UTC)

    agent.last_heartbeat = now
    applied = not is_stale
    if applied:
        agent.state = state
        if body.task is not None:
            agent.task = body.task
        if body.progress is not None:
            agent.progress = body.progress
        if body.sequence is not None and body.sequence > last_seq:
            agent.last_sequence = body.sequence
        # Projection diffusable via l'outbox (persistée avant publication).
        db.add(
            MCOutboxEvent(
                installation_id=agent.installation_id,
                event_id=str(uuid.uuid4()),
                event_type="agent.heartbeat",
                topic=f"agent:{agent.id}",
                sequence=body.sequence,
                payload={
                    "agent_key": agent.agent_key,
                    "state": state.value,
                    "progress": agent.progress or 0,
                },
                status="pending",
            )
        )

    ctx.credential.last_used_at = now
    db.commit()

    return IngestHeartbeatResponse(
        agent_key=agent.agent_key,
        state=agent.state.value if hasattr(agent.state, "value") else str(agent.state),
        last_sequence=agent.last_sequence,
        last_heartbeat=agent.last_heartbeat.isoformat() if agent.last_heartbeat else None,
        applied=applied,
    )
