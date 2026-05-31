"""add projects.repo (dépôt GitHub "owner/name")

Revision ID: 0002_project_repo
Revises: 0001_initial
Create Date: 2026-06-01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_project_repo"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("repo", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "repo")
