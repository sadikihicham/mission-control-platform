"""Enveloppes de contrat V1 : erreur, pagination, événement, message WS.

Ces formes s'appliquent **exclusivement** aux routes `/agent-control/v1/*` et au
temps réel `/agent-control/ws`. Les contrats V0 (A–E) conservent leurs formes
existantes intactes : `{"detail": ...}` pour les erreurs, `{"type","data"}` pour
les messages du canal `mc:events`. Aucune de ces primitives ne modifie V0.
"""
import enum

from pydantic import BaseModel, Field


class ErrorCode(str, enum.Enum):
    """Codes machine stables des erreurs V1 (en plus du message humain).

    Un code n'est jamais renommé ni recyclé : c'est une valeur de contrat. La
    correspondance code → statut HTTP est indicative (colonne « HTTP » du
    contrat V1) ; le code reste la source d'interprétation programmatique.
    """

    unauthenticated = "unauthenticated"          # 401 — identité absente/invalide
    credential_invalid = "credential_invalid"    # 401 — credential agent invalide
    credential_revoked = "credential_revoked"    # 403 — credential révoqué/expiré
    permission_denied = "permission_denied"      # 403 — capacité requise absente
    tenant_required = "tenant_required"          # 403 — aucun contexte tenant résolu
    tenant_forbidden = "tenant_forbidden"        # 403 — accès hors tenant courant
    not_found = "not_found"                      # 404 — ressource absente dans le tenant
    validation_error = "validation_error"        # 422 — corps/paramètres invalides
    conflict = "conflict"                        # 409 — conflit d'unicité générique
    idempotency_conflict = "idempotency_conflict"  # 409 — clé d'idempotence rejouée
    sequence_out_of_order = "sequence_out_of_order"  # 409 — séquence ancienne/dupliquée
    state_conflict = "state_conflict"            # 409 — transition d'état interdite
    approval_required = "approval_required"      # 409 — action bloquée en attente de décision
    budget_exceeded = "budget_exceeded"          # 409 — dépassement budget bloquant
    rate_limited = "rate_limited"                # 429 — quota dépassé
    not_implemented = "not_implemented"          # 501 — route V1 non encore livrée
    internal_error = "internal_error"            # 500 — erreur serveur


# Correspondance indicative code → statut HTTP (le contrat V1 fait foi).
HTTP_STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.unauthenticated: 401,
    ErrorCode.credential_invalid: 401,
    ErrorCode.credential_revoked: 403,
    ErrorCode.permission_denied: 403,
    ErrorCode.tenant_required: 403,
    ErrorCode.tenant_forbidden: 403,
    ErrorCode.not_found: 404,
    ErrorCode.validation_error: 422,
    ErrorCode.conflict: 409,
    ErrorCode.idempotency_conflict: 409,
    ErrorCode.sequence_out_of_order: 409,
    ErrorCode.state_conflict: 409,
    ErrorCode.approval_required: 409,
    ErrorCode.budget_exceeded: 409,
    ErrorCode.rate_limited: 429,
    ErrorCode.not_implemented: 501,
    ErrorCode.internal_error: 500,
}


class ErrorBody(BaseModel):
    """Corps d'erreur V1. `code` est stable, `message` est humain (fr par défaut)."""

    code: ErrorCode
    message: str
    request_id: str
    details: dict = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    """Enveloppe d'erreur V1 : `{"error": {code, message, request_id, details}}`."""

    error: ErrorBody


class PageInfo(BaseModel):
    """Métadonnées de pagination par curseur. Ordre stable, limite bornée.

    `next_cursor` est un curseur opaque (base64url) encodant la dernière clé de
    tri ; `null` quand il n'y a plus de page. Le client ne fabrique jamais de
    curseur, il ne fait que renvoyer celui reçu.
    """

    next_cursor: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
    has_more: bool = False


class EventEnvelopeV1(BaseModel):
    """Enveloppe d'événement V1 (ingest producteur → serveur, puis persistée).

    Champs obligatoires : `event_id`, `agent_key`, `sequence`, `event_type`,
    `occurred_at`, `payload`. Champs contextuels facultatifs : `run_id`,
    `project_id`, `task_id`, `trace_id`, `client_version`. Le tenant n'est jamais
    accepté depuis cette enveloppe : il est dérivé du credential agent.
    """

    event_id: str
    agent_key: str
    sequence: int = Field(ge=0)
    event_type: str
    occurred_at: str
    payload: dict = Field(default_factory=dict)
    run_id: str | None = None
    project_id: str | None = None
    task_id: str | None = None
    trace_id: str | None = None
    client_version: str | None = None


class WsMessageV1(BaseModel):
    """Message diffusé sur `/agent-control/ws` (Contract E V1, canal distinct de V0).

    Toujours estampillé `tenant_id` côté serveur ; jamais diffusé sans tenant ni
    topic autorisé. `id` = `event_id` d'origine (idempotence/reprise via
    `last_event_id`). `sequence` permet la détection de trou côté client.
    """

    id: str
    type: str
    tenant_id: str
    topic: str
    sequence: int
    data: dict = Field(default_factory=dict)
    occurred_at: str
