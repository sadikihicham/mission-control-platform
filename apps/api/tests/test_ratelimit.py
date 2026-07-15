"""Rate-limit fixe (core/ratelimit.py) + garde brute-force sur /auth/login et
/auth/change-password en prod."""
import socket
import uuid

import redis

from apps.api.core import ratelimit
from apps.api.core.redis import get_sync_redis
from apps.api.tests.conftest import auth


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
    monkeypatch.setattr(settings, "trusted_proxies", [])
    email = f"ratelimited-{uuid.uuid4().hex}@mc.local"
    ip_key = "ratelimit:login:ip:testclient"
    email_key = f"ratelimit:login:email:{email}"
    try:
        for _ in range(10):
            client.post("/auth/login", json={"email": email, "password": "WRONG"})
        r = client.post("/auth/login", json={"email": email, "password": "WRONG"})
        assert r.status_code == 429
    finally:
        get_sync_redis().delete(ip_key)
        get_sync_redis().delete(email_key)


def test_xff_spoofing_no_longer_bypasses_ip_limit(client, monkeypatch):
    """Régression : sans proxy de confiance déclaré, un `X-Forwarded-For` différent
    à chaque requête (et un email différent à chaque fois) ne doit plus permettre de
    contourner la limite — seul le vrai peer TCP compte."""
    from apps.api.core.config import settings

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "trusted_proxies", [])
    ip_key = "ratelimit:login:ip:testclient"
    emails = [f"spoof-{uuid.uuid4().hex}@mc.local" for _ in range(11)]
    try:
        for i, email in enumerate(emails[:10]):
            client.post(
                "/auth/login",
                json={"email": email, "password": "WRONG"},
                headers={"X-Forwarded-For": f"1.2.3.{i}"},
            )
        r = client.post(
            "/auth/login",
            json={"email": emails[10], "password": "WRONG"},
            headers={"X-Forwarded-For": "9.9.9.9"},
        )
        assert r.status_code == 429
    finally:
        get_sync_redis().delete(ip_key)
        for email in emails:
            get_sync_redis().delete(f"ratelimit:login:email:{email}")


def test_xff_honored_behind_trusted_proxy_but_email_key_still_limits(client, monkeypatch):
    """Derrière un proxy de confiance déclaré, `X-Forwarded-For` est honoré (IPs
    client distinctes = compteurs distincts, comportement voulu) — mais la 2e clé
    par email empêche qu'un attaquant contourne la limite en faisant simplement
    tourner ses IPs source contre un seul compte."""
    from apps.api.core.config import settings

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "trusted_proxies", ["testclient"])
    email = f"rotated-ip-{uuid.uuid4().hex}@mc.local"
    email_key = f"ratelimit:login:email:{email}"
    ips = [f"10.0.0.{i}" for i in range(11)]
    try:
        for ip in ips[:10]:
            client.post(
                "/auth/login",
                json={"email": email, "password": "WRONG"},
                headers={"X-Forwarded-For": ip},
            )
        r = client.post(
            "/auth/login",
            json={"email": email, "password": "WRONG"},
            headers={"X-Forwarded-For": ips[10]},
        )
        assert r.status_code == 429
    finally:
        get_sync_redis().delete(email_key)
        for ip in ips:
            get_sync_redis().delete(f"ratelimit:login:ip:{ip}")


def test_trusted_proxy_resolved_by_hostname(client, monkeypatch):
    """`trusted_proxies` accepte un nom résolu par DNS (ex. `caddy` en prod
    co-hébergée, cf. docs/DEPLOY_FRONTED.md), pas seulement une IP littérale —
    résolu à chaque requête pour survivre à un `--force-recreate` de Caddy."""
    from apps.api.core.config import settings

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "trusted_proxies", ["caddy"])

    def fake_gethostbyname(name):
        if name == "caddy":
            return "testclient"
        raise OSError(f"lookup DNS inattendu pour {name!r}")

    monkeypatch.setattr(socket, "gethostbyname", fake_gethostbyname)

    email = f"caddy-dns-{uuid.uuid4().hex}@mc.local"
    xff_ip_key = "ratelimit:login:ip:203.0.113.7"
    r = get_sync_redis()
    try:
        client.post(
            "/auth/login",
            json={"email": email, "password": "WRONG"},
            headers={"X-Forwarded-For": "203.0.113.7"},
        )
        # La clé est bâtie sur l'IP du header, pas sur "testclient" (le peer TCP) —
        # preuve que "caddy" a bien été résolu et considéré de confiance.
        assert r.get(xff_ip_key) is not None
    finally:
        r.delete(xff_ip_key)
        r.delete(f"ratelimit:login:email:{email}")


def test_unresolvable_trusted_proxy_hostname_does_not_break_login(client, monkeypatch):
    """Une entrée `trusted_proxies` non résolvable (Caddy pas encore démarré, DNS en
    hoquet) ne doit jamais faire planter /auth/login — juste ne pas être honorée."""
    from apps.api.core.config import settings

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "trusted_proxies", ["caddy"])
    monkeypatch.setattr(
        socket, "gethostbyname", lambda name: (_ for _ in ()).throw(OSError("no such host"))
    )
    r = get_sync_redis()
    try:
        resp = client.post(
            "/auth/login",
            json={"email": "admin@mc.local", "password": "WRONG"},
            headers={"X-Forwarded-For": "203.0.113.7"},
        )
        assert resp.status_code == 401
    finally:
        r.delete("ratelimit:login:ip:testclient")
        r.delete("ratelimit:login:email:admin@mc.local")


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


def test_change_password_rate_limited_in_prod(client, make_user, monkeypatch):
    """Un JWT volé/partagé ne doit pas pouvoir deviner le mot de passe actuel par
    force brute via /auth/change-password — même garde IP+utilisateur qu'au login."""
    from apps.api.core.config import settings

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "trusted_proxies", [])
    email = make_user(password="initial1")
    token = client.post("/auth/login", json={"email": email, "password": "initial1"}).json()[
        "access_token"
    ]
    user_id = client.get("/auth/me", headers=auth(token)).json()["id"]
    ip_key = "ratelimit:change-password:ip:testclient"
    user_key = f"ratelimit:change-password:user:{user_id}"
    try:
        for _ in range(10):
            client.post(
                "/auth/change-password",
                json={"current_password": "WRONG", "new_password": "brandnew1"},
                headers=auth(token),
            )
        r = client.post(
            "/auth/change-password",
            json={"current_password": "WRONG", "new_password": "brandnew1"},
            headers=auth(token),
        )
        assert r.status_code == 429
    finally:
        get_sync_redis().delete(ip_key)
        get_sync_redis().delete(user_key)


def test_change_password_not_rate_limited_outside_prod(client, make_user):
    # Même garde qu'au login : hors prod, jamais de 429 même après de nombreuses
    # tentatives (les fixtures/tests appellent cette route en boucle).
    email = make_user(password="initial1")
    token = client.post("/auth/login", json={"email": email, "password": "initial1"}).json()[
        "access_token"
    ]
    for _ in range(12):
        r = client.post(
            "/auth/change-password",
            json={"current_password": "WRONG", "new_password": "brandnew1"},
            headers=auth(token),
        )
    assert r.status_code == 400
