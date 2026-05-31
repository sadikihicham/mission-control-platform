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
