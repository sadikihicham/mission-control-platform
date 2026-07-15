"""Catalogue gelé des `event_type` V1 et des topics WS autorisés.

Les producteurs (SP4) et le frontend (SP5) ne doivent jamais inventer un type
d'événement ou un topic hors de ces ensembles. Distinct des types V0 du canal
`mc:events` (`agent.update`, `agent.stale`, `stats.update`, `refresh`), qui
restent inchangés sur `/ws`. Les événements V1 transitent par l'outbox puis le
canal V1 (`ac:events`) vers `/agent-control/ws`.
"""

# Types d'événements V1 (append-only dans `agent_events`, diffusés en WS V1).
EVENT_TYPES: frozenset[str] = frozenset(
    {
        # Cycle de vie du registre d'agent
        "agent.registered",
        "agent.updated",
        "agent.suspended",
        "agent.resumed",
        "agent.revoked",
        "agent.archived",
        "agent.heartbeat",
        # Runs
        "run.queued",
        "run.starting",
        "run.running",
        "run.waiting_approval",
        "run.blocked",
        "run.succeeded",
        "run.failed",
        "run.cancelled",
        "run.timed_out",
        # Étapes de run / tool calls
        "run.step.started",
        "run.step.completed",
        "run.step.failed",
        # Commandes
        "command.queued",
        "command.delivered",
        "command.acknowledged",
        "command.succeeded",
        "command.failed",
        "command.expired",
        "command.cancelled",
        # Approbations
        "approval.requested",
        "approval.approved",
        "approval.rejected",
        "approval.expired",
        "approval.cancelled",
        # Alertes
        "alert.opened",
        "alert.acknowledged",
        "alert.resolved",
        # Coûts / budgets
        "usage.recorded",
        "budget.threshold_reached",
        "budget.exceeded",
    }
)

# Familles de topics WS V1. Un topic paramétré s'écrit `famille:{id}`.
# Le serveur vérifie tenant + capacité avant d'autoriser une souscription ;
# le client ne choisit jamais un tenant arbitraire.
WS_TOPIC_FAMILIES: frozenset[str] = frozenset(
    {
        "fleet",          # santé/flotte du tenant courant
        "project",        # project:{id}
        "agent",          # agent:{id}
        "run",            # run:{id}
        "approvals",      # file d'approbations du tenant
    }
)

# Topics non paramétrés (souscription directe, sans identifiant).
WS_TOPICS_SCALAR: frozenset[str] = frozenset({"fleet", "approvals"})


def is_valid_topic(topic: str) -> bool:
    """Vrai si `topic` appartient à une famille autorisée (`fleet`, `project:{id}`…)."""
    if topic in WS_TOPICS_SCALAR:
        return True
    family, _, ident = topic.partition(":")
    return bool(ident) and family in (WS_TOPIC_FAMILIES - WS_TOPICS_SCALAR)
