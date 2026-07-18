"""Adaptateur hôte `jwt` (`JwtHostAdapter`, ADR-0010) — Gate P1 bis.

Miroir de `test_agent_control_host_adapter.py` (adaptateur `local`), pour le
second adaptateur concret : identité/tenant/capacités résolus depuis un JWT
hôte (ex. SGI), pas depuis un `User`/JWT V0 de ce service.
"""
import time
import uuid

import pytest
from jose import jwt as jose_jwt

from apps.api.core.config import settings
from apps.api.integrations.capabilities import Capability
from apps.api.integrations.errors import IdentityUnresolved, TenantUnresolved
from apps.api.integrations.jwt_adapter import JwtHostAdapter
from apps.api.models import MCInstallation


def _host_token(*, sub="host-user-1", company_id="company-1", role="admin", **extra) -> str:
    payload = {"sub": sub, "company_id": company_id, "role": role, "exp": time.time() + 900, **extra}
    return jose_jwt.encode(payload, settings.sgi_jwt_secret, algorithm=settings.sgi_jwt_algorithm)


def _active_installation(db, *, company_id: str) -> MCInstallation:
    inst = MCInstallation(
        external_tenant_id=company_id,
        installation_key=f"jwt-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db.add(inst)
    db.commit()
    return inst


def test_valid_host_token_builds_full_context(db):
    inst = _active_installation(db, company_id="company-valid")
    token = _host_token(company_id="company-valid", role="admin")
    adapter = JwtHostAdapter(db)

    ctx = adapter.build_context(token, request_id="req-1", locale="ar", timezone="Asia/Dubai")

    assert ctx.request_id == "req-1"
    assert ctx.user.external_user_id == "host-user-1"
    assert ctx.user.email is None  # SGI ne porte pas encore d'email dans son JWT
    assert ctx.installation.id == str(inst.id)
    assert ctx.tenant.external_tenant_id == "company-valid"
    assert ctx.locale == "ar" and ctx.timezone == "Asia/Dubai"
    assert Capability.admin in ctx.capabilities


def test_missing_token_is_rejected(db):
    adapter = JwtHostAdapter(db)
    with pytest.raises(IdentityUnresolved):
        adapter.build_context(None, request_id="req-2")


def test_garbage_token_is_rejected(db):
    adapter = JwtHostAdapter(db)
    with pytest.raises(IdentityUnresolved):
        adapter.build_context("not-a-jwt", request_id="req-3")


def test_token_signed_with_wrong_secret_is_rejected(db):
    bad_token = jose_jwt.encode(
        {"sub": "u", "company_id": "company-valid", "role": "admin", "exp": time.time() + 900},
        "wrong-secret",
        algorithm=settings.sgi_jwt_algorithm,
    )
    adapter = JwtHostAdapter(db)
    with pytest.raises(IdentityUnresolved):
        adapter.build_context(bad_token, request_id="req-4")


def test_missing_company_id_claim_is_rejected(db):
    token = jose_jwt.encode(
        {"sub": "host-user-2", "role": "admin", "exp": time.time() + 900},  # pas de company_id
        settings.sgi_jwt_secret,
        algorithm=settings.sgi_jwt_algorithm,
    )
    adapter = JwtHostAdapter(db)
    with pytest.raises(TenantUnresolved):
        adapter.build_context(token, request_id="req-5")


def test_token_without_exp_is_rejected(db):
    """Un jeton sans expiration ne doit jamais être accepté (ADR-0010 : TTL 15 min)."""
    token = jose_jwt.encode(
        {"sub": "host-user-3", "company_id": "company-valid", "role": "admin"},
        settings.sgi_jwt_secret,
        algorithm=settings.sgi_jwt_algorithm,
    )
    adapter = JwtHostAdapter(db)
    with pytest.raises(IdentityUnresolved):
        adapter.build_context(token, request_id="req-5b")


def test_expired_token_is_rejected(db):
    token = jose_jwt.encode(
        {
            "sub": "host-user-4",
            "company_id": "company-valid",
            "role": "admin",
            "exp": time.time() - 60,
        },
        settings.sgi_jwt_secret,
        algorithm=settings.sgi_jwt_algorithm,
    )
    adapter = JwtHostAdapter(db)
    with pytest.raises(IdentityUnresolved):
        adapter.build_context(token, request_id="req-5c")


def test_unknown_tenant_is_rejected(db):
    token = _host_token(company_id="company-never-onboarded")
    adapter = JwtHostAdapter(db)
    with pytest.raises(TenantUnresolved):
        adapter.build_context(token, request_id="req-6")


def test_suspended_installation_is_rejected(db):
    inst = MCInstallation(
        external_tenant_id="company-suspended",
        installation_key=f"jwt-{uuid.uuid4().hex[:8]}",
        status="suspended",
    )
    db.add(inst)
    db.commit()
    token = _host_token(company_id="company-suspended")
    adapter = JwtHostAdapter(db)
    with pytest.raises(TenantUnresolved):
        adapter.build_context(token, request_id="req-7")


def test_portal_persona_role_yields_no_capability(db):
    """Les personas portail SGI (owner/tenant/client/technician) ne sont pas
    mappées : fail-closed, aucune capacité — Agent Control est un outil staff."""
    _active_installation(db, company_id="company-persona")
    token = _host_token(company_id="company-persona", role="owner")
    adapter = JwtHostAdapter(db)

    ctx = adapter.build_context(token, request_id="req-8")

    assert ctx.capabilities == frozenset()


def test_sgi_agent_role_maps_to_operate_not_manage(db):
    _active_installation(db, company_id="company-agent-role")
    token = _host_token(company_id="company-agent-role", role="agent")
    adapter = JwtHostAdapter(db)

    ctx = adapter.build_context(token, request_id="req-9")

    assert Capability.operate in ctx.capabilities
    assert Capability.manage_agents not in ctx.capabilities
