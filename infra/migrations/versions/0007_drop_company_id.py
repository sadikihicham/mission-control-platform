"""Retire company_id (users/projects) — colonne réservée jamais activée

Colonne posée dès la migration initiale pour un multi-tenant V1 qui n'a jamais
démarré : aucune clause de filtre ne la lit nulle part dans le code (finding
project-cartographer). La laisser en place est un faux signal d'isolation.
Si le multi-tenant redémarre un jour, elle sera réintroduite avec son filtre
actif dans le même changement, pas avant.

Revision ID: 0007_drop_company_id
Revises: 0006_user_active
Create Date: 2026-07-15
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_drop_company_id"
down_revision: str | None = "0006_user_active"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("users", "company_id")
    op.drop_column("projects", "company_id")


def downgrade() -> None:
    op.add_column("projects", sa.Column("company_id", sa.Uuid(), nullable=True))
    op.add_column("users", sa.Column("company_id", sa.Uuid(), nullable=True))
