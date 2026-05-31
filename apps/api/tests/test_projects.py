"""CRUD projets + RBAC write (pm minimum)."""
from apps.api.tests.conftest import auth


def test_viewer_cannot_create(client, viewer_token):
    r = client.post("/projects", headers=auth(viewer_token), json={"name": "Nope"})
    assert r.status_code == 403


def test_pm_crud_cycle(client, pm_token):
    # create
    r = client.post("/projects", headers=auth(pm_token), json={"name": "Test CRM", "status": "proposed"})
    assert r.status_code == 201
    pid = r.json()["id"]
    assert r.json()["editable"] is True

    # listé (+ projet vitrine seed)
    names = [p["name"] for p in client.get("/projects", headers=auth(pm_token)).json()]
    assert "Test CRM" in names

    # update status
    r = client.patch(f"/projects/{pid}", headers=auth(pm_token), json={"status": "in_dev", "progress": 20})
    assert r.status_code == 200 and r.json()["status"] == "in_dev"

    # delete → 204, puis 404
    assert client.delete(f"/projects/{pid}", headers=auth(pm_token)).status_code == 204
    assert client.get(f"/projects/{pid}", headers=auth(pm_token)).status_code == 404


def test_stats_shape(client, admin_token):
    s = client.get("/stats/dashboard", headers=auth(admin_token)).json()
    for k in ("agents_total", "agents_active", "agents_blocked", "overall_progress"):
        assert k in s
