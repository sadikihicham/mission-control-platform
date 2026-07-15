"""Moteur de politiques déterministe `allow|deny|require_approval` (P5, SP3).

Évaluation d'une action `(agent, command_type, project)` contre les politiques
**actives** du tenant courant. Déterministe et **auditée** : à jeu de politiques
donné, le résultat est toujours le même et la décision est journalisée
(`ActivityLog type="policy.evaluated"`) avec qui/quoi a été évalué et le résultat.

Ordre de résolution (la **première** politique gagnante l'emporte) :

1. priorité décroissante (`priority`) ;
2. spécificité de portée décroissante : `agent` > `project` > `installation` ;
3. action exacte avant joker (`command_type` littéral > `*`) ;
4. ancienneté croissante (`created_at`) puis `id` — départage stable.

Aucune politique applicable → effet par défaut `MC_POLICY_DEFAULT_EFFECT`
(`allow` par défaut ; `deny` pour un mode fail-closed strict). Le service CRUD des
politiques vit ici aussi (création/mise à jour/désactivation), tenant-scoped.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import Select, select, update
from sqlalchemy.orm import Session

from apps.api.agent_control.control.schemas import (
    POLICY_EFFECTS,
    POLICY_SCOPES,
    PolicyCreate,
    PolicyUpdate,
)
from apps.api.core.config import settings
from apps.api.integrations.errors import (
    ResourceNotFound,
    StateConflict,
    ValidationFailed,
)
from apps.api.integrations.host_context import HostContext
from apps.api.models import ActivityLog, Agent, AgentPolicy

# Spécificité de portée (plus grand = plus spécifique, l'emporte à priorité égale).
_SCOPE_SPECIFICITY: dict[str, int] = {"agent": 3, "project": 2, "installation": 1}


@dataclass(frozen=True)
class PolicyDecision:
    """Résultat d'une évaluation de politique (déterministe)."""

    effect: str                       # allow | deny | require_approval
    policy: AgentPolicy | None        # politique gagnante, None si effet par défaut
    risk_level: str | None            # risque attaché (si require_approval)

    @property
    def policy_id(self) -> uuid.UUID | None:
        return self.policy.id if self.policy is not None else None


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


def _matches(policy: AgentPolicy, agent: Agent, command_type: str, project_id) -> bool:
    """Vrai si la politique s'applique à l'action évaluée (portée ET action)."""
    if policy.scope_type == "installation":
        scope_ok = True
    elif policy.scope_type == "agent":
        scope_ok = policy.scope_id == agent.id
    elif policy.scope_type == "project":
        scope_ok = project_id is not None and policy.scope_id == project_id
    else:
        scope_ok = False
    if not scope_ok:
        return False
    return policy.action_type == "*" or policy.action_type == command_type


def _resolution_key(policy: AgentPolicy):
    """Clé de tri : le minimum est la politique gagnante (ordre déterministe)."""
    action_specificity = 0 if policy.action_type == "*" else 1
    return (
        -policy.priority,
        -_SCOPE_SPECIFICITY.get(policy.scope_type, 0),
        -action_specificity,
        policy.created_at,
        str(policy.id),
    )


def evaluate_policy(
    db: Session,
    ctx: HostContext,
    *,
    agent: Agent,
    command_type: str,
    project_id=None,
    audit_context: dict | None = None,
) -> PolicyDecision:
    """Évalue l'action contre les politiques actives du tenant. Déterministe + audité.

    Écrit une entrée d'audit `policy.evaluated` (qui/quoi/résultat) dans la même
    session : la décision reste traçable même sans le système d'audit complet (P6).
    N'exécute pas de commit (l'appelant commite dans la transaction métier).
    """
    tenant = _tenant(ctx)
    project = _as_uuid(project_id)
    policies = list(
        db.scalars(
            select(AgentPolicy).where(
                AgentPolicy.installation_id == tenant,
                AgentPolicy.status == "active",
            )
        ).all()
    )
    applicable = [p for p in policies if _matches(p, agent, command_type, project)]
    if applicable:
        applicable.sort(key=_resolution_key)
        winner = applicable[0]
        decision = PolicyDecision(
            effect=winner.effect, policy=winner, risk_level=winner.risk_level
        )
    else:
        decision = PolicyDecision(
            effect=settings.mc_policy_default_effect, policy=None, risk_level=None
        )

    _audit_decision(db, ctx, agent, command_type, decision, audit_context)
    return decision


def _audit_decision(
    db: Session,
    ctx: HostContext,
    agent: Agent,
    command_type: str,
    decision: PolicyDecision,
    audit_context: dict | None,
) -> None:
    """Journalise la décision de policy (traçabilité minimale P5, ADR audit P6)."""
    payload = {
        "agent_key": agent.agent_key,
        "command_type": command_type,
        "effect": decision.effect,
        "policy_id": str(decision.policy_id) if decision.policy_id else None,
        "scope_type": decision.policy.scope_type if decision.policy else "default",
        "priority": decision.policy.priority if decision.policy else None,
        "request_id": ctx.request_id,
        "user": ctx.user.external_user_id,
    }
    if audit_context:
        payload.update(audit_context)
    db.add(
        ActivityLog(
            agent_id=agent.id,
            project_id=None,
            type="policy.evaluated",
            payload=payload,
        )
    )


# --- CRUD des politiques (tenant-scoped) --------------------------------------


def _validate_effect(effect: str | None) -> None:
    if effect is not None and effect not in POLICY_EFFECTS:
        raise ValidationFailed(
            f"effet de politique invalide : {effect}",
            details={"allowed": sorted(POLICY_EFFECTS)},
        )


def _validate_scope(scope_type: str | None, scope_id) -> None:
    if scope_type is None:
        return
    if scope_type not in POLICY_SCOPES:
        raise ValidationFailed(
            f"portée de politique invalide : {scope_type}",
            details={"allowed": sorted(POLICY_SCOPES)},
        )
    if scope_type in ("agent", "project") and scope_id is None:
        raise ValidationFailed(
            f"scope_id requis pour la portée {scope_type}",
            details={"scope_type": scope_type},
        )


def create_policy(db: Session, ctx: HostContext, body: PolicyCreate) -> AgentPolicy:
    """Crée une politique dans le tenant courant (capacité `admin`)."""
    _validate_effect(body.effect)
    _validate_scope(body.scope_type, body.scope_id)
    policy = AgentPolicy(
        installation_id=_tenant(ctx),
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        action_type=body.action_type or "*",
        effect=body.effect,
        risk_level=body.risk_level,
        conditions=body.conditions or {},
        priority=body.priority,
        description=body.description,
        status="active",
        created_by=_as_uuid(ctx.user.local_user_id),
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


def _get_policy_in_scope(db: Session, ctx: HostContext, policy_id: str) -> AgentPolicy:
    pid = _as_uuid(policy_id)
    if pid is None:
        raise ResourceNotFound("politique introuvable", details={"policy_id": policy_id})
    policy = db.scalar(
        select(AgentPolicy).where(
            AgentPolicy.id == pid, AgentPolicy.installation_id == _tenant(ctx)
        )
    )
    if policy is None:
        raise ResourceNotFound("politique introuvable", details={"policy_id": policy_id})
    return policy


def update_policy(
    db: Session, ctx: HostContext, policy_id: str, body: PolicyUpdate
) -> AgentPolicy:
    """Met à jour une politique avec verrou optimiste (`version` attendue)."""
    policy = _get_policy_in_scope(db, ctx, policy_id)
    if policy.version != body.version:
        raise StateConflict(
            "version de politique périmée (édition concurrente)",
            details={"expected": body.version, "current": policy.version},
        )
    _validate_effect(body.effect)
    _validate_scope(
        body.scope_type or policy.scope_type,
        body.scope_id if body.scope_id is not None else policy.scope_id,
    )
    if body.scope_type is not None:
        policy.scope_type = body.scope_type
    if body.scope_id is not None:
        policy.scope_id = body.scope_id
    if body.action_type is not None:
        policy.action_type = body.action_type
    if body.effect is not None:
        policy.effect = body.effect
    if body.risk_level is not None:
        policy.risk_level = body.risk_level
    if body.conditions is not None:
        policy.conditions = body.conditions
    if body.priority is not None:
        policy.priority = body.priority
    if body.status is not None:
        policy.status = body.status
    if body.description is not None:
        policy.description = body.description
    policy.version += 1
    db.commit()
    db.refresh(policy)
    return policy


def disable_policy(db: Session, ctx: HostContext, policy_id: str) -> None:
    """Désactive une politique (soft delete : `status='disabled'`, jamais évaluée).

    On ne hard-delete pas : l'historique des décisions référence `policy_id`
    (audit). Une politique désactivée est exclue de l'évaluation (fail-closed).
    """
    policy = _get_policy_in_scope(db, ctx, policy_id)
    db.execute(
        update(AgentPolicy)
        .where(AgentPolicy.id == policy.id)
        .values(status="disabled", version=AgentPolicy.version + 1)
    )
    db.commit()


def list_policies(
    db: Session, ctx: HostContext, *, limit: int = 50
) -> list[AgentPolicy]:
    """Liste les politiques du tenant (ordre : priorité puis récence)."""
    limit = max(1, min(limit, 200))
    stmt: Select = (
        select(AgentPolicy)
        .where(AgentPolicy.installation_id == _tenant(ctx))
        .order_by(AgentPolicy.priority.desc(), AgentPolicy.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())
