"""Registre Agent Control V1 enrichi + credentials individuels (P3, SP2)

Étend `agents` de manière strictement additive (Contract A préservé : aucune
colonne existante retirée ou renommée) avec les métadonnées de registre V1 et le
compteur `last_sequence` (rejet des événements anciens), et crée la table
`agent_credentials` (ADR-0004 : credentials individuels, hashés, scopés,
rotatifs, révocables). Le secret brut n'est jamais stocké — seul `secret_hash`.

Additif et réversible : `downgrade` retire uniquement ce qui est ajouté ici.
Backfill idempotent : rattache les agents V0 existants à l'installation locale
(`installation_id` NULL → local), sans inventer de tenant production. Colonne
`installation_id` **nullable** pour compat V0 (ADR-0007) ; obligatoire au niveau
applicatif pour toute donnée V1.

Revision ID: 0011_agent_registry_credentials
Revises: 0010_tasks_hierarchy
Create Date: 2026-07-15
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_agent_registry_credentials"
down_revision: str | None = "0010_tasks_hierarchy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOCAL_INSTALLATION_ID = "c809b482-c662-5990-a436-999e973b437b"


def upgrade() -> None:
    # --- Extensions additives du registre `agents` (V1) ---
    op.add_column("agents", sa.Column("installation_id", sa.Uuid(), nullable=True))
    op.add_column("agents", sa.Column("display_name", sa.String(length=120), nullable=True))
    op.add_column("agents", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("agents", sa.Column("runtime", sa.String(length=60), nullable=True))
    op.add_column("agents", sa.Column("provider", sa.String(length=60), nullable=True))
    op.add_column("agents", sa.Column("client_version", sa.String(length=60), nullable=True))
    op.add_column("agents", sa.Column("environment", sa.String(length=40), nullable=True))
    op.add_column(
        "agents",
        sa.Column("capabilities", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "agents",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
    )
    op.add_column("agents", sa.Column("registered_by", sa.Uuid(), nullable=True))
    op.add_column("agents", sa.Column("registered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("agents", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "agents",
        sa.Column("last_sequence", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.create_foreign_key(
        "fk_agents_installation_id",
        "agents",
        "mc_installations",
        ["installation_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_agents_registered_by",
        "agents",
        "users",
        ["registered_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_agents_installation_id", "agents", ["installation_id"])

    # Backfill idempotent : rattache les agents V0 sans tenant à l'installation
    # locale déterministe (mode autonome/démo). Aucun tenant production inventé.
    op.execute(
        sa.text(
            "UPDATE agents SET installation_id = CAST(:inst AS uuid) "
            "WHERE installation_id IS NULL"
        ).bindparams(inst=_LOCAL_INSTALLATION_ID)
    )

    # --- Table des credentials agents (ADR-0004) ---
    op.create_table(
        "agent_credentials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("key_prefix", sa.String(length=40), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.Column("scopes", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("key_prefix", name="uq_agent_credentials_key_prefix"),
        sa.UniqueConstraint("secret_hash", name="uq_agent_credentials_secret_hash"),
    )
    op.create_index("ix_agent_credentials_agent_id", "agent_credentials", ["agent_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_credentials_agent_id", table_name="agent_credentials")
    op.drop_table("agent_credentials")

    op.drop_index("ix_agents_installation_id", table_name="agents")
    op.drop_constraint("fk_agents_registered_by", "agents", type_="foreignkey")
    op.drop_constraint("fk_agents_installation_id", "agents", type_="foreignkey")
    op.drop_column("agents", "last_sequence")
    op.drop_column("agents", "revoked_at")
    op.drop_column("agents", "registered_at")
    op.drop_column("agents", "registered_by")
    op.drop_column("agents", "status")
    op.drop_column("agents", "capabilities")
    op.drop_column("agents", "environment")
    op.drop_column("agents", "client_version")
    op.drop_column("agents", "provider")
    op.drop_column("agents", "runtime")
    op.drop_column("agents", "description")
    op.drop_column("agents", "display_name")
    op.drop_column("agents", "installation_id")
