"""SP4 — ingest V1 : credentials, idempotence, séquence, outbox, heartbeat (P3).

Gate P3 : un credential révoqué est refusé immédiatement et ne peut jamais agir
pour un autre agent/tenant ; l'ingest V1 est idempotent (rejeu = 0 doublon, une
séquence ancienne rejetée) ; persistance avant publication (outbox), jamais de
publish direct dans la requête.
"""
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from apps.api.core.security import generate_agent_credential
from apps.api.models import (
    LOCAL_INSTALLATION_ID,
    Agent,
    AgentCredential,
    AgentEvent,
    MCOutboxEvent,
)

HDR = "X-Agent-Credential"
_NOW = "2026-07-15T10:00:00Z"


def _make_agent_with_cred(
    db, *, scopes=("ingest",), key=None, tenant=LOCAL_INSTALLATION_ID, **cred_kw
):
    agent = Agent(agent_key=key or f"local:ing-{uuid.uuid4().hex[:8]}", installation_id=tenant)
    db.add(agent)
    db.commit()
    key_prefix, secret, secret_hash = generate_agent_credential()
    cred = AgentCredential(
        agent_id=agent.id,
        key_prefix=key_prefix,
        secret_hash=secret_hash,
        scopes=list(scopes),
        expires_at=cred_kw.get("expires_at"),
        revoked_at=cred_kw.get("revoked_at"),
    )
    db.add(cred)
    db.commit()
    return agent, secret


def _event(agent_key, seq, *, event_id=None, event_type="agent.heartbeat", **kw):
    return {
        "event_id": event_id or str(uuid.uuid4()),
        "agent_key": agent_key,
        "sequence": seq,
        "event_type": event_type,
        "occurred_at": _NOW,
        "payload": kw.get("payload", {}),
        **{k: v for k, v in kw.items() if k != "payload"},
    }


# --- Authentification par credential (fail-closed) ---------------------------

def test_missing_credential_is_401_v1_envelope(client, db):
    agent, _ = _make_agent_with_cred(db)
    r = client.post("/agent-control/v1/ingest/events", json={"events": []})
    assert r.status_code == 401
    body = r.json()
    assert body["error"]["code"] == "credential_invalid"  # enveloppe V1, pas {"detail"}
    assert "detail" not in body


def test_malformed_credential_is_401(client, db):
    r = client.post(
        "/agent-control/v1/ingest/events", json={"events": []},
        headers={HDR: "no-separator"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "credential_invalid"


def test_unknown_prefix_is_401(client, db):
    r = client.post(
        "/agent-control/v1/ingest/events", json={"events": []},
        headers={HDR: "ac_deadbeef.whatever"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "credential_invalid"


def test_tampered_secret_is_401(client, db):
    agent, secret = _make_agent_with_cred(db)
    prefix = secret.split(".", 1)[0]
    r = client.post(
        "/agent-control/v1/ingest/events", json={"events": []},
        headers={HDR: f"{prefix}.tampered-secret-value"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "credential_invalid"


def test_valid_credential_empty_batch_ok(client, db):
    agent, secret = _make_agent_with_cred(db)
    r = client.post(
        "/agent-control/v1/ingest/events", json={"events": []}, headers={HDR: secret}
    )
    assert r.status_code == 200
    assert r.json() == {"accepted": 0, "duplicates": 0, "rejected": 0, "last_sequence": 0}


# --- Gate P3 : credential révoqué refusé immédiatement -----------------------

def test_revoked_credential_refused_immediately(client, db):
    agent, secret = _make_agent_with_cred(db, revoked_at=datetime.now(UTC))
    r = client.post(
        "/agent-control/v1/ingest/events",
        json={"events": [_event(agent.agent_key, 1)]},
        headers={HDR: secret},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "credential_revoked"
    # Aucun événement écrit malgré un batch valide.
    assert db.scalar(select(func.count()).select_from(AgentEvent).where(AgentEvent.agent_id == agent.id)) == 0


def test_expired_credential_refused(client, db):
    agent, secret = _make_agent_with_cred(
        db, expires_at=datetime.now(UTC) - timedelta(seconds=1)
    )
    r = client.post(
        "/agent-control/v1/ingest/heartbeat",
        json={"agent_key": agent.agent_key, "state": "working"},
        headers={HDR: secret},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "credential_revoked"


def test_insufficient_scope_refused(client, db):
    agent, secret = _make_agent_with_cred(db, scopes=["commands"])  # pas "ingest"
    r = client.post(
        "/agent-control/v1/ingest/events",
        json={"events": [_event(agent.agent_key, 1)]},
        headers={HDR: secret},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "permission_denied"


# --- Gate P3 : jamais d'action cross-agent -----------------------------------

def test_credential_cannot_act_for_another_agent(client, db):
    agent_a, secret_a = _make_agent_with_cred(db)
    agent_b, _ = _make_agent_with_cred(db)
    # Credential A tente de publier un événement portant l'agent_key de B.
    r = client.post(
        "/agent-control/v1/ingest/events",
        json={"events": [_event(agent_b.agent_key, 1)]},
        headers={HDR: secret_a},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "permission_denied"
    # Rien n'est écrit ni pour A ni pour B.
    assert db.scalar(select(func.count()).select_from(AgentEvent).where(AgentEvent.agent_id == agent_b.id)) == 0
    assert db.scalar(select(func.count()).select_from(AgentEvent).where(AgentEvent.agent_id == agent_a.id)) == 0


def test_revoked_credential_cannot_act_for_another_agent(client, db):
    # Combinaison explicite du Gate : révoqué ET cross-agent → refus.
    agent_a, secret_a = _make_agent_with_cred(db, revoked_at=datetime.now(UTC))
    agent_b, _ = _make_agent_with_cred(db)
    r = client.post(
        "/agent-control/v1/ingest/events",
        json={"events": [_event(agent_b.agent_key, 1)]},
        headers={HDR: secret_a},
    )
    assert r.status_code == 403
    # La révocation prime (vérifiée avant même l'agent_key du body).
    assert r.json()["error"]["code"] == "credential_revoked"


# --- Idempotence et séquence -------------------------------------------------

def test_batch_accepted_then_replay_is_idempotent(client, db):
    agent, secret = _make_agent_with_cred(db)
    e1 = _event(agent.agent_key, 1)
    e2 = _event(agent.agent_key, 2)
    r1 = client.post(
        "/agent-control/v1/ingest/events", json={"events": [e1, e2]}, headers={HDR: secret}
    )
    assert r1.json() == {"accepted": 2, "duplicates": 0, "rejected": 0, "last_sequence": 2}
    # Rejeu du MÊME batch → aucun doublon, tout en duplicates.
    r2 = client.post(
        "/agent-control/v1/ingest/events", json={"events": [e1, e2]}, headers={HDR: secret}
    )
    assert r2.json() == {"accepted": 0, "duplicates": 2, "rejected": 0, "last_sequence": 2}
    # Exactement 2 lignes persistées.
    count = db.scalar(select(func.count()).select_from(AgentEvent).where(AgentEvent.agent_id == agent.id))
    assert count == 2


def test_old_sequence_rejected(client, db):
    agent, secret = _make_agent_with_cred(db)
    client.post(
        "/agent-control/v1/ingest/events",
        json={"events": [_event(agent.agent_key, 5)]},
        headers={HDR: secret},
    )
    # Nouvel event_id mais séquence ancienne → rejeté (sequence_out_of_order).
    r = client.post(
        "/agent-control/v1/ingest/events",
        json={"events": [_event(agent.agent_key, 3)]},
        headers={HDR: secret},
    )
    assert r.json() == {"accepted": 0, "duplicates": 0, "rejected": 1, "last_sequence": 5}


def test_sequence_advances_monotonically(client, db):
    agent, secret = _make_agent_with_cred(db)
    client.post(
        "/agent-control/v1/ingest/events",
        json={"events": [_event(agent.agent_key, 5)]},
        headers={HDR: secret},
    )
    r = client.post(
        "/agent-control/v1/ingest/events",
        json={"events": [_event(agent.agent_key, 6)]},
        headers={HDR: secret},
    )
    assert r.json()["accepted"] == 1
    assert r.json()["last_sequence"] == 6


def test_partial_invalid_batch(client, db):
    agent, secret = _make_agent_with_cred(db)
    good = _event(agent.agent_key, 1, event_type="run.step.completed")
    bad = _event(agent.agent_key, 2, event_type="totally.unknown.type")
    r = client.post(
        "/agent-control/v1/ingest/events", json={"events": [good, bad]}, headers={HDR: secret}
    )
    body = r.json()
    assert body["accepted"] == 1 and body["rejected"] == 1
    assert body["last_sequence"] == 1


def test_batch_too_large_is_422(client, db, monkeypatch):
    from apps.api.agent_control.ingest import service as svc

    monkeypatch.setattr(svc.settings, "mc_event_batch_max", 1)
    agent, secret = _make_agent_with_cred(db)
    r = client.post(
        "/agent-control/v1/ingest/events",
        json={"events": [_event(agent.agent_key, 1), _event(agent.agent_key, 2)]},
        headers={HDR: secret},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


# --- Outbox : persistance avant publication ----------------------------------

def test_accepted_events_write_outbox_pending(client, db):
    agent, secret = _make_agent_with_cred(db)
    ev = _event(agent.agent_key, 1, event_type="run.step.completed", run_id=str(uuid.uuid4()))
    client.post("/agent-control/v1/ingest/events", json={"events": [ev]}, headers={HDR: secret})
    outbox = db.scalars(
        select(MCOutboxEvent).where(MCOutboxEvent.event_id == ev["event_id"])
    ).all()
    assert len(outbox) == 1
    row = outbox[0]
    assert row.status == "pending"  # jamais publié en synchrone dans la requête
    assert row.topic.startswith("run:")
    assert row.installation_id == LOCAL_INSTALLATION_ID


# --- Heartbeat V1 : projection monotone --------------------------------------

def test_heartbeat_v1_updates_projection(client, db):
    agent, secret = _make_agent_with_cred(db)
    r = client.post(
        "/agent-control/v1/ingest/heartbeat",
        json={"agent_key": agent.agent_key, "state": "working", "task": "t", "progress": 40, "sequence": 10},
        headers={HDR: secret},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["applied"] is True
    assert body["state"] == "working"
    assert body["last_sequence"] == 10
    db.refresh(agent)
    assert agent.state.value == "working" and agent.progress == 40


def test_heartbeat_v1_stale_does_not_regress(client, db):
    agent, secret = _make_agent_with_cred(db)
    client.post(
        "/agent-control/v1/ingest/heartbeat",
        json={"agent_key": agent.agent_key, "state": "working", "sequence": 10},
        headers={HDR: secret},
    )
    # Heartbeat ancien (sequence 5 < 10) avec un état différent → ignoré.
    r = client.post(
        "/agent-control/v1/ingest/heartbeat",
        json={"agent_key": agent.agent_key, "state": "idle", "sequence": 5},
        headers={HDR: secret},
    )
    assert r.json()["applied"] is False
    db.refresh(agent)
    assert agent.state.value == "working"  # pas de régression
    assert agent.last_sequence == 10


def test_heartbeat_v1_agent_key_mismatch_refused(client, db):
    agent, secret = _make_agent_with_cred(db)
    r = client.post(
        "/agent-control/v1/ingest/heartbeat",
        json={"agent_key": "local:someone-else", "state": "working"},
        headers={HDR: secret},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "permission_denied"


def test_heartbeat_v1_stale_state_rejected(client, db):
    agent, secret = _make_agent_with_cred(db)
    r = client.post(
        "/agent-control/v1/ingest/heartbeat",
        json={"agent_key": agent.agent_key, "state": "stale"},
        headers={HDR: secret},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_heartbeat_v1_invalid_state_rejected(client, db):
    agent, secret = _make_agent_with_cred(db)
    r = client.post(
        "/agent-control/v1/ingest/heartbeat",
        json={"agent_key": agent.agent_key, "state": "flying"},
        headers={HDR: secret},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


# --- Compatibilité Contract D (V0 inchangé) ----------------------------------

def test_v0_heartbeat_still_works_alongside_v1(client, db):
    # Le heartbeat V0 (secret global partagé) reste strictement fonctionnel.
    r = client.post(
        "/agents/heartbeat",
        headers={"X-MC-Token": "test-ingest"},
        json={"agent": "v0-coexist", "state": "working", "task": "x", "progress": 5},
    )
    assert r.status_code == 202
    assert r.json()["agent"] == "v0-coexist"
