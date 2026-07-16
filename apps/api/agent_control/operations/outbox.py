"""Écriture outbox opérationnelle P6 (SP6) — persistance avant publication.

Les événements opérationnels (`alert.*`, `budget.*`, `usage.recorded`) transitent
par l'outbox transactionnel déjà posé en P3 (`mc_outbox_events`, ADR-0005) : ils
sont écrits DANS la transaction du fait métier, jamais publiés en synchrone. Un
relais (déjà en place pour les événements de contrôle) balaie les lignes
`pending` et les diffuse vers Redis/notifications ; un Redis indisponible ne perd
jamais l'alerte (elle reste `pending`).

Le payload est redacted ici aussi (défense en profondeur) : rien de diffusé ne
doit contenir de secret/PII, même si l'appelant a déjà nettoyé.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from apps.api.agent_control.operations.redaction import redact_dict
from apps.api.integrations.events_catalog import EVENT_TYPES
from apps.api.models import MCOutboxEvent


def emit_outbox(
    db: Session,
    *,
    installation_id,
    event_type: str,
    topic: str,
    payload: dict,
    sequence: int | None = None,
) -> MCOutboxEvent:
    """Écrit un événement diffusable (redacted) dans l'outbox. Ne commit pas.

    `event_type` doit appartenir au catalogue figé (`EVENT_TYPES`) — un type hors
    contrat lèverait plus loin côté relais ; on refuse à la source (fail-closed).
    """
    if event_type not in EVENT_TYPES:
        raise ValueError(f"event_type hors catalogue V1 : {event_type}")
    row = MCOutboxEvent(
        installation_id=installation_id,
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        topic=topic,
        payload=redact_dict(payload),
        sequence=sequence,
        status="pending",
    )
    db.add(row)
    return row
