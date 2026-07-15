"""Ingest V1 : journal d'événements append-only + outbox transactionnel (P3, SP4)

Crée `agent_events` (journal append-only des événements V1, idempotence par
producteur `(agent_id, event_id)`, séquence monotone par agent) et
`mc_outbox_events` (outbox ADR-0005 : le fait métier et l'événement à publier
sont écrits dans la même transaction, puis un relais publie vers Redis/WS V1).

Additif et réversible. Aucune FK vers `agent_runs` (livrée au lot P4) : `run_id`
est un uuid brut non contraint pour ne pas coupler l'ingest à une table absente.
FK `agent_id`/`installation_id` en RESTRICT : l'historique n'est jamais effacé
par suppression d'un agent/tenant (append-only, ADR/§7).

Revision ID: 0012_agent_events_outbox
Revises: 0011_agent_registry_credentials
Create Date: 2026-07-15
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_agent_events_outbox"
down_revision: str | None = "0011_agent_registry_credentials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("installation_id", sa.Uuid(), nullable=True),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("request_id", sa.String(length=255), nullable=True),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("trace_id", sa.String(length=120), nullable=True),
        sa.Column("client_version", sa.String(length=60), nullable=True),
        sa.ForeignKeyConstraint(["installation_id"], ["mc_installations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("agent_id", "event_id", name="uq_agent_events_agent_event"),
    )
    op.create_index("ix_agent_events_installation_id", "agent_events", ["installation_id"])
    op.create_index("ix_agent_events_agent_id", "agent_events", ["agent_id"])
    op.create_index(
        "ix_agent_events_installation_occurred", "agent_events", ["installation_id", "occurred_at"]
    )
    op.create_index("ix_agent_events_agent_sequence", "agent_events", ["agent_id", "sequence"])

    op.create_table(
        "mc_outbox_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("installation_id", sa.Uuid(), nullable=True),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("topic", sa.String(length=160), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["installation_id"], ["mc_installations.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_mc_outbox_events_installation_id", "mc_outbox_events", ["installation_id"])
    op.create_index("ix_mc_outbox_events_event_id", "mc_outbox_events", ["event_id"])
    op.create_index("ix_mc_outbox_status_created", "mc_outbox_events", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_mc_outbox_status_created", table_name="mc_outbox_events")
    op.drop_index("ix_mc_outbox_events_event_id", table_name="mc_outbox_events")
    op.drop_index("ix_mc_outbox_events_installation_id", table_name="mc_outbox_events")
    op.drop_table("mc_outbox_events")

    op.drop_index("ix_agent_events_agent_sequence", table_name="agent_events")
    op.drop_index("ix_agent_events_installation_occurred", table_name="agent_events")
    op.drop_index("ix_agent_events_agent_id", table_name="agent_events")
    op.drop_index("ix_agent_events_installation_id", table_name="agent_events")
    op.drop_table("agent_events")
