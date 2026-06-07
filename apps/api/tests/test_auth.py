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


# ---- Mot de passe oublié / réinitialisation ----
# NB : ces tests utilisent des comptes jetables (make_user) car le harness ne
# rollback pas entre tests — muter l'admin seedé casserait les tests suivants.

def test_forgot_password_returns_dev_token(client, make_user):
    email = make_user()
    r = client.post("/auth/forgot-password", json={"email": email})
    assert r.status_code == 200
    # En test (environment=development), le jeton brut est renvoyé faute de SMTP.
    assert r.json()["dev_token"]


def test_forgot_password_unknown_email_is_generic(client):
    r = client.post("/auth/forgot-password", json={"email": "ghost@nowhere.io"})
    assert r.status_code == 200
    # Anti-énumération : aucune fuite sur l'existence du compte.
    assert r.json()["dev_token"] is None


def test_reset_password_full_cycle(client, make_user):
    email = make_user(password="initial1")
    token = client.post("/auth/forgot-password", json={"email": email}).json()["dev_token"]
    r = client.post("/auth/reset-password", json={"token": token, "new_password": "brandnew1"})
    assert r.status_code == 200
    # Le nouveau mot de passe fonctionne, l'ancien non.
    assert client.post("/auth/login", json={"email": email, "password": "brandnew1"}).status_code == 200
    assert client.post("/auth/login", json={"email": email, "password": "initial1"}).status_code == 401


def test_reset_token_is_single_use(client, make_user):
    email = make_user()
    token = client.post("/auth/forgot-password", json={"email": email}).json()["dev_token"]
    assert client.post("/auth/reset-password", json={"token": token, "new_password": "firstpass1"}).status_code == 200
    # Réutilisation refusée.
    assert client.post("/auth/reset-password", json={"token": token, "new_password": "secondpass1"}).status_code == 400


def test_reset_password_invalid_token(client):
    r = client.post("/auth/reset-password", json={"token": "not-a-real-token", "new_password": "whatever1"})
    assert r.status_code == 400


def test_reset_password_too_short_rejected(client, make_user):
    email = make_user()
    token = client.post("/auth/forgot-password", json={"email": email}).json()["dev_token"]
    assert client.post("/auth/reset-password", json={"token": token, "new_password": "abc"}).status_code == 422


def test_new_forgot_invalidates_previous_token(client, make_user):
    email = make_user()
    first = client.post("/auth/forgot-password", json={"email": email}).json()["dev_token"]
    second = client.post("/auth/forgot-password", json={"email": email}).json()["dev_token"]
    # Émettre un nouveau jeton invalide le précédent.
    assert client.post("/auth/reset-password", json={"token": first, "new_password": "shouldfail1"}).status_code == 400
    assert client.post("/auth/reset-password", json={"token": second, "new_password": "shouldwork1"}).status_code == 200
