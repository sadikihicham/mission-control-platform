"""DTO publics des runs V1 (P4, SP3).

Formes de sortie exposées aux routes `/agent-control/v1/runs*`. N'exposent
jamais le tenant interne (`installation_id`) ni de prompt/secret brut. Les
résumés (`*_summary`) sont déjà bornés côté service.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from apps.api.integrations.envelopes import PageInfo


class RunStepOut(BaseModel):
    """Étape / tool call d'un run (résumés uniquement, pas de brut)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sequence: int
    step_type: str
    name: str | None = None
    state: str
    tool_name: str | None = None
    input_summary: str | None = None
    output_summary: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None


class RunOut(BaseModel):
    """Run borné (état serveur-autoritatif). Sans `installation_id` (tenant interne)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    agent_id: uuid.UUID
    external_run_key: str | None = None
    objective: str | None = None
    state: str
    retry_of_run_id: uuid.UUID | None = None
    attempt: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    heartbeat_at: datetime | None = None
    result_summary: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime


class RunDetailOut(RunOut):
    """Run + ses étapes (timeline structurelle interne au run)."""

    steps: list[RunStepOut] = []


class RunListOut(BaseModel):
    """Liste paginée de runs (curseur opaque, ordre récence décroissante)."""

    items: list[RunOut]
    page_info: PageInfo


class TimelineEntryOut(BaseModel):
    """Entrée de timeline d'audit (événement journalisé, payload redacted)."""

    event_id: str
    event_type: str
    sequence: int
    occurred_at: datetime
    payload: dict = {}


class RunTimelineOut(BaseModel):
    """Timeline paginée d'un run reconstituée depuis `agent_events` (redacted)."""

    run_id: uuid.UUID
    items: list[TimelineEntryOut]
    page_info: PageInfo
