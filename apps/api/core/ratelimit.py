"""Rate-limit fixe par fenêtre, best-effort — même philosophie que
`core/redis.publish_event` : une panne Redis ne doit jamais bloquer une action
utilisateur, seulement désactiver silencieusement la protection (fail-open)."""
import redis

from apps.api.core.redis import get_sync_redis


def check_and_increment(
    key: str, *, limit: int, window_seconds: int, client: redis.Redis | None = None
) -> bool:
    """Incrémente le compteur `key` sur la fenêtre courante. Renvoie False si
    `limit` est dépassé, True sinon (y compris si Redis est indisponible)."""
    try:
        r = client or get_sync_redis()
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds, nx=True)
        count, _ = pipe.execute()
        return count <= limit
    except redis.RedisError:
        return True
