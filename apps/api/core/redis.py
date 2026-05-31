"""Accès Redis partagé — pub/sub temps réel (Contract E).

- `publish_event` (sync) : utilisé par `api` dans l'endpoint heartbeat.
- `get_async_redis` : utilisé par `realtime` pour s'abonner et relayer en WS.
"""
import json

import redis
import redis.asyncio as aioredis

from apps.api.core.config import settings

EVENTS_CHANNEL = "mc:events"

_sync: redis.Redis | None = None
_async: aioredis.Redis | None = None


def get_sync_redis() -> redis.Redis:
    global _sync
    if _sync is None:
        _sync = redis.from_url(settings.redis_url, decode_responses=True)
    return _sync


def get_async_redis() -> aioredis.Redis:
    global _async
    if _async is None:
        _async = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _async


def publish_event(event_type: str, data: dict) -> None:
    """Publie un message Contract E sur le canal d'événements (sync, non bloquant)."""
    message = json.dumps({"type": event_type, "data": data}, default=str)
    try:
        get_sync_redis().publish(EVENTS_CHANNEL, message)
    except redis.RedisError:
        # La persistance DB a déjà réussi ; un Redis indisponible ne doit pas
        # faire échouer l'ingest.
        pass
