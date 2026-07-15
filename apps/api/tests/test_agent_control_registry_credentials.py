"""SP2 — registre Agent Control enrichi + credentials individuels (P3).

Vérifie : extensions additives de `agents` (défauts sûrs, tenant nullable),
credentials hashés (secret brut jamais persisté), unicité prefix/hash, statut
dérivé (active|revoked|expired), rotation, contrainte FK agent, et les
primitives crypto réutilisées (`generate_agent_credential`).
"""
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from apps.api.core.security import (
    generate_agent_credential,
    hash_reset_token,
    split_agent_credential,
)
from apps.api.models import (
    LOCAL_INSTALLATION_ID,
    Agent,
    AgentCredential,
)


def _agent(db, key: str | None = None, *, tenant=LOCAL_INSTALLATION_ID) -> Agent:
    agent = Agent(agent_key=key or f"local:reg-{uuid.uuid4().hex[:8]}", installation_id=tenant)
    db.add(agent)
    db.commit()
    return agent


def _new_credential(db, agent: Agent, **kw) -> tuple[AgentCredential, str]:
    key_prefix, secret, secret_hash = generate_agent_credential()
    cred = AgentCredential(
        agent_id=agent.id,
        key_prefix=key_prefix,
        secret_hash=secret_hash,
        scopes=kw.get("scopes", ["ingest"]),
        expires_at=kw.get("expires_at"),
    )
    db.add(cred)
    db.commit()
    return cred, secret


# --- Extensions additives du registre `agents` -------------------------------

def test_agent_registry_defaults(db):
    agent = _agent(db)
    db.refresh(agent)
    assert agent.status == "active"
    assert agent.capabilities == []
    assert agent.last_sequence == 0
    assert agent.installation_id == LOCAL_INSTALLATION_ID
    # Champs registre optionnels absents par défaut (compat V0).
    assert agent.runtime is None and agent.provider is None


def test_agent_installation_id_is_nullable_for_v0_compat(db):
    # Un agent V0 sans tenant reste insérable (colonne nullable, ADR-0007).
    agent = Agent(agent_key=f"local:notenant-{uuid.uuid4().hex[:6]}", installation_id=None)
    db.add(agent)
    db.commit()  # ne doit pas lever


# --- Primitives crypto réutilisées -------------------------------------------

def test_generate_agent_credential_shape_and_hash():
    key_prefix, secret, secret_hash = generate_agent_credential()
    assert key_prefix.startswith("ac_")
    # Le secret complet contient le prefix + un séparateur ; le hash correspond.
    assert secret.startswith(key_prefix + ".")
    assert secret_hash == hash_reset_token(secret)
    assert len(secret_hash) == 64  # SHA-256 hex (même primitive que reset/enrôlement)


def test_split_agent_credential():
    key_prefix, secret, _ = generate_agent_credential()
    assert split_agent_credential(secret) == (key_prefix, secret)
    assert split_agent_credential("no-separator-here") is None
    assert split_agent_credential(".leading") is None


def test_secret_hash_is_stored_never_raw(db):
    agent = _agent(db)
    cred, secret = _new_credential(db, agent)
    db.refresh(cred)
    # Le secret brut n'apparaît sur aucun attribut persisté du credential.
    assert secret != cred.secret_hash
    assert cred.secret_hash == hash_reset_token(secret)
    assert not hasattr(cred, "secret") or getattr(cred, "secret", None) != secret


# --- Contraintes d'unicité et FK ---------------------------------------------

def test_key_prefix_unique(db):
    agent = _agent(db)
    cred, _ = _new_credential(db, agent)
    dup = AgentCredential(agent_id=agent.id, key_prefix=cred.key_prefix, secret_hash="x" * 64)
    db.add(dup)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_secret_hash_unique(db):
    agent = _agent(db)
    cred, _ = _new_credential(db, agent)
    dup = AgentCredential(agent_id=agent.id, key_prefix="ac_deadbeef", secret_hash=cred.secret_hash)
    db.add(dup)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_credential_invalid_agent_fk_rejected(db):
    db.add(AgentCredential(agent_id=uuid.uuid4(), key_prefix="ac_orphan01", secret_hash="y" * 64))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


# --- Statut dérivé + usabilité (machine `credential`) ------------------------

def test_credential_active_is_usable(db):
    agent = _agent(db)
    cred, _ = _new_credential(db, agent)
    assert cred.is_usable() is True
    assert cred.status == "active"


def test_revoked_credential_is_never_usable(db):
    agent = _agent(db)
    cred, _ = _new_credential(db, agent)
    cred.revoked_at = datetime.now(UTC)
    db.commit()
    db.refresh(cred)
    assert cred.is_usable() is False
    assert cred.status == "revoked"


def test_expired_credential_is_never_usable(db):
    agent = _agent(db)
    cred, _ = _new_credential(db, agent, expires_at=datetime.now(UTC) - timedelta(seconds=1))
    db.refresh(cred)
    assert cred.is_usable() is False
    assert cred.status == "expired"


def test_future_expiry_is_usable(db):
    agent = _agent(db)
    cred, _ = _new_credential(db, agent, expires_at=datetime.now(UTC) + timedelta(hours=1))
    assert cred.is_usable() is True


# --- Rotation : nouveau credential + révocation de l'ancien -------------------

def test_rotation_creates_new_and_revokes_old(db):
    agent = _agent(db)
    old, _ = _new_credential(db, agent)
    # Rotation : révoque l'ancien, émet un nouveau (secret différent).
    old.revoked_at = datetime.now(UTC)
    new, new_secret = _new_credential(db, agent)
    db.commit()
    db.refresh(old)
    assert old.status == "revoked" and not old.is_usable()
    assert new.status == "active" and new.is_usable()
    assert new.secret_hash != old.secret_hash
    creds = db.scalars(select(AgentCredential).where(AgentCredential.agent_id == agent.id)).all()
    assert len(creds) == 2  # historique conservé, ancien révoqué


def test_agent_credentials_relationship(db):
    agent = _agent(db)
    _new_credential(db, agent)
    _new_credential(db, agent)
    db.refresh(agent)
    assert len(agent.credentials) == 2
