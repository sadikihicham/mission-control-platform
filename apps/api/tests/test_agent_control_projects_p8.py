"""P8 — routes projets & tâches V1 tenant-scoped.

Couvre : permissions (view vs manage_projects, fail-closed), bornage tenant
(cross-tenant = 404, jamais 403, jamais de fuite en liste), dérivation serveur du
tenant/slug, invariant projet vitrine en lecture seule, tâches (création,
hiérarchie un niveau, affectation d'agent du tenant), isolation cross-tenant des
tâches et de l'affectation d'agent.
"""
import uuid

import pytest

from apps.api.core.security import hash_password
from apps.api.models import MCInstallation, MCUserMapping, User


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _login(client, email, password) -> str:
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def tenant_b(client, db):
    inst = MCInstallation(
        external_tenant_id="proj-tenant-b",
        installation_key=f"projb-{uuid.uuid4().hex[:6]}",
        status="active",
    )
    db.add(inst)
    db.flush()
    email = f"projb-{uuid.uuid4().hex[:8]}@tenant-b.local"
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


def _create_project(client, token, name="Projet Alpha", **extra):
    return client.post(
        "/agent-control/v1/projects", json={"name": name, **extra}, headers=auth(token)
    )


# --- Permissions --------------------------------------------------------------


def test_create_requires_manage_projects(client, viewer_token):
    r = _create_project(client, viewer_token)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "permission_denied"


def test_list_and_get_view_capability(client, pm_token, viewer_token):
    pid = _create_project(client, pm_token, name="Visible").json()["id"]
    lr = client.get("/agent-control/v1/projects", headers=auth(viewer_token))
    assert lr.status_code == 200
    assert any(p["id"] == pid for p in lr.json()["items"])
    gr = client.get(f"/agent-control/v1/projects/{pid}", headers=auth(viewer_token))
    assert gr.status_code == 200
    assert gr.json()["id"] == pid


def test_create_derives_tenant_and_slug(client, pm_token):
    r = _create_project(client, pm_token, name="Mon Super Projet")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["installation_id"]
    assert body["slug"].startswith("mon-super-projet-")
    assert body["is_seed"] is False
    assert body["status"] == "in_dev"


def test_create_rejects_invalid_status(client, pm_token):
    r = _create_project(client, pm_token, name="X", status="nope")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_update_and_delete(client, pm_token):
    pid = _create_project(client, pm_token, name="Editable").json()["id"]
    u = client.patch(
        f"/agent-control/v1/projects/{pid}",
        json={"name": "Renommé", "progress": 60},
        headers=auth(pm_token),
    )
    assert u.status_code == 200 and u.json()["name"] == "Renommé"
    assert u.json()["progress"] == 60
    d = client.delete(f"/agent-control/v1/projects/{pid}", headers=auth(pm_token))
    assert d.status_code == 204
    assert client.get(f"/agent-control/v1/projects/{pid}", headers=auth(pm_token)).status_code == 404


# --- Projet vitrine (is_seed) en lecture seule --------------------------------


def _find_seed_project(client, token) -> dict | None:
    r = client.get("/agent-control/v1/projects?limit=200", headers=auth(token))
    for p in r.json()["items"]:
        if p["is_seed"]:
            return p
    return None


def test_seed_project_is_read_only(client, pm_token, admin_token):
    seed = _find_seed_project(client, admin_token)
    assert seed is not None, "le seed doit exposer au moins un projet vitrine dans le tenant local"
    # Visible en lecture, mais toute mutation est refusée (invariant V0 préservé).
    u = client.patch(
        f"/agent-control/v1/projects/{seed['id']}",
        json={"name": "hack"},
        headers=auth(pm_token),
    )
    assert u.status_code == 409
    assert u.json()["error"]["code"] == "state_conflict"
    d = client.delete(f"/agent-control/v1/projects/{seed['id']}", headers=auth(pm_token))
    assert d.status_code == 409


# --- Isolation cross-tenant ---------------------------------------------------


def test_cross_tenant_project_is_404(client, pm_token, tenant_b):
    pid = _create_project(client, pm_token, name="Secret A").json()["id"]
    token_b = _login(client, tenant_b["email"], tenant_b["password"])
    r = client.get(f"/agent-control/v1/projects/{pid}", headers=auth(token_b))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
    lb = client.get("/agent-control/v1/projects?limit=200", headers=auth(token_b))
    assert all(p["id"] != pid for p in lb.json()["items"])


def test_cross_tenant_project_mutation_is_404(client, pm_token, tenant_b):
    pid = _create_project(client, pm_token, name="Secret A2").json()["id"]
    token_b = _login(client, tenant_b["email"], tenant_b["password"])
    u = client.patch(
        f"/agent-control/v1/projects/{pid}", json={"name": "x"}, headers=auth(token_b)
    )
    assert u.status_code == 404
    d = client.delete(f"/agent-control/v1/projects/{pid}", headers=auth(token_b))
    assert d.status_code == 404


# --- Tâches -------------------------------------------------------------------


def test_task_crud_and_hierarchy(client, pm_token):
    pid = _create_project(client, pm_token, name="Avec tâches").json()["id"]
    tr = client.post(
        f"/agent-control/v1/projects/{pid}/tasks",
        json={"title": "Tâche racine", "code": "M0"},
        headers=auth(pm_token),
    )
    assert tr.status_code == 201, tr.text
    tid = tr.json()["id"]
    assert tr.json()["installation_id"]
    assert tr.json()["project_id"] == pid
    # Sous-tâche (un niveau)
    sr = client.post(
        f"/agent-control/v1/projects/{pid}/tasks",
        json={"title": "Sous-tâche", "parent_id": tid},
        headers=auth(pm_token),
    )
    assert sr.status_code == 201
    assert sr.json()["parent_id"] == tid
    # Pas de sous-sous-tâche (hiérarchie limitée à un niveau)
    ssr = client.post(
        f"/agent-control/v1/projects/{pid}/tasks",
        json={"title": "trop profond", "parent_id": sr.json()["id"]},
        headers=auth(pm_token),
    )
    assert ssr.status_code == 422
    # Liste
    lr = client.get(f"/agent-control/v1/projects/{pid}/tasks", headers=auth(pm_token))
    assert lr.status_code == 200 and len(lr.json()["items"]) == 2
    # Détail + update
    g = client.get(f"/agent-control/v1/tasks/{tid}", headers=auth(pm_token))
    assert g.status_code == 200
    up = client.patch(
        f"/agent-control/v1/tasks/{tid}",
        json={"status": "in_progress", "progress": 30},
        headers=auth(pm_token),
    )
    assert up.status_code == 200 and up.json()["status"] == "in_progress"


def test_task_code_duplicate_conflict(client, pm_token):
    pid = _create_project(client, pm_token, name="Codes").json()["id"]
    assert client.post(
        f"/agent-control/v1/projects/{pid}/tasks",
        json={"title": "A", "code": "DUP"}, headers=auth(pm_token),
    ).status_code == 201
    r = client.post(
        f"/agent-control/v1/projects/{pid}/tasks",
        json={"title": "B", "code": "DUP"}, headers=auth(pm_token),
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"


def test_task_list_requires_view(client, pm_token, viewer_token):
    pid = _create_project(client, pm_token, name="ViewTasks").json()["id"]
    r = client.get(f"/agent-control/v1/projects/{pid}/tasks", headers=auth(viewer_token))
    assert r.status_code == 200


def test_cross_tenant_task_is_404(client, pm_token, tenant_b):
    pid = _create_project(client, pm_token, name="TenantA tasks").json()["id"]
    tid = client.post(
        f"/agent-control/v1/projects/{pid}/tasks",
        json={"title": "secret"}, headers=auth(pm_token),
    ).json()["id"]
    token_b = _login(client, tenant_b["email"], tenant_b["password"])
    # Tâche par id : 404 hors tenant
    assert client.get(f"/agent-control/v1/tasks/{tid}", headers=auth(token_b)).status_code == 404
    # Liste des tâches d'un projet hors tenant : 404 (projet invisible)
    assert client.get(
        f"/agent-control/v1/projects/{pid}/tasks", headers=auth(token_b)
    ).status_code == 404


def test_assign_agent_of_tenant(client, admin_token, pm_token):
    # Agent enregistré dans le tenant local (manage_agents = admin).
    aid = client.post(
        "/agent-control/v1/agents",
        json={"local_key": f"assignee-{uuid.uuid4().hex[:6]}"},
        headers=auth(admin_token),
    ).json()["id"]
    agent_key = client.get(
        f"/agent-control/v1/agents/{aid}", headers=auth(admin_token)
    ).json()["agent_key"]
    pid = _create_project(client, pm_token, name="Assign").json()["id"]
    tid = client.post(
        f"/agent-control/v1/projects/{pid}/tasks",
        json={"title": "à affecter"}, headers=auth(pm_token),
    ).json()["id"]
    r = client.post(
        f"/agent-control/v1/tasks/{tid}/assign",
        json={"agent_id": aid}, headers=auth(pm_token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["agent_id"] == aid
    assert r.json()["agent_key"] == agent_key


def test_assign_cross_tenant_agent_is_404(client, admin_token, pm_token, tenant_b):
    token_b = _login(client, tenant_b["email"], tenant_b["password"])
    # Agent du tenant B
    aid_b = client.post(
        "/agent-control/v1/agents",
        json={"local_key": f"bagent-{uuid.uuid4().hex[:6]}"},
        headers=auth(token_b),
    ).json()["id"]
    # Tâche du tenant local
    pid = _create_project(client, pm_token, name="AssignX").json()["id"]
    tid = client.post(
        f"/agent-control/v1/projects/{pid}/tasks",
        json={"title": "t"}, headers=auth(pm_token),
    ).json()["id"]
    r = client.post(
        f"/agent-control/v1/tasks/{tid}/assign",
        json={"agent_id": aid_b}, headers=auth(pm_token),
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
