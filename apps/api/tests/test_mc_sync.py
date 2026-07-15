"""Sync des statuts fichiers .mission-control/status → table `agents` (mc_sync.py)."""
import json

from sqlalchemy import select

from apps.api.core.config import settings
from apps.api.models import Agent, AgentState
from apps.api.services.mc_sync import AGENT_SOURCE_MC_FILE, sync_once


def _write_status(dir_, agent_key, **fields):
    payload = {"agent": agent_key, "state": "working", **fields}
    (dir_ / f"{agent_key}.json").write_text(json.dumps(payload))


def test_sync_once_tags_synced_agents_with_mc_file_source(db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "mc_status_dir", str(tmp_path))
    _write_status(tmp_path, "file-agent-tag")
    try:
        assert sync_once(db) == 1
        agent = db.scalar(select(Agent).where(Agent.agent_key == "file-agent-tag"))
        assert agent.meta.get("source") == AGENT_SOURCE_MC_FILE
    finally:
        agent = db.scalar(select(Agent).where(Agent.agent_key == "file-agent-tag"))
        if agent:
            db.delete(agent)
            db.commit()


def test_sync_once_purges_mc_file_agent_whose_status_file_disappeared(db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "mc_status_dir", str(tmp_path))
    _write_status(tmp_path, "file-agent-gone")
    try:
        sync_once(db)
        assert db.scalar(select(Agent).where(Agent.agent_key == "file-agent-gone")) is not None

        (tmp_path / "file-agent-gone.json").unlink()
        sync_once(db)
        assert db.scalar(select(Agent).where(Agent.agent_key == "file-agent-gone")) is None
    finally:
        agent = db.scalar(select(Agent).where(Agent.agent_key == "file-agent-gone"))
        if agent:
            db.delete(agent)
            db.commit()


def test_sync_once_never_purges_heartbeat_sourced_agent(db, tmp_path, monkeypatch):
    """Un agent DB-natif (créé par POST /agents/heartbeat, donc sans meta.source) ne doit
    jamais être supprimé par sync_once(), même si son agent_key n'apparaît dans aucun
    fichier `mc` — seule la provenance `mc-file` explicite déclenche la purge."""
    agent = Agent(agent_key="hb-agent-untouched", state=AgentState.working)
    db.add(agent)
    db.commit()

    monkeypatch.setattr(settings, "mc_status_dir", str(tmp_path))  # dossier vide
    try:
        sync_once(db)
        assert db.scalar(select(Agent).where(Agent.agent_key == "hb-agent-untouched")) is not None
    finally:
        agent = db.scalar(select(Agent).where(Agent.agent_key == "hb-agent-untouched"))
        if agent:
            db.delete(agent)
            db.commit()
