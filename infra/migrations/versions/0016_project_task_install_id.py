"""Ajoute installation_id (tenant V1) sur projects et tasks — P8

Ferme le gap assumé au Gate P7 : les tables V0 `projects`/`tasks` n'avaient pas
de colonne tenant, ce qui interdisait de les exposer sous `/agent-control/v1`
sans risque de fuite cross-tenant (critère de rejet dur). Cette migration
réintroduit l'isolation via `installation_id` (ADR-0003/0007), pas via l'ancienne
colonne `company_id` retirée en 0007.

Additive et réversible :
- colonne `installation_id` **nullable** (compat V0 : un producteur/écran V0
  n'en dépend jamais, ADR-0007), FK vers `mc_installations` en RESTRICT (jamais
  de cascade destructive sur l'historique d'un tenant) ;
- backfill idempotent des lignes existantes vers l'installation déterministe
  `local` (même identité que `LOCAL_INSTALLATION_ID`), pour que les données V0
  restent accessibles sous le tenant local sans inventer un tenant de production.

Aucune colonne/route/payload existant n'est muté (Contract A intact, §12).

Revision ID: 0016_project_task_install_id
Revises: 0015_costs_budgets_alerts_audit
Create Date: 2026-07-16
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_project_task_install_id"
down_revision: str | None = "0015_costs_budgets_alerts_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Aligné sur models.agent_control.LOCAL_INSTALLATION_ID /
# integrations.local_adapter.LOCAL_INSTALLATION_ID (uuid5 déterministe). L'insert
# de cette ligne est garanti par la migration 0008 (ON CONFLICT DO NOTHING).
_LOCAL_INSTALLATION_ID = "c809b482-c662-5990-a436-999e973b437b"


def _add_installation_id(table: str) -> None:
    op.add_column(
        table,
        sa.Column(
            "installation_id",
            sa.Uuid(),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        f"fk_{table}_installation_id",
        table,
        "mc_installations",
        ["installation_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        f"ix_{table}_installation_id",
        table,
        ["installation_id"],
    )
    # Backfill idempotent : rattache les lignes V0 existantes au tenant local.
    op.execute(
        sa.text(
            f"UPDATE {table} SET installation_id = CAST(:id AS uuid) "
            "WHERE installation_id IS NULL"
        ).bindparams(id=_LOCAL_INSTALLATION_ID)
    )


def _drop_installation_id(table: str) -> None:
    op.drop_index(f"ix_{table}_installation_id", table_name=table)
    op.drop_constraint(f"fk_{table}_installation_id", table, type_="foreignkey")
    op.drop_column(table, "installation_id")


def upgrade() -> None:
    _add_installation_id("projects")
    _add_installation_id("tasks")


def downgrade() -> None:
    _drop_installation_id("tasks")
    _drop_installation_id("projects")
