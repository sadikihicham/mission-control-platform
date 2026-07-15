"""Seed idempotent : users de démo + projets (demo-crm + vitrine persistée).

Lancement : `python -m apps.api.seed` (DATABASE_URL doit pointer une base migrée).
La vitrine d'orchestration (projet → tâches → sous-tâches) est désormais
persistée en base (cf. `_seed_showcase`) au lieu d'une fixture lue à l'exécution.
"""
import os
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core.db import get_sessionmaker
from apps.api.core.security import hash_password
from apps.api.models import (
    LOCAL_INSTALLATION_ID,
    LOCAL_INSTALLATION_KEY,
    MCInstallation,
    MCUserMapping,
    Project,
    ProjectStatus,
    Task,
    User,
)
from apps.api.services.project_seed import PROJECTS

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


def _seed_showcase(db: Session) -> None:
    """Persiste le(s) projet(s) vitrine + leurs tâches/sous-tâches (idempotent).

    Remplace les fixtures Python lues à l'exécution : la structure vit désormais
    en base. Idempotence par clés naturelles — `projects.slug` et `(project_id,
    tasks.code)`. Le projet est marqué `is_seed=True` (non éditable via l'API).
    Les états/taux restent superposés en live depuis la flotte (`agent_key`).
    """
    for proj in PROJECTS:
        project = db.scalar(select(Project).where(Project.slug == proj["id"]))
        if project is None:
            project = Project(
                slug=proj["id"],
                name=proj["name"],
                description=proj.get("description"),
                status=ProjectStatus(proj.get("status", "in_dev")),
                is_seed=True,
            )
            db.add(project)
            db.flush()
            print(f"+ projet vitrine {project.slug} ({len(proj['tasks'])} tâches)")
        elif not project.is_seed:
            # Rattrape un projet vitrine créé avant la migration 0010.
            project.is_seed = True

        for t_pos, t in enumerate(proj["tasks"]):
            lead = (t.get("agents") or [None])[0]
            task = db.scalar(
                select(Task).where(Task.project_id == project.id, Task.code == t["id"])
            )
            if task is None:
                task = Task(
                    project_id=project.id,
                    code=t["id"],
                    title=t["title"],
                    module=t.get("module"),
                    agent_key=lead,
                    position=t_pos,
                    status="todo",
                )
                db.add(task)
                db.flush()
            for s_pos, sub_title in enumerate(t.get("subtasks", [])):
                # Séparateur "/" (jamais présent dans un code racine "M3.5") pour
                # éviter toute collision de la contrainte unique (project_id, code)
                # entre une sous-tâche et une tâche racine (ex. M3 5e sous-tâche
                # vs tâche racine M3.5).
                sub_code = f"{t['id']}/{s_pos + 1}"
                exists = db.scalar(
                    select(Task).where(
                        Task.project_id == project.id, Task.code == sub_code
                    )
                )
                if exists is None:
                    db.add(
                        Task(
                            project_id=project.id,
                            parent_id=task.id,
                            code=sub_code,
                            title=sub_title,
                            agent_key=lead,
                            position=s_pos,
                            status="todo",
                        )
                    )
    db.commit()


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

        # Vitrine d'orchestration persistée (projet + tâches + sous-tâches).
        _seed_showcase(db)

        # --- Agent Control V1 : installation locale + mappings utilisateurs ---
        # Idempotent : conftest reconstruit le schéma via create_all (sans alembic),
        # donc le socle tenancy doit exister après seed pour que /agent-control/v1
        # résolve un contexte. L'id est déterministe (aligné local_adapter).
        installation = db.get(MCInstallation, LOCAL_INSTALLATION_ID)
        if installation is None:
            installation = MCInstallation(
                id=LOCAL_INSTALLATION_ID,
                external_tenant_id=LOCAL_INSTALLATION_KEY,
                installation_key=LOCAL_INSTALLATION_KEY,
                status="active",
            )
            db.add(installation)
            print(f"+ installation locale {LOCAL_INSTALLATION_KEY} ({LOCAL_INSTALLATION_ID})")
        db.commit()

        for user in db.scalars(select(User)).all():
            existing = db.scalar(
                select(MCUserMapping).where(
                    MCUserMapping.installation_id == LOCAL_INSTALLATION_ID,
                    MCUserMapping.external_user_id == str(user.id),
                )
            )
            if existing is None:
                db.add(
                    MCUserMapping(
                        installation_id=LOCAL_INSTALLATION_ID,
                        external_user_id=str(user.id),
                        local_user_id=user.id,
                        email=user.email,
                        display_name=user.full_name,
                        role=user.role,
                        status="active",
                    )
                )
                print(f"+ mapping user {user.email} → installation locale")
        db.commit()
    print("seed OK")


if __name__ == "__main__":
    run()
