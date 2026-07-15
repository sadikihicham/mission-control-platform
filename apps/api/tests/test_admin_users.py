"""Gestion utilisateurs (rubrique Administration) — CRUD réservé au rôle admin."""
import uuid

from apps.api.tests.conftest import auth


def _id_of(client, admin_token, email):
    users = client.get("/auth/users", headers=auth(admin_token)).json()
    return next(u["id"] for u in users if u["email"] == email)


def test_create_user_requires_admin(client, viewer_token):
    r = client.post(
        "/auth/users",
        json={"email": "x@mc.local", "password": "secret1"},
        headers=auth(viewer_token),
    )
    assert r.status_code == 403


def test_create_user_ok(client, admin_token):
    r = client.post(
        "/auth/users",
        json={"email": "nouveau@mc.local", "password": "secret12", "role": "pm"},
        headers=auth(admin_token),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "nouveau@mc.local"
    assert body["role"] == "pm"
    assert body["is_active"] is True
    login = client.post("/auth/login", json={"email": "nouveau@mc.local", "password": "secret12"})
    assert login.status_code == 200


def test_create_user_defaults_to_viewer_role(client, admin_token):
    r = client.post(
        "/auth/users",
        json={"email": "role-defaut@mc.local", "password": "secret12"},
        headers=auth(admin_token),
    )
    assert r.json()["role"] == "viewer"


def test_create_user_duplicate_email_rejected(client, admin_token, make_user):
    email = make_user()
    r = client.post(
        "/auth/users", json={"email": email, "password": "secret12"}, headers=auth(admin_token)
    )
    assert r.status_code == 409


def test_update_user_role(client, admin_token, make_user):
    email = make_user(role="viewer")
    user_id = _id_of(client, admin_token, email)
    r = client.patch(f"/auth/users/{user_id}", json={"role": "pm"}, headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["role"] == "pm"


def test_deactivate_user_blocks_login(client, admin_token, make_user):
    email = make_user(password="willbeoff1")
    user_id = _id_of(client, admin_token, email)
    r = client.patch(f"/auth/users/{user_id}", json={"is_active": False}, headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["is_active"] is False
    r2 = client.post("/auth/login", json={"email": email, "password": "willbeoff1"})
    assert r2.status_code == 401


def test_reactivate_user_restores_login(client, admin_token, make_user):
    email = make_user(password="backagain1")
    user_id = _id_of(client, admin_token, email)
    client.patch(f"/auth/users/{user_id}", json={"is_active": False}, headers=auth(admin_token))
    r = client.patch(f"/auth/users/{user_id}", json={"is_active": True}, headers=auth(admin_token))
    assert r.status_code == 200
    r2 = client.post("/auth/login", json={"email": email, "password": "backagain1"})
    assert r2.status_code == 200


def test_admin_cannot_deactivate_self(client, admin_token):
    me = client.get("/auth/me", headers=auth(admin_token)).json()
    r = client.patch(f"/auth/users/{me['id']}", json={"is_active": False}, headers=auth(admin_token))
    assert r.status_code == 400


def test_admin_cannot_demote_self(client, admin_token):
    me = client.get("/auth/me", headers=auth(admin_token)).json()
    r = client.patch(f"/auth/users/{me['id']}", json={"role": "viewer"}, headers=auth(admin_token))
    assert r.status_code == 400


def test_update_user_requires_admin(client, viewer_token, admin_token):
    me = client.get("/auth/me", headers=auth(admin_token)).json()
    r = client.patch(f"/auth/users/{me['id']}", json={"full_name": "x"}, headers=auth(viewer_token))
    assert r.status_code == 403


def test_update_unknown_user_404(client, admin_token):
    r = client.patch(
        f"/auth/users/{uuid.uuid4()}", json={"full_name": "x"}, headers=auth(admin_token)
    )
    assert r.status_code == 404
