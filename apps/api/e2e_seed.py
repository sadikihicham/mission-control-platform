"""Seed E2E multi-tenant pour la QA Playwright (P9, gap 3).

Crée deux installations tenant distinctes (`local` + `e2e-tenant-b`) avec des
données **reconnaissables par mot-clé** (Alpha vs Beta), pour prouver en bout de
chaîne l'absence de fuite cross-tenant dans l'UI et le respect des profils.

À exécuter APRÈS `python -m apps.api.seed` (qui crée l'installation locale et
mappe les comptes existants). Idempotent : rejouable sans doublon.

Comptes créés (mots de passe déterministes, usage E2E uniquement) :
- `a@e2e.local` / `pw-alpha-123` (admin) → tenant local (Alpha) ;
- `b@e2e.local` / `pw-beta-123` (admin)  → tenant e2e-tenant-b (Beta) ;
- `v@e2e.local` / `pw-viewer-123` (viewer) → tenant local (profil lecture seule).
"""
from __future__ import annotations

from sqlalchemy import select

from apps.api.core.db import get_sessionmaker
from apps.api.core.security import hash_password
from apps.api.models import (
    LOCAL_INSTALLATION_ID,
    Agent,
    MCInstallation,
    MCUserMapping,
    Project,
    User,
)

E2E_TENANT_B_KEY = "e2e-tenant-b"


def _user(db, email: str, pwd: str, role: str = "admin") -> User:
    u = db.scalar(select(User).where(User.email == email))
    if u is None:
        u = User(email=email, hashed_password=hash_password(pwd), role=role, is_active=True)
        db.add(u)
        db.flush()
    return u


def _map(db, user: User, installation_id) -> None:
    existing = db.scalar(
        select(MCUserMapping).where(
            MCUserMapping.installation_id == installation_id,
            MCUserMapping.external_user_id == str(user.id),
        )
    )
    if existing is None:
        db.add(
            MCUserMapping(
                installation_id=installation_id,
                external_user_id=str(user.id),
                local_user_id=user.id,
                email=user.email,
                role=user.role,
                status="active",
            )
        )


def _agent(db, key: str, installation_id, display_name: str) -> None:
    a = db.scalar(select(Agent).where(Agent.agent_key == key))
    if a is None:
        db.add(Agent(agent_key=key, installation_id=installation_id, display_name=display_name))


def _project(db, slug: str, name: str, installation_id) -> None:
    p = db.scalar(select(Project).where(Project.slug == slug))
    if p is None:
        db.add(Project(slug=slug, name=name, installation_id=installation_id))


def run() -> None:
    session_factory = get_sessionmaker()
    with session_factory() as db:
        inst_b = db.scalar(
            select(MCInstallation).where(MCInstallation.installation_key == E2E_TENANT_B_KEY)
        )
        if inst_b is None:
            inst_b = MCInstallation(
                external_tenant_id=E2E_TENANT_B_KEY,
                installation_key=E2E_TENANT_B_KEY,
                status="active",
            )
            db.add(inst_b)
            db.flush()

        user_a = _user(db, "a@e2e.local", "pw-alpha-123", role="admin")
        user_b = _user(db, "b@e2e.local", "pw-beta-123", role="admin")
        user_v = _user(db, "v@e2e.local", "pw-viewer-123", role="viewer")
        db.flush()

        # Le viewer et l'admin A voient le tenant local (Alpha) ; l'admin B voit
        # exclusivement le tenant B (Beta). Aucun mapping croisé.
        _map(db, user_a, LOCAL_INSTALLATION_ID)
        _map(db, user_v, LOCAL_INSTALLATION_ID)
        _map(db, user_b, inst_b.id)

        _agent(db, "local:e2e-alpha-agent", LOCAL_INSTALLATION_ID, "Alpha Agent E2E")
        _agent(db, f"{E2E_TENANT_B_KEY}:e2e-beta-agent", inst_b.id, "Beta Agent E2E")
        _project(db, "e2e-projet-alpha", "Projet Alpha E2E", LOCAL_INSTALLATION_ID)
        _project(db, "e2e-projet-beta", "Projet Beta E2E", inst_b.id)
        db.commit()
    print("e2e seed OK")


if __name__ == "__main__":
    run()
