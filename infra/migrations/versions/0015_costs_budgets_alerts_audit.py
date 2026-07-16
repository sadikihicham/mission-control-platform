"""Coûts, budgets, alertes et audit — P6, SP6

Crée les quatre tables du plan opérationnel (schéma solution §
`agent_usage_records` / `agent_budgets` / `agent_alerts` / `mc_audit_logs`) :

- `agent_usage_records` : consommation (tokens/appels/durée) et coût d'un run/
  agent. Coût en `Numeric` décimal (jamais float). Idempotence par
  `(installation_id, source_event_id)` — rejouer un événement d'ingest ne double
  jamais la consommation, donc la somme reste réconciliable avec les agrégats.
- `agent_budgets` : seuil configurable par portée/période. Consommation
  recalculée à la demande depuis `agent_usage_records` (source unique).
- `agent_alerts` : alerte dédupliquée par `dedup_key` — un index unique partiel
  (`WHERE status <> 'resolved'`) empêche toute re-détection de dupliquer une
  condition déjà ouverte/acquittée.
- `mc_audit_logs` : journal append-only et redacted. Garanti append-only en
  base par un trigger PostgreSQL qui lève une exception sur UPDATE/DELETE
  (défense en profondeur, en plus de la garantie applicative).

Additif et réversible. FK tenant/agent en RESTRICT (jamais de cascade
destructive sur l'historique d'un tenant/agent) ; FK projet/run/utilisateur en
SET NULL (un enregistrement de coût/alerte/audit survit à la disparition de son
contexte, trace préservée).

Revision ID: 0015_costs_budgets_alerts_audit
Revises: 0014_commands_policies_approvals
Create Date: 2026-07-15
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_costs_budgets_alerts_audit"
down_revision: str | None = "0014_commands_policies_approvals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Consommation et coûts ---
    op.create_table(
        "agent_usage_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("installation_id", sa.Uuid(), nullable=True),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=60), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("calls", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("unit_cost_input", sa.Numeric(20, 10), nullable=True),
        sa.Column("unit_cost_output", sa.Numeric(20, 10), nullable=True),
        sa.Column("cost", sa.Numeric(20, 8), nullable=False, server_default="0"),
        sa.Column("pricing_version", sa.String(length=40), nullable=False),
        sa.Column("source_event_id", sa.String(length=255), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["installation_id"], ["mc_installations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "installation_id", "source_event_id", name="uq_agent_usage_source_event"
        ),
    )
    op.create_index(
        "ix_agent_usage_records_installation_id", "agent_usage_records", ["installation_id"]
    )
    op.create_index("ix_agent_usage_records_agent_id", "agent_usage_records", ["agent_id"])
    op.create_index("ix_agent_usage_records_project_id", "agent_usage_records", ["project_id"])
    op.create_index("ix_agent_usage_records_run_id", "agent_usage_records", ["run_id"])
    op.create_index(
        "ix_agent_usage_installation_occurred",
        "agent_usage_records",
        ["installation_id", "occurred_at"],
    )
    op.create_index(
        "ix_agent_usage_agent_occurred", "agent_usage_records", ["agent_id", "occurred_at"]
    )

    # --- Budgets ---
    op.create_table(
        "agent_budgets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("installation_id", sa.Uuid(), nullable=True),
        sa.Column(
            "scope_type", sa.String(length=20), nullable=False, server_default="installation"
        ),
        sa.Column("scope_id", sa.Uuid(), nullable=True),
        sa.Column("period", sa.String(length=20), nullable=False, server_default="monthly"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("amount_limit", sa.Numeric(20, 8), nullable=False),
        sa.Column(
            "thresholds", postgresql.JSONB(), nullable=False, server_default="[50, 80, 100]"
        ),
        sa.Column("on_exceed", sa.String(length=30), nullable=False, server_default="alert"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["installation_id"], ["mc_installations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_agent_budgets_installation_id", "agent_budgets", ["installation_id"])
    op.create_index(
        "ix_agent_budgets_installation_scope", "agent_budgets", ["installation_id", "scope_type"]
    )

    # --- Alertes ---
    op.create_table(
        "agent_alerts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("installation_id", sa.Uuid(), nullable=True),
        sa.Column("alert_type", sa.String(length=60), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="warning"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("target_type", sa.String(length=40), nullable=True),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("dedup_key", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", sa.Uuid(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["installation_id"], ["mc_installations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["acknowledged_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_agent_alerts_installation_id", "agent_alerts", ["installation_id"])
    op.create_index(
        "ix_agent_alerts_installation_status", "agent_alerts", ["installation_id", "status"]
    )
    op.create_index(
        "ix_agent_alerts_installation_opened", "agent_alerts", ["installation_id", "opened_at"]
    )
    # Dédup : une condition (installation, dedup_key) ne peut avoir qu'une seule
    # alerte non résolue à la fois — index unique PARTIEL (les lignes 'resolved'
    # n'y sont pas soumises, une même condition peut se rouvrir plus tard).
    op.create_index(
        "uq_agent_alerts_dedup_unresolved",
        "agent_alerts",
        ["installation_id", "dedup_key"],
        unique=True,
        postgresql_where=sa.text("status <> 'resolved'"),
    )

    # --- Audit ---
    op.create_table(
        "mc_audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("installation_id", sa.Uuid(), nullable=True),
        sa.Column("actor_type", sa.String(length=20), nullable=False, server_default="system"),
        sa.Column("actor_id", sa.String(length=255), nullable=True),
        sa.Column("actor_label", sa.String(length=255), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=60), nullable=True),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column("before", postgresql.JSONB(), nullable=True),
        sa.Column("after", postgresql.JSONB(), nullable=True),
        sa.Column("request_id", sa.String(length=255), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("audit_metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["installation_id"], ["mc_installations.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_mc_audit_logs_installation_id", "mc_audit_logs", ["installation_id"])
    op.create_index(
        "ix_mc_audit_logs_installation_created",
        "mc_audit_logs",
        ["installation_id", "created_at"],
    )
    op.create_index(
        "ix_mc_audit_logs_installation_action", "mc_audit_logs", ["installation_id", "action"]
    )

    # Défense en profondeur : append-only garanti aussi côté base, pas seulement
    # applicatif (aucune route/service ne mute une ligne d'audit).
    op.execute(
        """
        CREATE FUNCTION mc_audit_logs_append_only() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'mc_audit_logs is append-only: % not allowed', TG_OP;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_mc_audit_logs_append_only
        BEFORE UPDATE OR DELETE ON mc_audit_logs
        FOR EACH ROW EXECUTE FUNCTION mc_audit_logs_append_only()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_mc_audit_logs_append_only ON mc_audit_logs")
    op.execute("DROP FUNCTION IF EXISTS mc_audit_logs_append_only()")

    op.drop_index("ix_mc_audit_logs_installation_action", table_name="mc_audit_logs")
    op.drop_index("ix_mc_audit_logs_installation_created", table_name="mc_audit_logs")
    op.drop_index("ix_mc_audit_logs_installation_id", table_name="mc_audit_logs")
    op.drop_table("mc_audit_logs")

    op.drop_index("uq_agent_alerts_dedup_unresolved", table_name="agent_alerts")
    op.drop_index("ix_agent_alerts_installation_opened", table_name="agent_alerts")
    op.drop_index("ix_agent_alerts_installation_status", table_name="agent_alerts")
    op.drop_index("ix_agent_alerts_installation_id", table_name="agent_alerts")
    op.drop_table("agent_alerts")

    op.drop_index("ix_agent_budgets_installation_scope", table_name="agent_budgets")
    op.drop_index("ix_agent_budgets_installation_id", table_name="agent_budgets")
    op.drop_table("agent_budgets")

    op.drop_index("ix_agent_usage_agent_occurred", table_name="agent_usage_records")
    op.drop_index("ix_agent_usage_installation_occurred", table_name="agent_usage_records")
    op.drop_index("ix_agent_usage_records_run_id", table_name="agent_usage_records")
    op.drop_index("ix_agent_usage_records_project_id", table_name="agent_usage_records")
    op.drop_index("ix_agent_usage_records_agent_id", table_name="agent_usage_records")
    op.drop_index("ix_agent_usage_records_installation_id", table_name="agent_usage_records")
    op.drop_table("agent_usage_records")
