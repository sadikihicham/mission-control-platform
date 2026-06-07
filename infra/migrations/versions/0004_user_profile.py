"""users.full_name + users.civility (message d'accueil genré)

Revision ID: 0004_user_profile
Revises: 0003_password_reset
Create Date: 2026-06-01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_user_profile"
down_revision: str | None = "0003_password_reset"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("full_name", sa.String(120), nullable=True))
    op.add_column("users", sa.Column("civility", sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "civility")
    op.drop_column("users", "full_name")
