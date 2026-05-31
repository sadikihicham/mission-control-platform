"""Seed minimal : 1 user admin + le projet mission-control. Idempotent.

Lancement : `python -m apps.api.seed` (DATABASE_URL doit pointer une base migrée).
"""
from sqlalchemy import select

from apps.api.core.db import get_sessionmaker
from apps.api.core.security import hash_password
from apps.api.models import Project, ProjectStatus, User

# Comptes de démo (un par rôle) — mot de passe = nom du rôle.
SEED_USERS = [
    ("admin@mc.local", "admin", "admin"),
    ("cto@mc.local", "cto", "cto"),
    ("pm@mc.local", "pm", "pm"),
    ("dev@mc.local", "developer", "developer"),
    ("viewer@mc.local", "viewer", "viewer"),
]


def run() -> None:
    Session = get_sessionmaker()
    with Session() as db:
        for email, pwd, role in SEED_USERS:
            if not db.scalar(select(User).where(User.email == email)):
                db.add(User(email=email, hashed_password=hash_password(pwd), role=role))
                print(f"+ user {email} (rôle {role}, mdp: {pwd})")
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
