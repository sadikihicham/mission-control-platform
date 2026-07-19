"""Webhook entrant SGI → bascule mc_installations.status (ADR-0011)."""
import hashlib
import hmac
import json
import uuid

from apps.api.core.config import SECRET_DEV_DEFAUT, settings
from apps.api.models import MCInstallation

URL = "/integrations/sgi/subscription-events"


def _signed(body: dict) -> tuple[bytes, str]:
    raw = json.dumps(body).encode()
    sig = hmac.new(settings.sgi_webhook_secret.encode(), raw, hashlib.sha256).hexdigest()
    return raw, f"sha256={sig}"


def _installation(db, *, company_id: str, status: str = "suspended") -> MCInstallation:
    inst = MCInstallation(
        external_tenant_id=company_id,
        installation_key=f"sgi-{uuid.uuid4().hex[:8]}",
        status=status,
    )
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return inst


def test_enabled_true_flips_to_active(client, db):
    inst = _installation(db, company_id="company-flip-1", status="suspended")
    raw, sig = _signed({"company_id": "company-flip-1", "activity_key": "agent_control", "enabled": True})

    r = client.post(URL, content=raw, headers={"X-SGI-Signature": sig, "Content-Type": "application/json"})

    assert r.status_code == 200
    db.refresh(inst)
    assert inst.status == "active"


def test_enabled_false_flips_to_suspended(client, db):
    inst = _installation(db, company_id="company-flip-2", status="active")
    raw, sig = _signed({"company_id": "company-flip-2", "activity_key": "agent_control", "enabled": False})

    r = client.post(URL, content=raw, headers={"X-SGI-Signature": sig, "Content-Type": "application/json"})

    assert r.status_code == 200
    db.refresh(inst)
    assert inst.status == "suspended"


def test_missing_signature_is_rejected(client, db):
    _installation(db, company_id="company-flip-3", status="suspended")
    raw = json.dumps({"company_id": "company-flip-3", "activity_key": "agent_control", "enabled": True}).encode()

    r = client.post(URL, content=raw, headers={"Content-Type": "application/json"})

    assert r.status_code == 401


def test_wrong_secret_signature_is_rejected(client, db):
    inst = _installation(db, company_id="company-flip-4", status="suspended")
    raw = json.dumps({"company_id": "company-flip-4", "activity_key": "agent_control", "enabled": True}).encode()
    bad_sig = "sha256=" + hmac.new(b"wrong-secret", raw, hashlib.sha256).hexdigest()

    r = client.post(URL, content=raw, headers={"X-SGI-Signature": bad_sig, "Content-Type": "application/json"})

    assert r.status_code == 401
    db.refresh(inst)
    assert inst.status == "suspended"  # inchangé


def test_unknown_company_id_is_not_provisioned(client, db):
    raw, sig = _signed({"company_id": "company-never-onboarded-2", "activity_key": "agent_control", "enabled": True})

    r = client.post(URL, content=raw, headers={"X-SGI-Signature": sig, "Content-Type": "application/json"})

    assert r.status_code == 404
    assert db.query(MCInstallation).filter_by(external_tenant_id="company-never-onboarded-2").first() is None


def test_unrelated_activity_key_is_ignored(client, db):
    inst = _installation(db, company_id="company-flip-5", status="suspended")
    raw, sig = _signed({"company_id": "company-flip-5", "activity_key": "some_other_activity", "enabled": True})

    r = client.post(URL, content=raw, headers={"X-SGI-Signature": sig, "Content-Type": "application/json"})

    assert r.status_code == 200
    assert r.json()["status"] == "ignored"
    db.refresh(inst)
    assert inst.status == "suspended"  # inchangé


# --- Garde fail-closed : secret partagé resté au défaut du dépôt (audit 2026-07-19) -------------
# La route est montée SANS CONDITION (main.py) et n'est authentifiée que par ce secret. Laissé à sa
# valeur par défaut — publiquement lisible ici — n'importe qui peut forger une signature valide et
# suspendre un tenant. Hors dev, la route se DÉSACTIVE donc au lieu d'accepter le payload.


def test_secret_au_defaut_desactive_la_route_hors_dev(client, db, monkeypatch):
    """Secret non posé + environnement non-dev ⇒ 503, AVANT toute vérification de signature."""
    inst = _installation(db, company_id="company-garde-1", status="active")
    monkeypatch.setattr(settings, "environment", "prod")
    monkeypatch.setattr(settings, "sgi_webhook_secret", SECRET_DEV_DEFAUT)
    raw, sig = _signed({"company_id": "company-garde-1", "activity_key": "agent_control", "enabled": False})

    r = client.post(URL, content=raw, headers={"X-SGI-Signature": sig, "Content-Type": "application/json"})

    assert r.status_code == 503
    db.refresh(inst)
    assert inst.status == "active"  # aucune bascule : le tenant n'a PAS été suspendu


def test_secret_pose_reactive_la_route_hors_dev(client, db, monkeypatch):
    """Même environnement prod, mais secret réellement posé ⇒ la route fonctionne normalement."""
    inst = _installation(db, company_id="company-garde-2", status="suspended")
    monkeypatch.setattr(settings, "environment", "prod")
    monkeypatch.setattr(settings, "sgi_webhook_secret", "un-vrai-secret-partage-suffisamment-long")
    raw, sig = _signed({"company_id": "company-garde-2", "activity_key": "agent_control", "enabled": True})

    r = client.post(URL, content=raw, headers={"X-SGI-Signature": sig, "Content-Type": "application/json"})

    assert r.status_code == 200
    db.refresh(inst)
    assert inst.status == "active"


def test_environnement_inconnu_est_traite_comme_non_dev(client, db, monkeypatch):
    """Fail-closed sur l'inconnu : une faute de frappe dans ENVIRONMENT ne doit pas relâcher la
    garde (c'est le sens du test — `staging`, `preprod` ou `prd` valent prod, pas dev)."""
    _installation(db, company_id="company-garde-3", status="active")
    monkeypatch.setattr(settings, "environment", "staging")
    monkeypatch.setattr(settings, "sgi_webhook_secret", SECRET_DEV_DEFAUT)
    raw, sig = _signed({"company_id": "company-garde-3", "activity_key": "agent_control", "enabled": False})

    r = client.post(URL, content=raw, headers={"X-SGI-Signature": sig, "Content-Type": "application/json"})

    assert r.status_code == 503


def test_dev_continue_de_fonctionner_avec_le_defaut(client, db, monkeypatch):
    """Non-régression : en dev, le défaut reste utilisable (sinon toute la suite existante casse)."""
    inst = _installation(db, company_id="company-garde-4", status="suspended")
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "sgi_webhook_secret", SECRET_DEV_DEFAUT)
    raw, sig = _signed({"company_id": "company-garde-4", "activity_key": "agent_control", "enabled": True})

    r = client.post(URL, content=raw, headers={"X-SGI-Signature": sig, "Content-Type": "application/json"})

    assert r.status_code == 200
    db.refresh(inst)
    assert inst.status == "active"
