"""users.is_active (rubrique Administration — désactivation = soft-delete)

Revision ID: 0006_user_active
Revises: 0005_agent_token
Create Date: 2026-07-15
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_user_active"
down_revision: str | None = "0005_agent_token"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("users", "is_active")
