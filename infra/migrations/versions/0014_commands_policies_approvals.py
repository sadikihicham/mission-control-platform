"""Contrôle P5 : politiques, demandes d'approbation et commandes agent (SP3)

Crée les trois tables du plan de contrôle humain (schéma solution §
`agent_policies` / `approval_requests` / `agent_commands`) :

- `agent_policies` : règles `allow|deny|require_approval` par portée
  (installation|project|agent), action ciblée, priorité et version optimiste.
  Évaluation déterministe et auditée (cf. `services/policies.py`).
- `approval_requests` : demande d'approbation liée à une commande soumise à
  `require_approval`. Décision **versionnée** (`version`, verrou optimiste) pour
  empêcher toute double décision concurrente. SLA/expiration via `expires_at`.
- `agent_commands` : file de commandes vers un agent (livraison long poll, ACK,
  résultat). Idempotence par `(installation_id, idempotency_key)`. Une commande
  sous `require_approval` reste `queued` non libérée (`released_at IS NULL`) tant
  qu'aucune décision positive n'existe.

Additif et réversible. FK tenant/agent en RESTRICT (jamais de cascade destructive
sur l'historique d'un tenant/agent) ; FK projet/tâche/run/policy en SET NULL (une
commande/approbation survit à la disparition de son contexte, trace préservée).
Ordre de création respectant les dépendances : policies → approvals → commands.

Revision ID: 0014_commands_policies_approvals
Revises: 0013_agent_runs
Create Date: 2026-07-15
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_commands_policies_approvals"
down_revision: str | None = "0013_agent_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Politiques de gouvernance ---
    op.create_table(
        "agent_policies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("installation_id", sa.Uuid(), nullable=True),
        sa.Column(
            "scope_type", sa.String(length=20), nullable=False, server_default="installation"
        ),
        sa.Column("scope_id", sa.Uuid(), nullable=True),
        sa.Column("action_type", sa.String(length=120), nullable=False, server_default="*"),
        sa.Column("effect", sa.String(length=20), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=True),
        sa.Column("conditions", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["installation_id"], ["mc_installations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_agent_policies_installation_id", "agent_policies", ["installation_id"])
    op.create_index(
        "ix_agent_policies_installation_scope",
        "agent_policies",
        ["installation_id", "scope_type"],
    )

    # --- Demandes d'approbation ---
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("installation_id", sa.Uuid(), nullable=True),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=True),
        sa.Column("action_type", sa.String(length=120), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("context", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column("requested_by_agent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("assigned_to", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_by", sa.Uuid(), nullable=True),
        sa.Column("decision_comment", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["installation_id"], ["mc_installations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["policy_id"], ["agent_policies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["decision_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_approval_requests_installation_id", "approval_requests", ["installation_id"]
    )
    op.create_index("ix_approval_requests_agent_id", "approval_requests", ["agent_id"])
    op.create_index(
        "ix_approval_requests_installation_created",
        "approval_requests",
        ["installation_id", "created_at"],
    )
    op.create_index(
        "ix_approval_requests_installation_status",
        "approval_requests",
        ["installation_id", "status"],
    )

    # --- Commandes agent ---
    op.create_table(
        "agent_commands",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("installation_id", sa.Uuid(), nullable=True),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("command_type", sa.String(length=120), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column("approval_request_id", sa.Uuid(), nullable=True),
        sa.Column("policy_id", sa.Uuid(), nullable=True),
        sa.Column("policy_effect", sa.String(length=20), nullable=True),
        sa.Column("risk_level", sa.String(length=20), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_status", sa.String(length=20), nullable=True),
        sa.Column("result_payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["installation_id"], ["mc_installations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["approval_request_id"], ["approval_requests.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["policy_id"], ["agent_policies.id"], ondelete="SET NULL"),
        # Idempotence par tenant : une clé ne matérialise qu'une commande.
        sa.UniqueConstraint(
            "installation_id", "idempotency_key", name="uq_agent_commands_idempotency"
        ),
    )
    op.create_index("ix_agent_commands_installation_id", "agent_commands", ["installation_id"])
    op.create_index("ix_agent_commands_agent_id", "agent_commands", ["agent_id"])
    op.create_index("ix_agent_commands_run_id", "agent_commands", ["run_id"])
    op.create_index("ix_agent_commands_agent_status", "agent_commands", ["agent_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_agent_commands_agent_status", table_name="agent_commands")
    op.drop_index("ix_agent_commands_run_id", table_name="agent_commands")
    op.drop_index("ix_agent_commands_agent_id", table_name="agent_commands")
    op.drop_index("ix_agent_commands_installation_id", table_name="agent_commands")
    op.drop_table("agent_commands")

    op.drop_index(
        "ix_approval_requests_installation_status", table_name="approval_requests"
    )
    op.drop_index(
        "ix_approval_requests_installation_created", table_name="approval_requests"
    )
    op.drop_index("ix_approval_requests_agent_id", table_name="approval_requests")
    op.drop_index("ix_approval_requests_installation_id", table_name="approval_requests")
    op.drop_table("approval_requests")

    op.drop_index("ix_agent_policies_installation_scope", table_name="agent_policies")
    op.drop_index("ix_agent_policies_installation_id", table_name="agent_policies")
    op.drop_table("agent_policies")
