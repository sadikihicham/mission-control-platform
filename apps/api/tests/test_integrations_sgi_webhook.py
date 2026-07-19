"""Webhook entrant SGI → bascule mc_installations.status (ADR-0011)."""
import hashlib
import hmac
import json
import uuid

from apps.api.core.config import settings
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
