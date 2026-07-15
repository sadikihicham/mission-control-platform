"""Control plane V1 : affectations, runs et étapes de run (P4, SP3)

Crée les trois tables du plan de contrôle des runs (schéma solution §8) :

- `agent_project_assignments` : affectation agent↔projet (rôle, statut, capacité).
  Unicité d'une affectation **active** garantie par un index unique partiel
  (`WHERE status = 'active'`) — un même couple agent/projet ne peut avoir deux
  affectations actives, mais l'historique (affectations terminées) est conservé.
- `agent_runs` : run borné d'un agent (tenant `installation_id`, projet, tâche,
  agent). L'`id` est la clé fournie par le producteur (uuid du run côté agent) :
  idempotence naturelle et corrélation directe avec `agent_events.run_id`
  (renseigné en P3 sans FK). L'état suit la machine `run` figée en P0
  (`RUN_TRANSITIONS`) ; les états terminaux sont immuables (un retry crée un
  NOUVEAU run lié via `retry_of_run_id`, il ne rouvre jamais l'ancien).
- `agent_run_steps` : étapes/tool calls d'un run, unique `(run_id, sequence)`.
  Aucun prompt/secret brut : uniquement des résumés (`input_summary`/`output_summary`).

Additif et réversible. FK tenant/agent en RESTRICT (jamais de cascade destructive
sur l'historique d'un tenant/agent) ; FK projet/tâche en SET NULL (un run survit
à la suppression de son projet/tâche, il garde sa trace auditable). Pas de FK
`agent_events.run_id → agent_runs.id` : le journal d'événements est append-only
et tolère un `run_id` orphelin/hors-ordre (un événement d'audit valide ne doit
jamais être rejeté par une contrainte référentielle) — la timeline joint par
égalité au moment de la lecture.

Revision ID: 0013_agent_runs
Revises: 0012_agent_events_outbox
Create Date: 2026-07-15
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_agent_runs"
down_revision: str | None = "0012_agent_events_outbox"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Affectations agent↔projet ---
    op.create_table(
        "agent_project_assignments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("installation_id", sa.Uuid(), nullable=True),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False, server_default="runner"),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("assigned_by", sa.Uuid(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["installation_id"], ["mc_installations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_agent_project_assignments_installation_id",
        "agent_project_assignments",
        ["installation_id"],
    )
    op.create_index(
        "ix_agent_project_assignments_agent_id", "agent_project_assignments", ["agent_id"]
    )
    op.create_index(
        "ix_agent_project_assignments_project_id", "agent_project_assignments", ["project_id"]
    )
    # Unicité d'une affectation ACTIVE (index partiel) : pas deux actives pour un
    # même couple agent/projet, mais autant d'affectations terminées que voulu.
    op.create_index(
        "uq_agent_project_assignment_active",
        "agent_project_assignments",
        ["agent_id", "project_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    # --- Runs ---
    op.create_table(
        "agent_runs",
        # id = clé fournie par le producteur (uuid du run côté agent). Corrèle
        # directement avec agent_events.run_id (P3). Idempotence naturelle.
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("installation_id", sa.Uuid(), nullable=True),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("external_run_key", sa.String(length=120), nullable=True),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("state", sa.String(length=30), nullable=False, server_default="queued"),
        # Lien de retry : un nouveau run rejouant un run terminal pointe l'original.
        sa.Column("retry_of_run_id", sa.Uuid(), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("run_metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        # Verrou optimiste : incrémenté à chaque transition, empêche l'écrasement.
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["installation_id"], ["mc_installations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["retry_of_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_agent_runs_installation_id", "agent_runs", ["installation_id"])
    op.create_index("ix_agent_runs_agent_id", "agent_runs", ["agent_id"])
    op.create_index("ix_agent_runs_project_id", "agent_runs", ["project_id"])
    op.create_index("ix_agent_runs_task_id", "agent_runs", ["task_id"])
    # Pagination tenant-scoped par récence (created_at DESC, id DESC).
    op.create_index(
        "ix_agent_runs_installation_created", "agent_runs", ["installation_id", "created_at"]
    )

    # --- Étapes de run ---
    op.create_table(
        "agent_run_steps",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(length=40), nullable=False, server_default="step"),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=False, server_default="started"),
        sa.Column("tool_name", sa.String(length=120), nullable=True),
        sa.Column("input_summary", sa.Text(), nullable=True),
        sa.Column("output_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("step_metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # CASCADE : les étapes appartiennent à leur run (pas un historique tenant
        # indépendant) — mais un run n'est jamais hard-deleted en pratique.
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("run_id", "sequence", name="uq_agent_run_steps_run_sequence"),
    )
    op.create_index("ix_agent_run_steps_run_id", "agent_run_steps", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_run_steps_run_id", table_name="agent_run_steps")
    op.drop_table("agent_run_steps")

    op.drop_index("ix_agent_runs_installation_created", table_name="agent_runs")
    op.drop_index("ix_agent_runs_task_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_project_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_agent_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_installation_id", table_name="agent_runs")
    op.drop_table("agent_runs")

    op.drop_index("uq_agent_project_assignment_active", table_name="agent_project_assignments")
    op.drop_index(
        "ix_agent_project_assignments_project_id", table_name="agent_project_assignments"
    )
    op.drop_index(
        "ix_agent_project_assignments_agent_id", table_name="agent_project_assignments"
    )
    op.drop_index(
        "ix_agent_project_assignments_installation_id", table_name="agent_project_assignments"
    )
    op.drop_table("agent_project_assignments")
