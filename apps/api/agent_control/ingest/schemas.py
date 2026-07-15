"""DTO d'ingest V1 (contrat V1 §8/§13). Le tenant n'apparaît jamais ici : il est
dérivé du credential agent côté serveur.
"""
from pydantic import BaseModel, Field

from apps.api.integrations.envelopes import EventEnvelopeV1


class IngestEventsRequest(BaseModel):
    """Batch borné d'événements V1 (`MC_EVENT_BATCH_MAX`)."""

    events: list[EventEnvelopeV1] = Field(default_factory=list)


class IngestEventsResponse(BaseModel):
    """Résultat d'un batch : idempotent et séquencé (§8).

    - `accepted` : événements nouveaux persistés (+ outbox) ;
    - `duplicates` : `event_id` déjà vus pour cet agent (idempotence, sans erreur) ;
    - `rejected` : type inconnu ou séquence ancienne/dupliquée (sequence_out_of_order) ;
    - `last_sequence` : plus haute séquence connue de l'agent après le batch.
    """

    accepted: int
    duplicates: int
    rejected: int
    last_sequence: int


class IngestHeartbeatV1(BaseModel):
    """Heartbeat V1 tenant-aware : met à jour la projection agent de façon monotone.

    `agent_key` doit correspondre à l'identité du credential (sinon
    permission_denied). `sequence` (facultative) empêche un heartbeat ancien de
    faire régresser l'état (§10 : un événement ancien ne régresse jamais l'état).
    """

    agent_key: str
    state: str
    run_id: str | None = None
    task: str | None = None
    progress: int | None = None
    sequence: int | None = Field(default=None, ge=0)
    occurred_at: str | None = None
    metrics: dict = Field(default_factory=dict)


class IngestHeartbeatResponse(BaseModel):
    """Projection agent après heartbeat V1."""

    agent_key: str
    state: str
    last_sequence: int
    last_heartbeat: str | None = None
    applied: bool  # False si ignoré car séquence ancienne (pas de régression)
