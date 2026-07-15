"""Ajoute mc_installations — socle tenancy Agent Control V1 (installation_id)

Table du registre des installations du module dans un tenant hôte. Additive :
aucune table/colonne V0 modifiée (Contract A intact, ADR-0007). Le tenant est
résolu serveur via `HostTenantPort` (ADR-0003) ; `installation_key` préfixe les
clés d'agent `<installation_key>:<local_key>` (ADR-0006).

Backfill : insère l'installation déterministe `local` (mode autonome / dev) pour
que les données V0 restent accessibles sans inventer un tenant de production.

Revision ID: 0008_mc_installations
Revises: 0007_drop_company_id
Create Date: 2026-07-15
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0008_mc_installations"
down_revision: str | None = "0007_drop_company_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Doit rester aligné sur models.agent_control.LOCAL_INSTALLATION_ID /
# integrations.local_adapter.LOCAL_INSTALLATION_ID (uuid5 déterministe).
_LOCAL_INSTALLATION_ID = "c809b482-c662-5990-a436-999e973b437b"
_LOCAL_INSTALLATION_KEY = "local"


def upgrade() -> None:
    op.create_table(
        "mc_installations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("external_tenant_id", sa.String(length=255), nullable=False),
        sa.Column("installation_key", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("settings", JSONB(), nullable=False, server_default="{}"),
        sa.Column("feature_flags", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_mc_installations_external_tenant_id", "mc_installations", ["external_tenant_id"])
    op.create_index(
        "ix_mc_installations_installation_key", "mc_installations", ["installation_key"], unique=True
    )

    # Backfill idempotent : installation locale déterministe.
    op.execute(
        sa.text(
            "INSERT INTO mc_installations (id, external_tenant_id, installation_key, status) "
            "VALUES (CAST(:id AS uuid), :key, :key, 'active') "
            "ON CONFLICT (installation_key) DO NOTHING"
        ).bindparams(id=_LOCAL_INSTALLATION_ID, key=_LOCAL_INSTALLATION_KEY)
    )


def downgrade() -> None:
    op.drop_index("ix_mc_installations_installation_key", table_name="mc_installations")
    op.drop_index("ix_mc_installations_external_tenant_id", table_name="mc_installations")
    op.drop_table("mc_installations")
