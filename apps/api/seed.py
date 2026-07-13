"""Seed minimal : 1 user admin + le projet mission-control. Idempotent.

Lancement : `python -m apps.api.seed` (DATABASE_URL doit pointer une base migrée).
"""
import os
import sys

from sqlalchemy import select

from apps.api.core.db import get_sessionmaker
from apps.api.core.security import hash_password
from apps.api.models import Project, ProjectStatus, User

# Comptes de démo. Le 1er est le login par défaut de la plateforme.
# (email, mot de passe, rôle, nom affiché, civilité mr|mrs|miss)
SEED_USERS = [
    ("demo@infinity.ae", "password", "admin", "Sultan", "mr"),
    ("admin@mc.local", "admin", "admin", "Admin", "mr"),
    ("cto@mc.local", "cto", "cto", "Mansouri", "mrs"),
    ("pm@mc.local", "pm", "pm", "Karimi", "miss"),
    ("dev@mc.local", "developer", "developer", "Haddad", "mr"),
    ("viewer@mc.local", "viewer", "viewer", "Nadia", "miss"),
]


def run() -> None:
    if os.getenv("ENVIRONMENT", "").lower().startswith("prod"):
        print("refuse : ENVIRONMENT=prod, seed démo interdit en production", file=sys.stderr)
        raise SystemExit(1)
    Session = get_sessionmaker()
    with Session() as db:
        for email, pwd, role, full_name, civility in SEED_USERS:
            existing = db.scalar(select(User).where(User.email == email))
            if not existing:
                db.add(User(
                    email=email, hashed_password=hash_password(pwd), role=role,
                    full_name=full_name, civility=civility,
                ))
                print(f"+ user {email} (rôle {role}, {civility} {full_name}, mdp: {pwd})")
            elif existing.full_name is None and existing.civility is None:
                # Backfill profil pour les comptes seedés avant la migration 0004.
                existing.full_name, existing.civility = full_name, civility
                print(f"~ user {email} : profil ajouté ({civility} {full_name})")
        if not db.scalar(select(Project).where(Project.slug == "demo-crm")):
            db.add(
                Project(
                    slug="demo-crm",
                    name="Démo — CRM Acme",
                    description="Projet exemple (en cours) pour illustrer le CRUD et le dégradé de couleur.",
                    status=ProjectStatus.in_dev,
                    progress=45,
                )
            )
            print("+ projet démo demo-crm (45%)")
        db.commit()
    print("seed OK")


if __name__ == "__main__":
    run()
