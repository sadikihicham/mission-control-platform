"""Persistance de la hiérarchie projet→tâche→sous-tâche (Agent Control P2)

Rend réelles en base les tâches et sous-tâches auparavant codées en dur dans
`apps/api/services/project_seed.py`. Changements strictement additifs (Contract A
préservé : aucune colonne existante retirée ou renommée) :

- `projects.is_seed` : marque le projet vitrine de démonstration, non éditable
  via l'API (le seed en est la source). Défaut `false` → les projets V0/CRUD
  existants restent éditables sans intervention.
- `tasks.parent_id` : sous-tâche → tâche racine (un seul niveau, ON DELETE
  CASCADE pour ne pas orpheliner une sous-tâche).
- `tasks.code` : clé naturelle stable par projet (ex. "M0", "M0.1"), ancre de
  seed idempotent et identifiant stable côté frontend.
- `tasks.module`, `tasks.progress`, `tasks.position`, `tasks.agent_key`,
  `tasks.updated_at` : métadonnées d'affichage. `agent_key` porte la clé globale
  Contract D de l'agent attendu (pas une FK) pour superposer l'état live.

Additif et réversible : `downgrade` retire uniquement les colonnes ajoutées ici.

Revision ID: 0010_tasks_hierarchy
Revises: 0009_mc_user_mappings
Create Date: 2026-07-15
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_tasks_hierarchy"
down_revision: str | None = "0009_mc_user_mappings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("is_seed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.add_column("tasks", sa.Column("parent_id", sa.Uuid(), nullable=True))
    op.add_column("tasks", sa.Column("code", sa.String(length=40), nullable=True))
    op.add_column("tasks", sa.Column("module", sa.String(length=120), nullable=True))
    op.add_column(
        "tasks", sa.Column("progress", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "tasks", sa.Column("position", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("tasks", sa.Column("agent_key", sa.String(length=120), nullable=True))
    op.add_column(
        "tasks",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_tasks_parent_id",
        "tasks",
        "tasks",
        ["parent_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_tasks_parent_id", "tasks", ["parent_id"])
    op.create_index("ix_tasks_agent_key", "tasks", ["agent_key"])
    op.create_unique_constraint("uq_tasks_project_code", "tasks", ["project_id", "code"])


def downgrade() -> None:
    op.drop_constraint("uq_tasks_project_code", "tasks", type_="unique")
    op.drop_index("ix_tasks_agent_key", table_name="tasks")
    op.drop_index("ix_tasks_parent_id", table_name="tasks")
    op.drop_constraint("fk_tasks_parent_id", "tasks", type_="foreignkey")
    op.drop_column("tasks", "updated_at")
    op.drop_column("tasks", "agent_key")
    op.drop_column("tasks", "position")
    op.drop_column("tasks", "progress")
    op.drop_column("tasks", "module")
    op.drop_column("tasks", "code")
    op.drop_column("tasks", "parent_id")
    op.drop_column("projects", "is_seed")
