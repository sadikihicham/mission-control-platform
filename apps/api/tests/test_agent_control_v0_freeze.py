"""Gel des formes V0 réellement servies (Contrats C, D, E) — Gate P0.

Ces tests échouent dès qu'un champ existant disparaît d'une forme V0 ou qu'une
dérive de nommage gelée change. Ils NE prescrivent pas la « bonne » forme : ils
figent la forme RÉELLE d'aujourd'hui pour empêcher toute rupture accidentelle
pendant la construction d'Agent Control V1. Voir la table des dérives dans
`.mission-control/CONTRACTS_AGENT_CONTROL_V1.md` §2.
"""
from apps.api.core.redis import EVENTS_CHANNEL
from apps.api.routers.auth import MeOut
from apps.api.schemas.agent import ActivityOut, AgentOut, DashboardStats
from apps.api.schemas.heartbeat import AgentDTO, HeartbeatIn
from apps.api.schemas.project import ProjectDetail, ProjectSummary
from apps.api.tests.conftest import auth


def _fields(model) -> set[str]:
    return set(model.model_fields.keys())


# --- Gel par introspection des schémas (aucun champ ne doit disparaître) ------

def test_freeze_agent_out_fields():
    # Contract C — DTO REST agent servi au frontend (lib/api.ts `Agent`).
    assert _fields(AgentOut) == {
        "agent", "state", "task", "module", "label", "branch", "blocker",
        "progress", "tasks_done", "tasks_total", "updated_at", "age_seconds",
        "token_issued_at",
    }


def test_freeze_agent_dto_fields():
    # Contract E — objet Agent diffusé en temps réel (agent.update).
    assert _fields(AgentDTO) == {
        "agent_key", "state", "task", "progress", "module", "branch",
        "blocker", "project_id", "last_heartbeat",
    }


def test_freeze_naming_drift_http_vs_ws():
    # Dérive gelée : REST expose `agent`+`updated_at`, WS/ingest `agent_key`+`last_heartbeat`.
    http_fields = _fields(AgentOut)
    ws_fields = _fields(AgentDTO)
    assert "agent" in http_fields and "updated_at" in http_fields
    assert "agent_key" in ws_fields and "last_heartbeat" in ws_fields
    # Les noms ne se croisent jamais : aucune fusion accidentelle.
    assert "agent_key" not in http_fields and "last_heartbeat" not in http_fields
    assert "agent" not in ws_fields and "updated_at" not in ws_fields


def test_freeze_heartbeat_in_fields():
    # Contract D — corps d'ingest, aligné sur le JSON `mc`.
    assert _fields(HeartbeatIn) == {
        "agent", "state", "project", "task", "progress", "tasks_done",
        "tasks_total", "module", "branch", "blocker", "meta",
    }


def test_freeze_dashboard_stats_is_seven_kpis():
    # État réel = 7 KPI (AGENTS.md en décrit 5, périmé — dérive documentée).
    assert _fields(DashboardStats) == {
        "agents_total", "agents_active", "agents_blocked", "agents_stale",
        "agents_done", "agents_error", "overall_progress",
    }


def test_freeze_project_summary_and_detail_fields():
    assert _fields(ProjectSummary) == {
        "id", "name", "description", "status", "progress", "tasks_total",
        "tasks_done", "agents_total", "agents_active", "agents_blocked",
        "editable", "repo",
    }
    assert {"tasks", "agents"} <= _fields(ProjectDetail)


def test_freeze_activity_and_me_fields():
    assert _fields(ActivityOut) == {"type", "state", "task", "progress", "created_at"}
    assert _fields(MeOut) == {"id", "email", "role", "full_name", "civility", "is_active"}


def test_freeze_events_channel_name():
    # Le canal Redis V0 reste `mc:events` ; V1 utilisera un canal distinct.
    assert EVENTS_CHANNEL == "mc:events"


# --- Gel par appel réel (les champs sont bien sérialisés par l'API) -----------

def test_live_heartbeat_response_shape(client):
    r = client.post(
        "/agents/heartbeat",
        headers={"X-MC-Token": "test-ingest"},
        json={"agent": "freeze-agent", "state": "working", "task": "t", "progress": 10},
    )
    assert r.status_code == 202
    body = r.json()
    assert set(body.keys()) >= {"ok", "agent", "state"}
    assert body["agent"] == "freeze-agent"


def test_live_heartbeat_error_keeps_v0_detail_shape(client):
    # Invariant : les erreurs V0 gardent `{"detail": ...}` (jamais l'enveloppe V1).
    r = client.post(
        "/agents/heartbeat",
        headers={"X-MC-Token": "WRONG"},
        json={"agent": "x", "state": "idle"},
    )
    assert r.status_code == 403
    body = r.json()
    assert "detail" in body and "error" not in body


def test_live_agents_item_has_all_frozen_fields(client, admin_token):
    client.post(
        "/agents/heartbeat",
        headers={"X-MC-Token": "test-ingest"},
        json={"agent": "freeze-agent-2", "state": "idle"},
    )
    agents = client.get("/agents", headers=auth(admin_token)).json()
    assert agents, "au moins un agent attendu"
    for item in agents:
        assert _fields(AgentOut) <= set(item.keys())


def test_live_dashboard_has_exactly_seven_kpis(client, admin_token):
    stats = client.get("/stats/dashboard", headers=auth(admin_token)).json()
    assert set(stats.keys()) == {
        "agents_total", "agents_active", "agents_blocked", "agents_stale",
        "agents_done", "agents_error", "overall_progress",
    }


def test_live_me_shape(client, admin_token):
    me = client.get("/auth/me", headers=auth(admin_token)).json()
    assert set(me.keys()) == {"id", "email", "role", "full_name", "civility", "is_active"}
