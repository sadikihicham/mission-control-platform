"""Adaptateur hôte `jwt` (`JwtHostAdapter`, ADR-0010) — Gate P1 bis.

Miroir de `test_agent_control_host_adapter.py` (adaptateur `local`), pour le
second adaptateur concret : identité/tenant/capacités résolus depuis un JWT
hôte (ex. SGI), pas depuis un `User`/JWT V0 de ce service.
"""
import time
import uuid

import pytest
from jose import jwt as jose_jwt
from pydantic import ValidationError

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


# --- Garde fail-closed au démarrage (audit 2026-07-19) -----------------------------------------
# `MC_HOST_ADAPTER=jwt` hors dev sans `SGI_JWT_SECRET` posé signifierait accepter des JWT signés
# avec un secret publiquement lisible dans ce dépôt : forge de `role:admin` sur n'importe quel
# `company_id`. Aucun mode dégradé acceptable ⇒ refus de démarrer (contrairement au webhook, dont
# seule la route se désactive).


def _settings(**surcharges):
    from apps.api.core.config import Settings

    return Settings(**surcharges)


def test_adaptateur_jwt_hors_dev_sans_secret_refuse_de_demarrer():
    from apps.api.core.config import SECRET_DEV_DEFAUT

    with pytest.raises(ValidationError):
        _settings(environment="prod", mc_host_adapter="jwt", sgi_jwt_secret=SECRET_DEV_DEFAUT)


def test_adaptateur_jwt_hors_dev_secret_vide_refuse_de_demarrer():
    # Cas le PLUS probable en pratique : le compose prod injecte `${SGI_JWT_SECRET:-}`, donc une
    # chaîne VIDE quand l'opérateur n'a rien posé. Ne tester que l'égalité au défaut le raterait.
    with pytest.raises(ValidationError):
        _settings(environment="prod", mc_host_adapter="jwt", sgi_jwt_secret="")
    with pytest.raises(ValidationError):
        _settings(environment="prod", mc_host_adapter="jwt", sgi_jwt_secret="   ")


def test_adaptateur_jwt_hors_dev_avec_secret_demarre():
    s = _settings(environment="prod", mc_host_adapter="jwt", sgi_jwt_secret="un-vrai-secret-hote")
    assert s.mc_host_adapter == "jwt"


def test_adaptateur_local_hors_dev_sans_secret_demarre():
    # Non-régression : le déploiement actuel tourne en `local` et n'utilise PAS ce secret —
    # l'exiger bloquerait un déploiement qui n'a rien demandé.
    from apps.api.core.config import SECRET_DEV_DEFAUT

    s = _settings(environment="prod", mc_host_adapter="local", sgi_jwt_secret=SECRET_DEV_DEFAUT)
    assert s.mc_host_adapter == "local"


def test_adaptateur_jwt_en_dev_sans_secret_demarre():
    from apps.api.core.config import SECRET_DEV_DEFAUT

    s = _settings(environment="development", mc_host_adapter="jwt", sgi_jwt_secret=SECRET_DEV_DEFAUT)
    assert s.mc_host_adapter == "jwt"


def test_adaptateur_jwt_defaut_avec_espaces_parasites_refuse_de_demarrer():
    """F1 (audit adverse) : idem côté JWT. Le validator strippait pour tester le vide mais PAS pour
    comparer au défaut — `dev-insecure-change-me\\n` démarrait donc sur un secret public."""
    from apps.api.core.config import SECRET_DEV_DEFAUT

    for valeur in (SECRET_DEV_DEFAUT + "\n", SECRET_DEV_DEFAUT + " ", " " + SECRET_DEV_DEFAUT):
        with pytest.raises(ValidationError):
            _settings(environment="prod", mc_host_adapter="jwt", sgi_jwt_secret=valeur)

