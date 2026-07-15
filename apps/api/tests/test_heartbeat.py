"""Ingest heartbeat (Contract D) → DB."""
from apps.api.tests.conftest import auth

HB = {"Content-Type": "application/json"}


def test_heartbeat_ingest(client, admin_token):
    r = client.post(
        "/agents/heartbeat",
        headers={"X-MC-Token": "test-ingest"},
        json={"agent": "test-worker", "state": "working", "task": "unit", "progress": 42, "tasks_done": 1, "tasks_total": 3, "module": "T0"},
    )
    assert r.status_code == 202
    assert r.json()["agent"] == "test-worker"
    # l'agent est persisté et visible via /agents
    agents = client.get("/agents", headers=auth(admin_token)).json()
    a = next((x for x in agents if x["agent"] == "test-worker"), None)
    assert a and a["state"] == "working" and a["progress"] == 42
    assert a["tasks_total"] == 3  # rangé dans meta


def test_heartbeat_bad_token(client):
    r = client.post("/agents/heartbeat", headers={"X-MC-Token": "WRONG"}, json={"agent": "x", "state": "idle"})
    assert r.status_code == 403


def test_heartbeat_invalid_state(client):
    r = client.post("/agents/heartbeat", headers={"X-MC-Token": "test-ingest"}, json={"agent": "y", "state": "stale"})
    assert r.status_code == 422  # 'stale' est dérivé serveur, pas ingérable


def test_heartbeat_without_enroll_header_keeps_legacy_behavior(client):
    """Non-régression : sans X-MC-Enroll (client non mis à jour), l'agent n'est
    jamais enrôlé — le secret partagé continue de fonctionner à chaque appel."""
    for _ in range(3):
        r = client.post(
            "/agents/heartbeat",
            headers={"X-MC-Token": "test-ingest"},
            json={"agent": "legacy-agent", "state": "idle"},
        )
        assert r.status_code == 202
        assert "agent_token" not in r.json()


def test_heartbeat_enroll_issues_agent_token(client):
    r = client.post(
        "/agents/heartbeat",
        headers={"X-MC-Token": "test-ingest", "X-MC-Enroll": "1"},
        json={"agent": "enroll-agent", "state": "idle"},
    )
    assert r.status_code == 202
    token = r.json()["agent_token"]
    assert token

    # Enrôlé : le secret partagé ne suffit plus.
    r2 = client.post(
        "/agents/heartbeat",
        headers={"X-MC-Token": "test-ingest"},
        json={"agent": "enroll-agent", "state": "working"},
    )
    assert r2.status_code == 403

    # Son propre token, lui, fonctionne — et n'est plus jamais renvoyé ensuite.
    r3 = client.post(
        "/agents/heartbeat",
        headers={"X-MC-Token": token},
        json={"agent": "enroll-agent", "state": "working"},
    )
    assert r3.status_code == 202
    assert "agent_token" not in r3.json()


def test_revoke_agent_token(client, admin_token, viewer_token):
    client.post(
        "/agents/heartbeat",
        headers={"X-MC-Token": "test-ingest", "X-MC-Enroll": "1"},
        json={"agent": "revoke-agent", "state": "idle"},
    )

    # Enrôlé : visible côté admin (rubrique Administration → identifiants agents).
    agents = client.get("/agents", headers=auth(admin_token)).json()
    enrolled = next(a for a in agents if a["agent"] == "revoke-agent")
    assert enrolled["token_issued_at"]

    forbidden = client.post("/agents/revoke-agent/revoke-token", headers=auth(viewer_token))
    assert forbidden.status_code == 403

    rv = client.post("/agents/revoke-agent/revoke-token", headers=auth(admin_token))
    assert rv.status_code == 204

    # Révoqué : ne réapparaît plus comme enrôlé tant qu'il ne s'est pas ré-enrôlé.
    agents = client.get("/agents", headers=auth(admin_token)).json()
    revoked = next(a for a in agents if a["agent"] == "revoke-agent")
    assert revoked["token_issued_at"] is None

    # Révoqué : doit se ré-enrôler avec le secret partagé + X-MC-Enroll.
    r2 = client.post(
        "/agents/heartbeat",
        headers={"X-MC-Token": "test-ingest", "X-MC-Enroll": "1"},
        json={"agent": "revoke-agent", "state": "working"},
    )
    assert r2.status_code == 202
    assert r2.json()["agent_token"]
