"""agents.token_hash + agents.token_issued_at (identité par agent, Contract D)

Revision ID: 0005_agent_token
Revises: 0004_user_profile
Create Date: 2026-07-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_agent_token"
down_revision: str | None = "0004_user_profile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("token_hash", sa.String(64), nullable=True))
    op.add_column(
        "agents", sa.Column("token_issued_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_unique_constraint("uq_agents_token_hash", "agents", ["token_hash"])


def downgrade() -> None:
    op.drop_constraint("uq_agents_token_hash", "agents", type_="unique")
    op.drop_column("agents", "token_issued_at")
    op.drop_column("agents", "token_hash")
