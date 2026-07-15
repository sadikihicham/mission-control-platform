"""Machines d'état V1 : run, commande, approbation, alerte, credential.

Tables de transition gelées (schéma solution §9). Le serveur fait foi : une
transition non listée est refusée (`state_conflict`). Les états terminaux sont
immuables — un « retry » crée une nouvelle entité liée à la précédente, il ne
rouvre jamais un état terminal. Fonctions pures, sans DB ni domaine.
"""
from enum import Enum


class RunState(str, Enum):
    queued = "queued"
    starting = "starting"
    running = "running"
    waiting_approval = "waiting_approval"
    blocked = "blocked"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"
    timed_out = "timed_out"


class CommandState(str, Enum):
    queued = "queued"
    delivered = "delivered"
    acknowledged = "acknowledged"
    succeeded = "succeeded"
    failed = "failed"
    expired = "expired"
    cancelled = "cancelled"


class ApprovalState(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"
    cancelled = "cancelled"


class AlertState(str, Enum):
    open = "open"
    acknowledged = "acknowledged"
    resolved = "resolved"


class CredentialState(str, Enum):
    active = "active"
    revoked = "revoked"
    expired = "expired"


# Transitions autorisées : état source → ensemble d'états cibles atteignables.
RUN_TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    RunState.queued: frozenset({RunState.starting, RunState.cancelled, RunState.timed_out}),
    RunState.starting: frozenset({RunState.running, RunState.failed, RunState.cancelled}),
    RunState.running: frozenset(
        {
            RunState.waiting_approval,
            RunState.blocked,
            RunState.succeeded,
            RunState.failed,
            RunState.cancelled,
            RunState.timed_out,
        }
    ),
    RunState.waiting_approval: frozenset(
        {RunState.running, RunState.cancelled, RunState.timed_out, RunState.failed}
    ),
    RunState.blocked: frozenset(
        {RunState.running, RunState.cancelled, RunState.timed_out, RunState.failed}
    ),
    RunState.succeeded: frozenset(),
    RunState.failed: frozenset(),
    RunState.cancelled: frozenset(),
    RunState.timed_out: frozenset(),
}

COMMAND_TRANSITIONS: dict[CommandState, frozenset[CommandState]] = {
    CommandState.queued: frozenset(
        {CommandState.delivered, CommandState.expired, CommandState.cancelled}
    ),
    CommandState.delivered: frozenset(
        {CommandState.acknowledged, CommandState.expired, CommandState.cancelled}
    ),
    CommandState.acknowledged: frozenset({CommandState.succeeded, CommandState.failed}),
    CommandState.succeeded: frozenset(),
    CommandState.failed: frozenset(),
    CommandState.expired: frozenset(),
    CommandState.cancelled: frozenset(),
}

APPROVAL_TRANSITIONS: dict[ApprovalState, frozenset[ApprovalState]] = {
    ApprovalState.pending: frozenset(
        {
            ApprovalState.approved,
            ApprovalState.rejected,
            ApprovalState.expired,
            ApprovalState.cancelled,
        }
    ),
    ApprovalState.approved: frozenset(),
    ApprovalState.rejected: frozenset(),
    ApprovalState.expired: frozenset(),
    ApprovalState.cancelled: frozenset(),
}

ALERT_TRANSITIONS: dict[AlertState, frozenset[AlertState]] = {
    AlertState.open: frozenset({AlertState.acknowledged, AlertState.resolved}),
    AlertState.acknowledged: frozenset({AlertState.resolved}),
    AlertState.resolved: frozenset(),
}

CREDENTIAL_TRANSITIONS: dict[CredentialState, frozenset[CredentialState]] = {
    CredentialState.active: frozenset({CredentialState.revoked, CredentialState.expired}),
    CredentialState.revoked: frozenset(),
    CredentialState.expired: frozenset(),
}

# Registre des machines pour un accès générique (nom → table de transition).
_MACHINES: dict[str, dict] = {
    "run": RUN_TRANSITIONS,
    "command": COMMAND_TRANSITIONS,
    "approval": APPROVAL_TRANSITIONS,
    "alert": ALERT_TRANSITIONS,
    "credential": CREDENTIAL_TRANSITIONS,
}


def terminal_states(machine: str) -> frozenset:
    """États sans transition sortante (terminaux, immuables)."""
    table = _MACHINES[machine]
    return frozenset(state for state, targets in table.items() if not targets)


def can_transition(machine: str, src, dst) -> bool:
    """Vrai si `src → dst` est une transition autorisée de la machine nommée."""
    table = _MACHINES[machine]
    return dst in table.get(src, frozenset())
