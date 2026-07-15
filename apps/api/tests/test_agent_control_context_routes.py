"""SP1 (P1) — routes /agent-control/v1/context et /capabilities, isolation tenant.

Vérifie la résolution serveur du HostContext, le fail-closed (pas de JWT, pas de
mapping tenant), et l'absence de fuite cross-tenant : deux installations, deux
utilisateurs mappés, chacun ne voit QUE la sienne.
"""
import uuid

import pytest

from apps.api.core.security import hash_password
from apps.api.models import (
    LOCAL_INSTALLATION_ID,
    MCInstallation,
    MCUserMapping,
    User,
)


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _login(client, email: str, password: str) -> str:
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def tenant_b(db):
    """Crée une 2e installation + un utilisateur mappé UNIQUEMENT à elle.

    Le seed ayant déjà mappé tous les users seedés à l'installation `local`, ce
    nouvel utilisateur (créé après le seed) n'est rattaché qu'au tenant B.
    """
    inst = MCInstallation(
        external_tenant_id="tenant-b-ext",
        installation_key=f"tenant-b-{uuid.uuid4().hex[:6]}",
        status="active",
    )
    db.add(inst)
    db.flush()
    email = f"userb-{uuid.uuid4().hex[:8]}@tenant-b.local"
    user = User(email=email, hashed_password=hash_password("passwordb"), role="cto")
    db.add(user)
    db.flush()
    db.add(
        MCUserMapping(
            installation_id=inst.id,
            external_user_id=str(user.id),
            local_user_id=user.id,
            email=user.email,
            role=user.role,
            status="active",
        )
    )
    db.commit()
    return {"installation_id": str(inst.id), "installation_key": inst.installation_key,
            "email": email, "password": "passwordb"}


def test_context_requires_jwt(client):
    r = client.get("/agent-control/v1/context")
    assert r.status_code == 401


def test_context_returns_local_installation_for_seeded_user(client, pm_token):
    r = client.get("/agent-control/v1/context", headers=auth(pm_token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["installation"]["installation_key"] == "local"
    assert body["installation"]["id"] == str(LOCAL_INSTALLATION_ID)
    assert body["tenant"]["external_tenant_id"] == "local"
    assert "view" in body["capabilities"]
    assert body["user"]["email"] == "pm@mc.local"


def test_capabilities_route_reflects_role(client, pm_token):
    r = client.get("/agent-control/v1/capabilities", headers=auth(pm_token))
    assert r.status_code == 200, r.text
    caps = r.json()["capabilities"]
    assert "manage_projects" in caps  # pm
    assert "manage_agents" not in caps  # réservé cto+
    assert "admin" not in caps


def test_unmapped_user_is_tenant_required(client, db):
    # Utilisateur créé APRÈS le seed → aucun mapping tenant → fail-closed 403.
    email = f"orphan-{uuid.uuid4().hex[:8]}@mc.local"
    db.add(User(email=email, hashed_password=hash_password("orphan1"), role="admin"))
    db.commit()
    token = _login(client, email, "orphan1")
    r = client.get("/agent-control/v1/context", headers=auth(token))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "tenant_required"


def test_cross_tenant_no_leak(client, pm_token, tenant_b):
    # Utilisateur A (seedé) → installation locale.
    ra = client.get("/agent-control/v1/context", headers=auth(pm_token))
    assert ra.status_code == 200
    a = ra.json()

    # Utilisateur B → tenant B uniquement.
    token_b = _login(client, tenant_b["email"], tenant_b["password"])
    rb = client.get("/agent-control/v1/context", headers=auth(token_b))
    assert rb.status_code == 200
    b = rb.json()

    # Chacun ne voit QUE son installation, jamais celle de l'autre.
    assert a["installation"]["installation_key"] == "local"
    assert b["installation"]["installation_key"] == tenant_b["installation_key"]
    assert a["installation"]["id"] != b["installation"]["id"]
    assert b["installation"]["id"] == tenant_b["installation_id"]
    assert a["tenant"]["external_tenant_id"] != b["tenant"]["external_tenant_id"]


def test_suspended_installation_is_fail_closed(client, db):
    # Une installation suspendue ne résout aucun contexte (fail-closed).
    inst = MCInstallation(
        external_tenant_id="suspended-ext",
        installation_key=f"suspended-{uuid.uuid4().hex[:6]}",
        status="suspended",
    )
    db.add(inst)
    db.flush()
    email = f"susp-{uuid.uuid4().hex[:8]}@mc.local"
    user = User(email=email, hashed_password=hash_password("susp1234"), role="admin")
    db.add(user)
    db.flush()
    db.add(
        MCUserMapping(
            installation_id=inst.id, external_user_id=str(user.id),
            local_user_id=user.id, status="active",
        )
    )
    db.commit()
    token = _login(client, email, "susp1234")
    r = client.get("/agent-control/v1/context", headers=auth(token))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "tenant_required"
