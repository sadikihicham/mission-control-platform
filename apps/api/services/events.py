"""Helpers d'événements temps réel (Contract E)."""
from apps.api.core.redis import publish_event
from apps.api.services import agents_db


def publish_stats() -> None:
    """Publie les KPIs courants (stats.update) — déclenché après tout changement."""
    publish_event("stats.update", agents_db.dashboard_stats().model_dump())
