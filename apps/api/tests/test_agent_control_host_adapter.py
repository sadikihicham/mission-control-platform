"""Adaptateur hôte local (`LocalHostAdapter`) — Gate P0, fail-closed.

Couvre les quatre cas exigés : token/identité valide, utilisateur absent,
tenant absent, rôle insuffisant. Aucune identité ni permission ne provient d'un
body : tout est dérivé de l'`User` local et du RBAC hôte.
"""
from dataclasses import dataclass

import pytest

from apps.api.integrations.capabilities import Capability
from apps.api.integrations.errors import IdentityUnresolved, TenantUnresolved
from apps.api.integrations.local_adapter import (
    LOCAL_INSTALLATION_KEY,
    LocalHostAdapter,
)


@dataclass
class _FakeUser:
    id: str
    email: str
    role: str
    is_active: bool = True
    full_name: str | None = None


def test_valid_identity_builds_full_context():
    adapter = LocalHostAdapter()
    user = _FakeUser(id="u-1", email="pm@mc.local", role="pm", full_name="Alice")
    ctx = adapter.build_context(user, request_id="req-1", locale="ar", timezone="Asia/Dubai")

    assert ctx.request_id == "req-1"
    assert ctx.user.external_user_id == "u-1"
    assert ctx.user.local_user_id == "u-1"
    assert ctx.user.display_name == "Alice"
    assert ctx.installation.installation_key == LOCAL_INSTALLATION_KEY
    assert ctx.tenant.external_tenant_id == LOCAL_INSTALLATION_KEY
    assert ctx.locale == "ar"
    assert ctx.timezone == "Asia/Dubai"
    # pm → capacités attendues
    assert Capability.manage_projects in ctx.capabilities
    assert Capability.manage_agents not in ctx.capabilities


def test_missing_user_is_rejected():
    adapter = LocalHostAdapter()
    with pytest.raises(IdentityUnresolved):
        adapter.build_context(None, request_id="req-2")


def test_inactive_user_is_rejected():
    adapter = LocalHostAdapter()
    user = _FakeUser(id="u-2", email="x@mc.local", role="admin", is_active=False)
    with pytest.raises(IdentityUnresolved):
        adapter.build_context(user, request_id="req-3")


def test_missing_tenant_is_rejected():
    # Installation désactivée → aucun tenant résolu (fail-closed).
    adapter = LocalHostAdapter(installation_active=False)
    user = _FakeUser(id="u-3", email="a@mc.local", role="admin")
    with pytest.raises(TenantUnresolved):
        adapter.build_context(user, request_id="req-4")


def test_unknown_installation_key_is_rejected():
    adapter = LocalHostAdapter()
    user = _FakeUser(id="u-4", email="a@mc.local", role="admin")
    with pytest.raises(TenantUnresolved):
        adapter.build_context(user, request_id="req-5", installation_key="other-tenant")


def test_insufficient_role_yields_no_write_capability():
    adapter = LocalHostAdapter()
    user = _FakeUser(id="u-5", email="v@mc.local", role="viewer")
    ctx = adapter.build_context(user, request_id="req-6")
    assert ctx.capabilities == frozenset({Capability.view})
    assert not ctx.has(Capability.operate)
    assert not ctx.has(Capability.manage_projects)


def test_unknown_role_is_fail_closed():
    adapter = LocalHostAdapter()
    user = _FakeUser(id="u-6", email="r@mc.local", role="superuser")
    ctx = adapter.build_context(user, request_id="req-7")
    assert ctx.capabilities == frozenset()


def test_context_is_immutable():
    adapter = LocalHostAdapter()
    user = _FakeUser(id="u-7", email="a@mc.local", role="admin")
    ctx = adapter.build_context(user, request_id="req-8")
    with pytest.raises(Exception):  # noqa: B017,PT011 — pydantic frozen -> ValidationError
        ctx.locale = "en"
