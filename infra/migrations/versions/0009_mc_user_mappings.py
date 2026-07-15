"""Ajoute mc_user_mappings — lien utilisateur hôte ↔ installation

Relie un `external_user_id` (identité côté plateforme hôte) à une installation,
avec un mapping optionnel vers l'`User` local (mode embarqué). Unicité
`(installation_id, external_user_id)` : deux installations peuvent partager la
même clé locale sans collision. FK `installation_id` en RESTRICT (jamais de
cascade destructive sur les lignes tenant) ; `local_user_id` en SET NULL (User
soft-deleted, on conserve le mapping).

Backfill : rattache chaque `users` existant à l'installation `local` afin que les
utilisateurs V0 authentifiés résolvent un contexte tenant dès P1.

Revision ID: 0009_mc_user_mappings
Revises: 0008_mc_installations
Create Date: 2026-07-15
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_mc_user_mappings"
down_revision: str | None = "0008_mc_installations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOCAL_INSTALLATION_ID = "c809b482-c662-5990-a436-999e973b437b"


def upgrade() -> None:
    op.create_table(
        "mc_user_mappings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("installation_id", sa.Uuid(), nullable=False),
        sa.Column("external_user_id", sa.String(length=255), nullable=False),
        sa.Column("local_user_id", sa.Uuid(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("role", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["installation_id"], ["mc_installations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["local_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "installation_id", "external_user_id", name="uq_user_mapping_installation_external"
        ),
    )
    op.create_index("ix_mc_user_mappings_installation_id", "mc_user_mappings", ["installation_id"])
    op.create_index("ix_mc_user_mappings_local_user_id", "mc_user_mappings", ["local_user_id"])

    # Backfill idempotent : rattache les users V0 existants à l'installation locale.
    op.execute(
        sa.text(
            "INSERT INTO mc_user_mappings "
            "(id, installation_id, external_user_id, local_user_id, email, role, status) "
            "SELECT gen_random_uuid(), CAST(:inst AS uuid), u.id::text, u.id, u.email, u.role, 'active' "
            "FROM users u "
            "WHERE NOT EXISTS ("
            "  SELECT 1 FROM mc_user_mappings m "
            "  WHERE m.installation_id = CAST(:inst AS uuid) AND m.external_user_id = u.id::text"
            ")"
        ).bindparams(inst=_LOCAL_INSTALLATION_ID)
    )


def downgrade() -> None:
    op.drop_index("ix_mc_user_mappings_local_user_id", table_name="mc_user_mappings")
    op.drop_index("ix_mc_user_mappings_installation_id", table_name="mc_user_mappings")
    op.drop_table("mc_user_mappings")
