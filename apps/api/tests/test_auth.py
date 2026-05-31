"""Auth + RBAC."""
from apps.api.tests.conftest import auth


def test_login_ok(client):
    r = client.post("/auth/login", json={"email": "admin@mc.local", "password": "admin"})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_login_bad_password(client):
    r = client.post("/auth/login", json={"email": "admin@mc.local", "password": "WRONG"})
    assert r.status_code == 401


def test_me(client, admin_token):
    r = client.get("/auth/me", headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_protected_route_requires_token(client):
    assert client.get("/projects").status_code == 401


def test_admin_only_users_endpoint(client, admin_token, viewer_token):
    assert client.get("/auth/users", headers=auth(admin_token)).status_code == 200
    assert client.get("/auth/users", headers=auth(viewer_token)).status_code == 403


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"
