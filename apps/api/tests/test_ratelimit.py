"""Rate-limit fixe (core/ratelimit.py) + garde brute-force sur /auth/login en prod."""
import uuid

import redis

from apps.api.core import ratelimit
from apps.api.core.redis import get_sync_redis


def _unique_key() -> str:
    return f"ratelimit:test:{uuid.uuid4().hex}"


def test_allows_under_limit():
    key = _unique_key()
    try:
        for _ in range(3):
            assert ratelimit.check_and_increment(key, limit=3, window_seconds=60) is True
    finally:
        get_sync_redis().delete(key)


def test_blocks_over_limit():
    key = _unique_key()
    try:
        for _ in range(3):
            ratelimit.check_and_increment(key, limit=3, window_seconds=60)
        assert ratelimit.check_and_increment(key, limit=3, window_seconds=60) is False
    finally:
        get_sync_redis().delete(key)


def test_fails_open_when_redis_unavailable(monkeypatch):
    class _Broken:
        def pipeline(self):
            raise redis.ConnectionError("boom")

    monkeypatch.setattr(ratelimit, "get_sync_redis", lambda: _Broken())
    assert ratelimit.check_and_increment(_unique_key(), limit=1, window_seconds=60) is True


def test_login_rate_limited_in_prod(client, monkeypatch):
    from apps.api.core.config import settings

    monkeypatch.setattr(settings, "environment", "production")
    ip = f"test-{uuid.uuid4().hex}"
    key = f"ratelimit:login:{ip}"
    headers = {"X-Forwarded-For": ip}
    try:
        for _ in range(10):
            client.post(
                "/auth/login", json={"email": "admin@mc.local", "password": "WRONG"}, headers=headers
            )
        r = client.post(
            "/auth/login", json={"email": "admin@mc.local", "password": "WRONG"}, headers=headers
        )
        assert r.status_code == 429
    finally:
        get_sync_redis().delete(key)


def test_login_not_rate_limited_outside_prod(client):
    # `settings.environment` reste "development" par défaut dans le harness de test —
    # aucune limite ne doit s'appliquer, même après de nombreuses tentatives.
    ip = f"test-{uuid.uuid4().hex}"
    headers = {"X-Forwarded-For": ip}
    for _ in range(12):
        r = client.post(
            "/auth/login", json={"email": "admin@mc.local", "password": "WRONG"}, headers=headers
        )
    assert r.status_code == 401
