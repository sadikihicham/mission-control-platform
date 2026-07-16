"""Moteur de budgets — seuils, alertes, comportement au dépassement (P6, SP6).

Un budget borne un montant sur une portée (installation|project|agent) et une
période (daily|weekly|monthly|total). La consommation est **recalculée** depuis
`agent_usage_records` (source unique, toujours réconciliable) sur la fenêtre de
la période courante — jamais dénormalisée.

Deux responsabilités :

1. **Évaluation** (`evaluate_budgets`) : après une consommation, pour chaque budget
   applicable, calculer le pourcentage consommé et, à chaque **nouveau** seuil
   franchi (défaut 50/80/100), ouvrir une alerte **dédupliquée** (`budget:{id}:
   threshold:{n}`) et émettre l'événement outbox (`budget.threshold_reached` /
   `budget.exceeded`). Répéter des consommations qui restent au même palier ne
   re-notifie pas (dédup). Appelé DANS la transaction d'ingest (pas de commit).

2. **Gate** (`budget_gate`) : au point de contrôle P5 (soumission de commande),
   renvoyer le comportement à appliquer si un budget applicable est **dépassé**
   (100 %) : `block` (→ `budget_exceeded`, aucune commande) ou `require_approval`
   (→ force l'approbation même si la policy disait `allow`). C'est l'articulation
   budget × policy demandée : un budget dépassé durcit l'effet de la policy.

CRUD budget audité (création/modification = `budget.created`/`budget.updated`).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from apps.api.agent_control.operations import alerts as alerts_service
from apps.api.agent_control.operations import audit as audit_service
from apps.api.agent_control.operations import usage as usage_service
from apps.api.agent_control.operations.outbox import emit_outbox
from apps.api.integrations.errors import ResourceNotFound, StateConflict, ValidationFailed
from apps.api.integrations.host_context import HostContext
from apps.api.models import AgentBudget

BUDGET_SCOPES = frozenset({"installation", "project", "agent"})
BUDGET_PERIODS = frozenset({"daily", "weekly", "monthly", "total"})
ON_EXCEED = frozenset({"alert", "require_approval", "block_new_runs"})
DEFAULT_THRESHOLDS = (50, 80, 100)

# Sévérité de l'alerte selon le seuil franchi (100 % = critique).
_SEVERITY_BY_THRESHOLD = {50: "info", 80: "warning", 100: "critical"}


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


def period_start(period: str, now: datetime) -> datetime | None:
    """Début de la fenêtre courante d'une période. `total` → `None` (tout l'historique)."""
    if period == "total":
        return None
    if period == "daily":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "weekly":
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return midnight - timedelta(days=midnight.weekday())
    # monthly (défaut)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _thresholds(budget: AgentBudget) -> list[int]:
    raw = budget.thresholds or list(DEFAULT_THRESHOLDS)
    out = sorted({int(t) for t in raw if 0 < int(t) <= 100})
    return out or list(DEFAULT_THRESHOLDS)


def applicable_budgets(
    db: Session, installation_id, *, agent_id=None, project_id=None
) -> list[AgentBudget]:
    """Budgets actifs du tenant dont la portée couvre l'action (installation/project/agent)."""
    inst = _as_uuid(installation_id)
    budgets = list(
        db.scalars(
            select(AgentBudget).where(
                AgentBudget.installation_id == inst, AgentBudget.status == "active"
            )
        ).all()
    )
    aid = _as_uuid(agent_id)
    pid = _as_uuid(project_id)
    out: list[AgentBudget] = []
    for b in budgets:
        if b.scope_type == "installation":
            out.append(b)
        elif b.scope_type == "agent" and b.scope_id == aid and aid is not None:
            out.append(b)
        elif b.scope_type == "project" and b.scope_id == pid and pid is not None:
            out.append(b)
    return out


def consumed_and_pct(
    db: Session, budget: AgentBudget, *, at: datetime | None = None
) -> tuple[Decimal, Decimal]:
    """Consommation courante et pourcentage du budget (borné à la période)."""
    now = at or _now()
    since = period_start(budget.period, now)
    consumed = usage_service.consumption_for(
        db,
        budget.installation_id,
        scope_type=budget.scope_type,
        scope_id=budget.scope_id,
        since=since,
    )
    if budget.amount_limit and budget.amount_limit > 0:
        pct = (consumed / budget.amount_limit) * Decimal(100)
    else:
        pct = Decimal(0)
    return consumed, pct


@dataclass
class BudgetEvaluation:
    budget_id: uuid.UUID
    consumed: Decimal
    pct: Decimal
    thresholds_crossed: list[int] = field(default_factory=list)
    exceeded: bool = False


def evaluate_budgets(
    db: Session,
    installation_id,
    *,
    agent_id=None,
    project_id=None,
    at: datetime | None = None,
) -> list[BudgetEvaluation]:
    """Évalue les budgets applicables ; ouvre alertes dédupliquées aux seuils franchis.

    Ne commit pas (transaction d'ingest appelante). Pour chaque budget applicable,
    à chaque seuil `t` tel que `pct >= t` sans alerte active `budget:{id}:
    threshold:{t}`, ouvre une alerte et émet l'événement outbox correspondant.
    """
    now = at or _now()
    evaluations: list[BudgetEvaluation] = []
    for budget in applicable_budgets(
        db, installation_id, agent_id=agent_id, project_id=project_id
    ):
        consumed, pct = consumed_and_pct(db, budget, at=now)
        ev = BudgetEvaluation(
            budget_id=budget.id, consumed=consumed, pct=pct, exceeded=pct >= Decimal(100)
        )
        for threshold in _thresholds(budget):
            if pct < Decimal(threshold):
                continue
            dedup_key = f"budget:{budget.id}:threshold:{threshold}"
            _, created = alerts_service.open_alert(
                db,
                installation_id=budget.installation_id,
                alert_type="budget_exceeded" if threshold >= 100 else "budget_threshold",
                dedup_key=dedup_key,
                title=(
                    f"Budget dépassé ({budget.scope_type})"
                    if threshold >= 100
                    else f"Budget à {threshold}% ({budget.scope_type})"
                ),
                severity=_SEVERITY_BY_THRESHOLD.get(threshold, "warning"),
                target_type="budget",
                target_id=budget.id,
                details={
                    "budget_id": str(budget.id),
                    "threshold": threshold,
                    "consumed": str(consumed),
                    "limit": str(budget.amount_limit),
                    "currency": budget.currency,
                    "on_exceed": budget.on_exceed,
                },
            )
            if created:
                ev.thresholds_crossed.append(threshold)
                emit_outbox(
                    db,
                    installation_id=budget.installation_id,
                    event_type="budget.exceeded" if threshold >= 100 else "budget.threshold_reached",
                    topic="fleet",
                    payload={
                        "budget_id": str(budget.id),
                        "threshold": threshold,
                        "consumed": str(consumed),
                        "limit": str(budget.amount_limit),
                        "on_exceed": budget.on_exceed,
                    },
                )
        evaluations.append(ev)
    return evaluations


# --- Gate d'articulation avec la policy P5 ------------------------------------

# Comportement renvoyé au point de contrôle (soumission de commande).
GATE_ALLOW = "allow"
GATE_REQUIRE_APPROVAL = "require_approval"
GATE_BLOCK = "block"


@dataclass(frozen=True)
class BudgetGateDecision:
    behavior: str  # allow | require_approval | block
    budget_id: uuid.UUID | None = None
    consumed: Decimal | None = None
    limit: Decimal | None = None


def budget_gate(
    db: Session,
    installation_id,
    *,
    agent_id=None,
    project_id=None,
    at: datetime | None = None,
) -> BudgetGateDecision:
    """Décision budget au point de contrôle P5 : `allow|require_approval|block`.

    Un budget applicable **dépassé** (>=100 %) avec `on_exceed=block_new_runs`
    → `block` (le plus strict, l'emporte). Sinon `require_approval` si un budget
    dépassé l'exige. Sinon `allow`. `on_exceed=alert` n'influe jamais sur le gate
    (l'alerte est déjà émise à l'évaluation) — il n'introduit aucun blocage.
    """
    now = at or _now()
    strictest = BudgetGateDecision(behavior=GATE_ALLOW)
    for budget in applicable_budgets(
        db, installation_id, agent_id=agent_id, project_id=project_id
    ):
        consumed, pct = consumed_and_pct(db, budget, at=now)
        if pct < Decimal(100):
            continue
        if budget.on_exceed == "block_new_runs":
            return BudgetGateDecision(
                behavior=GATE_BLOCK,
                budget_id=budget.id,
                consumed=consumed,
                limit=budget.amount_limit,
            )
        if budget.on_exceed == "require_approval" and strictest.behavior == GATE_ALLOW:
            strictest = BudgetGateDecision(
                behavior=GATE_REQUIRE_APPROVAL,
                budget_id=budget.id,
                consumed=consumed,
                limit=budget.amount_limit,
            )
    return strictest


# --- CRUD (capacité view_costs, audité) ---------------------------------------


def _validate(scope_type, period, on_exceed, thresholds) -> None:
    if scope_type is not None and scope_type not in BUDGET_SCOPES:
        raise ValidationFailed(
            f"portée de budget invalide : {scope_type}",
            details={"allowed": sorted(BUDGET_SCOPES)},
        )
    if period is not None and period not in BUDGET_PERIODS:
        raise ValidationFailed(
            f"période de budget invalide : {period}",
            details={"allowed": sorted(BUDGET_PERIODS)},
        )
    if on_exceed is not None and on_exceed not in ON_EXCEED:
        raise ValidationFailed(
            f"comportement au dépassement invalide : {on_exceed}",
            details={"allowed": sorted(ON_EXCEED)},
        )
    if thresholds is not None:
        for t in thresholds:
            if not isinstance(t, int) or not (0 < t <= 100):
                raise ValidationFailed(
                    "seuils invalides : entiers 1..100 attendus",
                    details={"thresholds": thresholds},
                )


def create_budget(db: Session, ctx: HostContext, body, *, ip: str | None = None) -> AgentBudget:
    """Crée un budget dans le tenant courant (capacité `view_costs`). Audité."""
    _validate(body.scope_type, body.period, body.on_exceed, body.thresholds)
    if body.scope_type in ("agent", "project") and body.scope_id is None:
        raise ValidationFailed(
            f"scope_id requis pour la portée {body.scope_type}",
            details={"scope_type": body.scope_type},
        )
    if body.amount_limit is None or body.amount_limit <= 0:
        raise ValidationFailed("amount_limit doit être strictement positif")
    budget = AgentBudget(
        installation_id=_tenant(ctx),
        scope_type=body.scope_type or "installation",
        scope_id=_as_uuid(body.scope_id),
        period=body.period or "monthly",
        currency=body.currency or "USD",
        amount_limit=body.amount_limit,
        thresholds=body.thresholds or list(DEFAULT_THRESHOLDS),
        on_exceed=body.on_exceed or "alert",
        status="active",
        description=body.description,
        created_by=_as_uuid(ctx.user.local_user_id),
    )
    db.add(budget)
    db.flush()
    audit_service.audit_from_context(
        db,
        ctx,
        action="budget.created",
        target_type="budget",
        target_id=str(budget.id),
        after={
            "scope_type": budget.scope_type,
            "period": budget.period,
            "amount_limit": str(budget.amount_limit),
            "on_exceed": budget.on_exceed,
        },
        ip=ip,
    )
    db.commit()
    db.refresh(budget)
    return budget


def _get_in_scope(db: Session, ctx: HostContext, budget_id: str) -> AgentBudget:
    bid = _as_uuid(budget_id)
    if bid is None:
        raise ResourceNotFound("budget introuvable", details={"budget_id": budget_id})
    budget = db.scalar(
        select(AgentBudget).where(
            AgentBudget.id == bid, AgentBudget.installation_id == _tenant(ctx)
        )
    )
    if budget is None:
        raise ResourceNotFound("budget introuvable", details={"budget_id": budget_id})
    return budget


def update_budget(
    db: Session, ctx: HostContext, budget_id: str, body, *, ip: str | None = None
) -> AgentBudget:
    """Met à jour un budget avec verrou optimiste (`version`). Audité (avant/après)."""
    budget = _get_in_scope(db, ctx, budget_id)
    if budget.version != body.version:
        raise StateConflict(
            "version de budget périmée (édition concurrente)",
            details={"expected": body.version, "current": budget.version},
        )
    _validate(body.scope_type, body.period, body.on_exceed, body.thresholds)
    before = {
        "amount_limit": str(budget.amount_limit),
        "on_exceed": budget.on_exceed,
        "status": budget.status,
        "thresholds": list(budget.thresholds or []),
    }
    if body.amount_limit is not None:
        if body.amount_limit <= 0:
            raise ValidationFailed("amount_limit doit être strictement positif")
        budget.amount_limit = body.amount_limit
    if body.thresholds is not None:
        budget.thresholds = body.thresholds
    if body.on_exceed is not None:
        budget.on_exceed = body.on_exceed
    if body.period is not None:
        budget.period = body.period
    if body.status is not None:
        budget.status = body.status
    if body.description is not None:
        budget.description = body.description
    budget.version += 1
    db.flush()
    audit_service.audit_from_context(
        db,
        ctx,
        action="budget.updated",
        target_type="budget",
        target_id=str(budget.id),
        before=before,
        after={
            "amount_limit": str(budget.amount_limit),
            "on_exceed": budget.on_exceed,
            "status": budget.status,
            "thresholds": list(budget.thresholds or []),
        },
        ip=ip,
    )
    db.commit()
    db.refresh(budget)
    return budget


def get_budget(db: Session, ctx: HostContext, budget_id: str) -> AgentBudget:
    """Charge un budget borné au tenant. 404 hors tenant/inexistant."""
    return _get_in_scope(db, ctx, budget_id)


def list_budgets(db: Session, ctx: HostContext, *, limit: int = 50) -> list[AgentBudget]:
    """Liste les budgets du tenant (récence décroissante)."""
    limit = max(1, min(limit, 200))
    stmt: Select = (
        select(AgentBudget)
        .where(AgentBudget.installation_id == _tenant(ctx))
        .order_by(AgentBudget.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())
