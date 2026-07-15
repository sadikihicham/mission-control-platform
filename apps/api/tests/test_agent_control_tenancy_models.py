"""SP2 — tables tenancy Agent Control (mc_installations / mc_user_mappings).

Vérifie contraintes (unique, FK), isolation par installation (même clé locale
dans deux installations sans collision), présence de l'installation `local`
déterministe après seed, et idempotence du seed.
"""
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from apps.api.models import (
    LOCAL_INSTALLATION_ID,
    LOCAL_INSTALLATION_KEY,
    MCInstallation,
    MCUserMapping,
    User,
)


def _installation(db, key: str) -> MCInstallation:
    inst = MCInstallation(external_tenant_id=key, installation_key=key, status="active")
    db.add(inst)
    db.commit()
    return inst


def test_local_installation_seeded_with_deterministic_id(db):
    inst = db.get(MCInstallation, LOCAL_INSTALLATION_ID)
    assert inst is not None
    assert inst.installation_key == LOCAL_INSTALLATION_KEY
    assert inst.status == "active"


def test_installation_key_unique(db):
    _installation(db, "acme")
    dup = MCInstallation(external_tenant_id="acme", installation_key="acme")
    db.add(dup)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_user_mapping_unique_per_installation(db):
    inst = _installation(db, f"tenant-{uuid.uuid4().hex[:6]}")
    db.add(MCUserMapping(installation_id=inst.id, external_user_id="ext-1"))
    db.commit()
    db.add(MCUserMapping(installation_id=inst.id, external_user_id="ext-1"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_same_external_user_id_across_two_installations_no_collision(db):
    inst_a = _installation(db, f"a-{uuid.uuid4().hex[:6]}")
    inst_b = _installation(db, f"b-{uuid.uuid4().hex[:6]}")
    db.add(MCUserMapping(installation_id=inst_a.id, external_user_id="shared-key"))
    db.add(MCUserMapping(installation_id=inst_b.id, external_user_id="shared-key"))
    # Deux installations, même clé locale → aucune violation d'unicité.
    db.commit()
    count = (
        db.query(MCUserMapping)
        .filter(MCUserMapping.external_user_id == "shared-key")
        .count()
    )
    assert count == 2


def test_mapping_invalid_installation_fk_rejected(db):
    db.add(MCUserMapping(installation_id=uuid.uuid4(), external_user_id="orphan"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_mapping_null_local_user_id_accepted(db):
    inst = _installation(db, f"nulluser-{uuid.uuid4().hex[:6]}")
    db.add(
        MCUserMapping(installation_id=inst.id, external_user_id="ext-null", local_user_id=None)
    )
    db.commit()  # ne doit pas lever


def test_existing_users_backfilled_to_local_installation(db):
    # Le seed a mappé les comptes seedés vers l'installation locale.
    admin = db.scalar(select(User).where(User.email == "admin@mc.local"))
    assert admin is not None
    mapping = (
        db.query(MCUserMapping)
        .filter(
            MCUserMapping.installation_id == LOCAL_INSTALLATION_ID,
            MCUserMapping.local_user_id == admin.id,
        )
        .one_or_none()
    )
    assert mapping is not None
    assert mapping.external_user_id == str(admin.id)


def test_seed_is_idempotent(db):
    from apps.api.seed import run as seed_run

    # 1er passage : mappe aussi les users créés par d'autres tests (DB partagée).
    seed_run()
    db.expire_all()
    inst_after_first = db.query(MCInstallation).count()
    map_after_first = db.query(MCUserMapping).count()
    # 2e passage consécutif : aucune ligne ajoutée → idempotent.
    seed_run()
    db.expire_all()
    assert db.query(MCInstallation).count() == inst_after_first
    assert db.query(MCUserMapping).count() == map_after_first
