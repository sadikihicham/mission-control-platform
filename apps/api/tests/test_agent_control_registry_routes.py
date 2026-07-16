"""P7 — routes registre d'agents V1 + vue d'ensemble (dashboard/health).

Couvre : permissions (view vs manage_agents, fail-closed), dérivation serveur de
la clé d'agent (`<installation_key>:<local_key>`), credentials (secret affiché une
seule fois, jamais stocké en clair), cycle de vie registre (suspend/resume/archive),
agrégats dashboard réels et isolation cross-tenant (404, pas de fuite).
"""
import uuid

import pytest

from apps.api.core.security import hash_password, hash_reset_token
from apps.api.models import AgentCredential, MCInstallation, MCUserMapping, User


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _login(client, email, password) -> str:
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def tenant_b(client, db):
    inst = MCInstallation(
        external_tenant_id="reg-tenant-b",
        installation_key=f"regb-{uuid.uuid4().hex[:6]}",
        status="active",
    )
    db.add(inst)
    db.flush()
    email = f"regb-{uuid.uuid4().hex[:8]}@tenant-b.local"
    user = User(email=email, hashed_password=hash_password("passwordb"), role="admin")
    db.add(user)
    db.flush()
    db.add(
        MCUserMapping(
            installation_id=inst.id, external_user_id=str(user.id),
            local_user_id=user.id, email=user.email, role=user.role, status="active",
        )
    )
    db.commit()
    return {"email": email, "password": "passwordb", "installation_id": str(inst.id)}


def _register(client, token, local_key="worker-1", **extra):
    body = {"local_key": local_key, "display_name": "Worker 1", **extra}
    return client.post("/agent-control/v1/agents", json=body, headers=auth(token))


def test_register_requires_manage_agents(client, viewer_token):
    r = _register(client, viewer_token)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "permission_denied"


def test_register_derives_namespaced_key(client, admin_token):
    r = _register(client, admin_token, local_key="alpha")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["agent_key"] == "local:alpha"
    assert body["installation_id"]
    assert body["status"] == "active"
    assert body["state"] in {"idle", "working", "blocked", "stale", "done", "error"}


def test_register_rejects_duplicate_key(client, admin_token):
    assert _register(client, admin_token, local_key="dup").status_code == 201
    r = _register(client, admin_token, local_key="dup")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"


def test_register_rejects_colon_in_local_key(client, admin_token):
    r = _register(client, admin_token, local_key="bad:key")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_list_and_get_agent_view_capability(client, admin_token, viewer_token):
    rid = _register(client, admin_token, local_key="listed").json()["id"]
    lr = client.get("/agent-control/v1/agents", headers=auth(viewer_token))
    assert lr.status_code == 200
    assert any(a["id"] == rid for a in lr.json()["items"])
    gr = client.get(f"/agent-control/v1/agents/{rid}", headers=auth(viewer_token))
    assert gr.status_code == 200
    assert gr.json()["id"] == rid


def test_agent_health_is_server_derived(client, admin_token):
    rid = _register(client, admin_token, local_key="healthy").json()["id"]
    r = client.get(f"/agent-control/v1/agents/{rid}/health", headers=auth(admin_token))
    assert r.status_code == 200
    body = r.json()
    assert body["agent_key"] == "local:healthy"
    assert "healthy" in body and isinstance(body["healthy"], bool)


def test_credential_secret_shown_once_and_hashed(client, admin_token, db):
    rid = _register(client, admin_token, local_key="cred").json()["id"]
    r = client.post(
        f"/agent-control/v1/agents/{rid}/credentials",
        json={"scopes": ["ingest"]},
        headers=auth(admin_token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    secret = body["secret"]
    assert secret and secret.startswith(body["key_prefix"])
    # Le secret brut n'est jamais persisté : seule son empreinte l'est.
    cred = db.get(AgentCredential, uuid.UUID(body["id"]))
    assert cred.secret_hash == hash_reset_token(secret)
    assert secret not in (cred.secret_hash,)


def test_credential_refused_on_viewer(client, admin_token, viewer_token):
    rid = _register(client, admin_token, local_key="cred2").json()["id"]
    r = client.post(
        f"/agent-control/v1/agents/{rid}/credentials",
        json={"scopes": ["ingest"]},
        headers=auth(viewer_token),
    )
    assert r.status_code == 403


def test_lifecycle_suspend_resume_archive(client, admin_token):
    rid = _register(client, admin_token, local_key="life").json()["id"]
    s = client.post(f"/agent-control/v1/agents/{rid}/suspend", headers=auth(admin_token))
    assert s.status_code == 200 and s.json()["status"] == "suspended"
    r = client.post(f"/agent-control/v1/agents/{rid}/resume", headers=auth(admin_token))
    assert r.status_code == 200 and r.json()["status"] == "active"
    a = client.post(f"/agent-control/v1/agents/{rid}/archive", headers=auth(admin_token))
    assert a.status_code == 200 and a.json()["status"] == "archived"


def test_cross_tenant_agent_is_404(client, admin_token, tenant_b):
    rid = _register(client, admin_token, local_key="secret-a").json()["id"]
    token_b = _login(client, tenant_b["email"], tenant_b["password"])
    r = client.get(f"/agent-control/v1/agents/{rid}", headers=auth(token_b))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
    # La liste du tenant B ne contient jamais l'agent du tenant A.
    lb = client.get("/agent-control/v1/agents", headers=auth(token_b))
    assert all(a["id"] != rid for a in lb.json()["items"])


def test_dashboard_reflects_registered_agents(client, admin_token):
    before = client.get("/agent-control/v1/dashboard", headers=auth(admin_token)).json()
    _register(client, admin_token, local_key="dash-1")
    after = client.get("/agent-control/v1/dashboard", headers=auth(admin_token)).json()
    assert after["agents"]["total"] == before["agents"]["total"] + 1
    assert after["installation_id"]
    assert isinstance(after["cost"]["total_cost"], str)


def test_health_route_is_tenant_scoped(client, pm_token):
    r = client.get("/agent-control/v1/health", headers=auth(pm_token))
    assert r.status_code == 200
    assert r.json()["installation_status"] == "active"
    assert "view" in r.json()["capabilities"]


def test_dashboard_requires_auth(client):
    assert client.get("/agent-control/v1/dashboard").status_code == 401
