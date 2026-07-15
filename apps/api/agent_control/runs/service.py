"""Plan de contrôle des runs V1 (P4, SP3) — projection, transitions, timeline.

Deux responsabilités :

1. **Projection depuis l'ingest** (`project_run_event` / `project_run_step_event`) :
   les événements `run.*` / `run.step.*` déjà journalisés (append-only) dans
   `agent_events` alimentent le modèle relationnel `agent_runs` / `agent_run_steps`.
   Le serveur fait foi sur les transitions (machine `run` figée en P0, §9) :

   - un état terminal est **immuable** — un événement qui prétend le faire
     transiter est journalisé (audit) mais **jamais appliqué** ;
   - une transition non autorisée est refusée (non appliquée) ;
   - un « retry » (nouveau `run_id` + `payload.retry_of`) crée un **nouveau** run
     lié via `retry_of_run_id`, il ne rouvre jamais l'ancien.

   La projection est **non fatale** pour l'ingest : elle n'échoue jamais un batch
   (les compteurs accepted/duplicates/rejected ne dépendent que du journal).

2. **Lecture tenant-scoped** (`list_runs` / `get_run` / `run_timeline`) : toute
   requête est bornée à `installation_id` du `HostContext` — aucune recherche par
   ID seul. Un run d'un autre tenant est un 404 (pas de fuite d'existence).

Le tenant/agent est toujours dérivé serveur (credential à l'ingest, JWT en
lecture), jamais d'un body/query. Aucun prompt/secret brut n'est exposé : la
timeline applique une redaction conservatrice (P6 durcira).
"""
from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime

from sqlalchemy import Select, select, tuple_
from sqlalchemy.orm import Session, selectinload

from apps.api.integrations.errors import ResourceNotFound, StateConflict
from apps.api.integrations.host_context import HostContext
from apps.api.integrations.state_machines import RUN_TRANSITIONS, RunState, can_transition
from apps.api.models import (
    Agent,
    AgentEvent,
    AgentProjectAssignment,
    AgentRun,
    AgentRunStep,
)

# --- Machine `run` : constantes dérivées de la table figée (P0) ---------------

# États terminaux = sans transition sortante (immuables).
_TERMINAL_RUN_STATES: frozenset[RunState] = frozenset(
    state for state, targets in RUN_TRANSITIONS.items() if not targets
)
# États où le run est « démarré » : jalonne `started_at`.
_STARTED_RUN_STATES: frozenset[RunState] = frozenset({RunState.starting, RunState.running})

# event_type `run.<state>` → RunState cible (hors `run.step.*`).
RUN_STATE_BY_EVENT: dict[str, RunState] = {
    f"run.{state.value}": state for state in RunState
}
# run.step.<verbe> → état de l'étape.
STEP_STATE_BY_EVENT: dict[str, str] = {
    "run.step.started": "started",
    "run.step.completed": "succeeded",
    "run.step.failed": "failed",
}

# Clés de payload masquées dans la timeline (redaction P4, conservatrice).
_REDACT_KEY_MARKERS: tuple[str, ...] = (
    "secret",
    "token",
    "password",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "prompt",
    "raw",
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


# --- Transition serveur-autoritative (pure, testable directement) -------------


def transition_run(run: AgentRun, new_state: RunState, *, at: datetime | None = None) -> None:
    """Applique `run.state → new_state` si la machine l'autorise, sinon `StateConflict`.

    Refuse toute transition depuis un état terminal (immuable) et toute
    transition non listée (`RUN_TRANSITIONS`). Met à jour les jalons temporels et
    incrémente le verrou optimiste `version`. Fonction autoritaire réutilisée par
    la projection d'ingest (qui capture l'exception pour rester non fatale).
    """
    moment = at or _now()
    current = RunState(run.state)
    if current == new_state:
        # Idempotence : ré-annoncer l'état courant ne fait rien (pas un conflit).
        run.heartbeat_at = moment
        return
    if current in _TERMINAL_RUN_STATES:
        raise StateConflict(
            f"run dans un état terminal immuable : {current.value}",
            details={"current": current.value, "requested": new_state.value},
        )
    if not can_transition("run", current, new_state):
        raise StateConflict(
            f"transition run interdite : {current.value} → {new_state.value}",
            details={"current": current.value, "requested": new_state.value},
        )
    run.state = new_state.value
    run.version += 1
    run.heartbeat_at = moment
    if new_state in _STARTED_RUN_STATES and run.started_at is None:
        run.started_at = moment
    if new_state in _TERMINAL_RUN_STATES:
        run.finished_at = moment


# --- Projection depuis l'ingest (non fatale) ----------------------------------


def _ensure_active_assignment(db: Session, agent: Agent, project_id: uuid.UUID) -> None:
    """Garantit une affectation active agent↔projet (unique active, get-or-create)."""
    existing = db.scalar(
        select(AgentProjectAssignment.id).where(
            AgentProjectAssignment.agent_id == agent.id,
            AgentProjectAssignment.project_id == project_id,
            AgentProjectAssignment.status == "active",
        )
    )
    if existing is not None:
        return
    db.add(
        AgentProjectAssignment(
            installation_id=agent.installation_id,
            agent_id=agent.id,
            project_id=project_id,
            role="runner",
            status="active",
        )
    )


def _find_run_in_scope(
    db: Session, agent: Agent, run_id: uuid.UUID
) -> AgentRun | None:
    """Charge un run par id **borné à l'agent et au tenant** (jamais par id seul)."""
    return db.scalar(
        select(AgentRun).where(
            AgentRun.id == run_id,
            AgentRun.agent_id == agent.id,
            AgentRun.installation_id == agent.installation_id,
        )
    )


def project_run_event(
    db: Session,
    agent: Agent,
    *,
    event_type: str,
    run_id_raw: str | None,
    project_id_raw: str | None,
    task_id_raw: str | None,
    payload: dict,
    occurred_at: datetime,
) -> AgentRun | None:
    """Projette un événement `run.<state>` dans `agent_runs`. Non fatal.

    Crée le run à sa première observation (idempotence par `run_id`), sinon
    applique la transition serveur-autoritative. Un état terminal existant reste
    immuable ; un `payload.retry_of` crée le lien vers le run rejoué.
    """
    new_state = RUN_STATE_BY_EVENT.get(event_type)
    run_id = _as_uuid(run_id_raw)
    if new_state is None or run_id is None:
        return None

    run = _find_run_in_scope(db, agent, run_id)
    if run is not None:
        # Transition d'un run connu : terminal immuable / transition interdite
        # sont refusées silencieusement (l'événement reste journalisé pour audit).
        try:
            transition_run(run, new_state, at=occurred_at)
        except StateConflict:
            return run
        _apply_terminal_result(run, payload)
        return run

    # Un run_id déjà pris par un autre agent/tenant : ne jamais écraser (sécurité).
    if db.scalar(select(AgentRun.id).where(AgentRun.id == run_id)) is not None:
        return None

    run = _create_run(
        db,
        agent,
        run_id=run_id,
        birth_state=new_state,
        project_id=_as_uuid(project_id_raw),
        task_id=_as_uuid(task_id_raw),
        payload=payload,
        occurred_at=occurred_at,
    )
    return run


def _create_run(
    db: Session,
    agent: Agent,
    *,
    run_id: uuid.UUID,
    birth_state: RunState,
    project_id: uuid.UUID | None,
    task_id: uuid.UUID | None,
    payload: dict,
    occurred_at: datetime,
) -> AgentRun:
    """Crée un run à sa première observation (état de naissance = 1er événement vu)."""
    retry_of = _as_uuid(payload.get("retry_of"))
    attempt = 1
    if retry_of is not None:
        parent = _find_run_in_scope(db, agent, retry_of)
        if parent is not None:
            attempt = (parent.attempt or 1) + 1
        else:
            retry_of = None  # lien invalide/hors tenant : ignoré, pas de fuite

    run = AgentRun(
        id=run_id,
        installation_id=agent.installation_id,
        project_id=project_id,
        task_id=task_id,
        agent_id=agent.id,
        external_run_key=(payload.get("external_run_key") or None),
        objective=(payload.get("objective") or None),
        state=birth_state.value,
        retry_of_run_id=retry_of,
        attempt=attempt,
        heartbeat_at=occurred_at,
        run_metadata=payload.get("metadata") or {},
    )
    if birth_state in _STARTED_RUN_STATES:
        run.started_at = occurred_at
    if birth_state in _TERMINAL_RUN_STATES:
        run.finished_at = occurred_at
    _apply_terminal_result(run, payload)
    db.add(run)
    if project_id is not None:
        _ensure_active_assignment(db, agent, project_id)
    # Session en autoflush=False : on matérialise le run (et l'affectation) tout de
    # suite pour que les événements suivants du MÊME batch le retrouvent (transition)
    # au lieu d'en recréer un doublon (collision de clé primaire au commit).
    db.flush()
    return run


def _apply_terminal_result(run: AgentRun, payload: dict) -> None:
    """Renseigne résumé/erreur quand le run est (ou devient) terminal."""
    if RunState(run.state) not in _TERMINAL_RUN_STATES:
        return
    if payload.get("result_summary") and not run.result_summary:
        run.result_summary = str(payload["result_summary"])[:4000]
    if payload.get("error_code") and not run.error_code:
        run.error_code = str(payload["error_code"])[:80]
    if payload.get("error_message") and not run.error_message:
        run.error_message = str(payload["error_message"])[:4000]


def project_run_step_event(
    db: Session,
    agent: Agent,
    *,
    event_type: str,
    run_id_raw: str | None,
    payload: dict,
    occurred_at: datetime,
) -> AgentRunStep | None:
    """Projette un événement `run.step.*` dans `agent_run_steps`. Non fatal.

    Rattache l'étape à un run **connu et dans le tenant** ; un `run_id` orphelin
    est ignoré (l'événement reste journalisé). Idempotence par `(run_id, sequence)`.
    """
    step_state = STEP_STATE_BY_EVENT.get(event_type)
    run_id = _as_uuid(run_id_raw)
    if step_state is None or run_id is None:
        return None

    run = _find_run_in_scope(db, agent, run_id)
    if run is None:
        return None

    sequence = payload.get("step_sequence")
    if sequence is None:
        sequence = payload.get("sequence")
    if sequence is None:
        # Pas de séquence fournie : numérote après la dernière étape connue.
        last = db.scalar(
            select(AgentRunStep.sequence)
            .where(AgentRunStep.run_id == run.id)
            .order_by(AgentRunStep.sequence.desc())
            .limit(1)
        )
        sequence = (last or 0) + 1
    try:
        sequence = int(sequence)
    except (ValueError, TypeError):
        return None

    step = db.scalar(
        select(AgentRunStep).where(
            AgentRunStep.run_id == run.id, AgentRunStep.sequence == sequence
        )
    )
    is_terminal_step = step_state in ("succeeded", "failed")
    if step is None:
        step = AgentRunStep(
            run_id=run.id,
            sequence=sequence,
            step_type=(payload.get("step_type") or "step"),
            name=(payload.get("name") or None),
            state=step_state,
            tool_name=(payload.get("tool_name") or None),
            input_summary=_clip(payload.get("input_summary")),
            output_summary=_clip(payload.get("output_summary")) if is_terminal_step else None,
            started_at=occurred_at if step_state == "started" else None,
            finished_at=occurred_at if is_terminal_step else None,
            step_metadata=payload.get("metadata") or {},
        )
        db.add(step)
        # autoflush=False : matérialiser l'étape pour qu'une clôture du MÊME batch
        # la retrouve (idempotence par (run_id, sequence)) au lieu d'en dupliquer.
        db.flush()
    else:
        # Étape déjà ouverte : n'accepte qu'une clôture (started reste started).
        if is_terminal_step:
            step.state = step_state
            step.finished_at = occurred_at
            if payload.get("output_summary"):
                step.output_summary = _clip(payload.get("output_summary"))
            if step.started_at is not None:
                step.duration_ms = int(
                    (occurred_at - step.started_at).total_seconds() * 1000
                )
            if payload.get("tool_name") and not step.tool_name:
                step.tool_name = payload.get("tool_name")

    run.heartbeat_at = occurred_at
    return step


def _clip(value, limit: int = 4000) -> str | None:
    if value is None:
        return None
    return str(value)[:limit]


# --- Lecture tenant-scoped ----------------------------------------------------


def _scoped(ctx: HostContext) -> uuid.UUID | None:
    """UUID d'installation du contexte (tenant), pour borner toute requête."""
    return _as_uuid(ctx.installation.id)


def _encode_cursor(*parts) -> str:
    raw = "|".join(str(p) for p in parts)
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> list[str] | None:
    try:
        return base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
    except (ValueError, TypeError):
        return None


def list_runs(
    db: Session,
    ctx: HostContext,
    *,
    limit: int = 50,
    cursor: str | None = None,
    project_id: str | None = None,
    agent_id: str | None = None,
    state: str | None = None,
) -> tuple[list[AgentRun], str | None, bool]:
    """Liste paginée (curseur) des runs du tenant courant, récence décroissante."""
    limit = max(1, min(limit, 200))
    stmt: Select = select(AgentRun).where(AgentRun.installation_id == _scoped(ctx))

    pid = _as_uuid(project_id)
    if pid is not None:
        stmt = stmt.where(AgentRun.project_id == pid)
    aid = _as_uuid(agent_id)
    if aid is not None:
        stmt = stmt.where(AgentRun.agent_id == aid)
    if state:
        stmt = stmt.where(AgentRun.state == state)

    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded and len(decoded) == 2:
            c_created, c_id = decoded
            cid = _as_uuid(c_id)
            if cid is not None:
                stmt = stmt.where(
                    tuple_(AgentRun.created_at, AgentRun.id)
                    < (datetime.fromisoformat(c_created), cid)
                )

    stmt = stmt.order_by(AgentRun.created_at.desc(), AgentRun.id.desc()).limit(limit + 1)
    rows = list(db.scalars(stmt).all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = _encode_cursor(last.created_at.isoformat(), last.id)
    return rows, next_cursor, has_more


def get_run(db: Session, ctx: HostContext, run_id: str) -> AgentRun:
    """Charge un run + ses étapes, borné au tenant. 404 hors tenant/inexistant."""
    rid = _as_uuid(run_id)
    if rid is None:
        raise ResourceNotFound("run introuvable", details={"run_id": run_id})
    run = db.scalar(
        select(AgentRun)
        .where(AgentRun.id == rid, AgentRun.installation_id == _scoped(ctx))
        .options(selectinload(AgentRun.steps))
    )
    if run is None:
        raise ResourceNotFound("run introuvable", details={"run_id": run_id})
    return run


def run_timeline(
    db: Session,
    ctx: HostContext,
    run_id: str,
    *,
    limit: int = 50,
    cursor: str | None = None,
) -> tuple[AgentRun, list[dict], str | None, bool]:
    """Reconstruit la timeline auditable d'un run depuis `agent_events` (redacted).

    Le journal append-only `agent_events` (P3) EST la source d'audit : chaque
    événement `run.*`/`run.step.*` y est horodaté et séquencé. On borne au tenant,
    on ordonne par séquence croissante et on masque les clés sensibles du payload.
    """
    run = get_run(db, ctx, run_id)  # borne tenant + 404
    limit = max(1, min(limit, 200))

    stmt: Select = select(AgentEvent).where(
        AgentEvent.run_id == run.id,
        AgentEvent.installation_id == _scoped(ctx),
    )
    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded and len(decoded) == 2:
            c_seq, c_id = decoded
            cid = _as_uuid(c_id)
            if cid is not None:
                stmt = stmt.where(
                    tuple_(AgentEvent.sequence, AgentEvent.id) > (int(c_seq), cid)
                )
    stmt = stmt.order_by(AgentEvent.sequence.asc(), AgentEvent.id.asc()).limit(limit + 1)
    events = list(db.scalars(stmt).all())
    has_more = len(events) > limit
    events = events[:limit]

    items = [
        {
            "event_id": ev.event_id,
            "event_type": ev.event_type,
            "sequence": ev.sequence,
            "occurred_at": ev.occurred_at,
            "payload": redact_payload(ev.payload or {}),
        }
        for ev in events
    ]
    next_cursor = None
    if has_more and events:
        last = events[-1]
        next_cursor = _encode_cursor(last.sequence, last.id)
    return run, items, next_cursor, has_more


def redact_payload(payload: dict) -> dict:
    """Masque les clés sensibles d'un payload de timeline (redaction P4).

    Conservateur : toute clé dont le nom contient un marqueur sensible
    (`secret`, `token`, `prompt`, `raw`, …) est remplacée par `"[redacted]"`.
    P6 durcira (redaction structurée, PII). Ne mute jamais l'original.
    """
    out: dict = {}
    for key, value in payload.items():
        lowered = str(key).lower()
        if any(marker in lowered for marker in _REDACT_KEY_MARKERS):
            out[key] = "[redacted]"
        elif isinstance(value, dict):
            out[key] = redact_payload(value)
        else:
            out[key] = value
    return out
