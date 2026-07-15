"""P4 (SP3) — plan de contrôle des runs : transitions, projection, timeline, tenant.

Gate P4 : un run complet est reconstituable et auditable depuis la DB (état,
étapes, horodatage, timeline via `agent_events`) ; les états terminaux sont
immuables (une transition depuis un état terminal est refusée) ; un retry crée un
NOUVEAU run lié à l'original, il ne rouvre jamais l'ancien. Isolation tenant :
un run d'un autre tenant n'est ni listé ni lisible (404, pas de fuite).

Les runs se créent par **projection des événements d'ingest** (`run.*`/`run.step.*`,
agent authentifié par credential) — le contrat V1 figé n'expose aucun `POST /runs`.
"""
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from apps.api.agent_control.runs import service as runs_service
from apps.api.core.security import generate_agent_credential
from apps.api.integrations.errors import StateConflict
from apps.api.integrations.state_machines import RunState
from apps.api.models import (
    LOCAL_INSTALLATION_ID,
    Agent,
    AgentCredential,
    AgentProjectAssignment,
    AgentRun,
    AgentRunStep,
    MCInstallation,
    Project,
)

CRED_HDR = "X-Agent-Credential"
_T0 = datetime(2026, 7, 15, 10, 0, 0, tzinfo=UTC)


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_agent_with_cred(db, *, tenant=LOCAL_INSTALLATION_ID, key=None):
    agent = Agent(agent_key=key or f"local:run-{uuid.uuid4().hex[:8]}", installation_id=tenant)
    db.add(agent)
    db.commit()
    key_prefix, secret, secret_hash = generate_agent_credential()
    db.add(
        AgentCredential(
            agent_id=agent.id, key_prefix=key_prefix, secret_hash=secret_hash, scopes=["ingest"]
        )
    )
    db.commit()
    return agent, secret


def _ev(agent_key, seq, event_type, *, run_id=None, occurred=None, payload=None, **top):
    return {
        "event_id": str(uuid.uuid4()),
        "agent_key": agent_key,
        "sequence": seq,
        "event_type": event_type,
        "occurred_at": (occurred or _T0).isoformat().replace("+00:00", "Z"),
        "payload": payload or {},
        **({"run_id": str(run_id)} if run_id else {}),
        **top,
    }


def _ingest(client, secret, events):
    r = client.post(
        "/agent-control/v1/ingest/events",
        json={"events": events},
        headers={CRED_HDR: secret},
    )
    assert r.status_code == 200, r.text
    return r.json()


# --- Transitions serveur-autoritatives (unitaire, machine `run` figée) --------


def _run(state=RunState.queued):
    return AgentRun(id=uuid.uuid4(), agent_id=uuid.uuid4(), state=state.value, version=1, attempt=1)


def test_transition_valid_path_sets_timestamps_and_version():
    run = _run(RunState.queued)
    runs_service.transition_run(run, RunState.starting, at=_T0)
    assert run.state == "starting" and run.started_at == _T0 and run.version == 2
    runs_service.transition_run(run, RunState.running, at=_T0)
    assert run.state == "running"
    runs_service.transition_run(run, RunState.succeeded, at=_T0 + timedelta(seconds=5))
    assert run.state == "succeeded"
    assert run.finished_at == _T0 + timedelta(seconds=5) and run.version == 4


def test_transition_invalid_is_refused():
    run = _run(RunState.queued)
    # queued ne peut aller directement à running (seulement starting|cancelled|timed_out).
    with pytest.raises(StateConflict):
        runs_service.transition_run(run, RunState.running, at=_T0)
    assert run.state == "queued" and run.version == 1  # inchangé


def test_terminal_state_is_immutable():
    run = _run(RunState.succeeded)
    with pytest.raises(StateConflict):
        runs_service.transition_run(run, RunState.running, at=_T0)
    assert run.state == "succeeded"


def test_transition_to_same_state_is_noop():
    run = _run(RunState.running)
    runs_service.transition_run(run, RunState.running, at=_T0)
    assert run.state == "running" and run.version == 1  # pas de bump


# --- Projection depuis l'ingest + lecture (intégration HTTP) ------------------


def test_run_created_and_readable_from_db(client, db, admin_token):
    agent, secret = _make_agent_with_cred(db)
    rid = uuid.uuid4()
    _ingest(
        client,
        secret,
        [
            _ev(agent.agent_key, 1, "run.queued", run_id=rid, payload={"objective": "build"}),
            _ev(agent.agent_key, 2, "run.starting", run_id=rid),
            _ev(agent.agent_key, 3, "run.running", run_id=rid),
        ],
    )
    r = client.get(f"/agent-control/v1/runs/{rid}", headers=auth(admin_token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "running"
    assert body["objective"] == "build"
    assert body["started_at"] is not None
    assert body["agent_id"] == str(agent.id)

    lst = client.get("/agent-control/v1/runs", headers=auth(admin_token)).json()
    assert any(item["id"] == str(rid) for item in lst["items"])


def test_full_lifecycle_with_steps_and_timeline(client, db, admin_token):
    agent, secret = _make_agent_with_cred(db)
    rid = uuid.uuid4()
    t = _T0
    _ingest(
        client,
        secret,
        [
            _ev(agent.agent_key, 1, "run.queued", run_id=rid, occurred=t),
            _ev(agent.agent_key, 2, "run.starting", run_id=rid, occurred=t + timedelta(seconds=1)),
            _ev(agent.agent_key, 3, "run.running", run_id=rid, occurred=t + timedelta(seconds=2)),
            _ev(
                agent.agent_key, 4, "run.step.started", run_id=rid,
                occurred=t + timedelta(seconds=3),
                payload={"step_sequence": 1, "name": "lint", "tool_name": "ruff"},
            ),
            _ev(
                agent.agent_key, 5, "run.step.completed", run_id=rid,
                occurred=t + timedelta(seconds=5),
                payload={"step_sequence": 1, "output_summary": "ok"},
            ),
            _ev(
                agent.agent_key, 6, "run.succeeded", run_id=rid,
                occurred=t + timedelta(seconds=6),
                payload={"result_summary": "done"},
            ),
        ],
    )
    detail = client.get(f"/agent-control/v1/runs/{rid}", headers=auth(admin_token)).json()
    assert detail["state"] == "succeeded"
    assert detail["result_summary"] == "done"
    assert detail["finished_at"] is not None
    assert len(detail["steps"]) == 1
    step = detail["steps"][0]
    assert step["sequence"] == 1 and step["state"] == "succeeded"
    assert step["tool_name"] == "ruff" and step["output_summary"] == "ok"
    assert step["duration_ms"] == 2000  # 5s - 3s

    tl = client.get(f"/agent-control/v1/runs/{rid}/timeline", headers=auth(admin_token)).json()
    types = [e["event_type"] for e in tl["items"]]
    assert types == [
        "run.queued", "run.starting", "run.running",
        "run.step.started", "run.step.completed", "run.succeeded",
    ]
    # Séquences strictement croissantes → timeline ordonnée reconstituable.
    seqs = [e["sequence"] for e in tl["items"]]
    assert seqs == sorted(seqs)


def test_terminal_run_immutable_via_ingest(client, db, admin_token):
    agent, secret = _make_agent_with_cred(db)
    rid = uuid.uuid4()
    _ingest(
        client,
        secret,
        [
            _ev(agent.agent_key, 1, "run.queued", run_id=rid),
            _ev(agent.agent_key, 2, "run.starting", run_id=rid),
            _ev(agent.agent_key, 3, "run.running", run_id=rid),
            _ev(agent.agent_key, 4, "run.failed", run_id=rid, payload={"error_code": "boom"}),
        ],
    )
    # Un événement qui prétend rouvrir le run terminal est journalisé mais NON appliqué.
    _ingest(client, secret, [_ev(agent.agent_key, 5, "run.running", run_id=rid)])
    body = client.get(f"/agent-control/v1/runs/{rid}", headers=auth(admin_token)).json()
    assert body["state"] == "failed"  # inchangé
    assert body["error_code"] == "boom"
    # L'événement de tentative reste bien dans la timeline (audit).
    tl = client.get(f"/agent-control/v1/runs/{rid}/timeline", headers=auth(admin_token)).json()
    assert tl["items"][-1]["event_type"] == "run.running"
    assert tl["items"][-1]["sequence"] == 5


def test_retry_creates_new_linked_run(client, db, admin_token):
    agent, secret = _make_agent_with_cred(db)
    r1 = uuid.uuid4()
    _ingest(
        client,
        secret,
        [
            _ev(agent.agent_key, 1, "run.queued", run_id=r1),
            _ev(agent.agent_key, 2, "run.starting", run_id=r1),
            _ev(agent.agent_key, 3, "run.running", run_id=r1),
            _ev(agent.agent_key, 4, "run.failed", run_id=r1),
        ],
    )
    r2 = uuid.uuid4()
    _ingest(
        client,
        secret,
        [_ev(agent.agent_key, 5, "run.queued", run_id=r2, payload={"retry_of": str(r1)})],
    )
    new = client.get(f"/agent-control/v1/runs/{r2}", headers=auth(admin_token)).json()
    assert new["retry_of_run_id"] == str(r1)
    assert new["attempt"] == 2
    assert new["state"] == "queued"
    # L'original reste terminal et intact (jamais rouvert).
    old = client.get(f"/agent-control/v1/runs/{r1}", headers=auth(admin_token)).json()
    assert old["state"] == "failed"


def test_step_idempotent_on_run_sequence(client, db, admin_token):
    agent, secret = _make_agent_with_cred(db)
    rid = uuid.uuid4()
    _ingest(
        client,
        secret,
        [
            _ev(agent.agent_key, 1, "run.queued", run_id=rid),
            _ev(agent.agent_key, 2, "run.starting", run_id=rid),
            _ev(agent.agent_key, 3, "run.running", run_id=rid),
            _ev(
                agent.agent_key, 4, "run.step.started", run_id=rid, occurred=_T0,
                payload={"step_sequence": 7, "name": "test"},
            ),
            _ev(
                agent.agent_key, 5, "run.step.completed", run_id=rid,
                occurred=_T0 + timedelta(seconds=3), payload={"step_sequence": 7},
            ),
        ],
    )
    # Une seule étape (run_id, sequence=7), passée à succeeded.
    count = db.scalar(
        select(func.count()).select_from(AgentRunStep).where(AgentRunStep.run_id == rid)
    )
    assert count == 1
    step = db.scalar(select(AgentRunStep).where(AgentRunStep.run_id == rid))
    assert step.sequence == 7 and step.state == "succeeded" and step.duration_ms == 3000


def test_assignment_created_once_for_project(client, db, admin_token):
    agent, secret = _make_agent_with_cred(db)
    proj = Project(slug=f"p-{uuid.uuid4().hex[:8]}", name="P4 proj")
    db.add(proj)
    db.commit()
    r1, r2 = uuid.uuid4(), uuid.uuid4()
    _ingest(client, secret, [_ev(agent.agent_key, 1, "run.queued", run_id=r1, project_id=str(proj.id))])
    _ingest(client, secret, [_ev(agent.agent_key, 2, "run.queued", run_id=r2, project_id=str(proj.id))])
    # Deux runs sur le même projet → une seule affectation ACTIVE (unique active).
    n = db.scalar(
        select(func.count())
        .select_from(AgentProjectAssignment)
        .where(
            AgentProjectAssignment.agent_id == agent.id,
            AgentProjectAssignment.project_id == proj.id,
            AgentProjectAssignment.status == "active",
        )
    )
    assert n == 1


def test_timeline_redacts_sensitive_keys(client, db, admin_token):
    agent, secret = _make_agent_with_cred(db)
    rid = uuid.uuid4()
    _ingest(
        client,
        secret,
        [
            _ev(
                agent.agent_key, 1, "run.queued", run_id=rid,
                payload={"objective": "x", "secret_token": "abc", "prompt": "raw text"},
            ),
        ],
    )
    tl = client.get(f"/agent-control/v1/runs/{rid}/timeline", headers=auth(admin_token)).json()
    payload = tl["items"][0]["payload"]
    assert payload["objective"] == "x"
    assert payload["secret_token"] == "[redacted]"
    assert payload["prompt"] == "[redacted]"


# --- Isolation tenant + fail-closed -------------------------------------------


def test_runs_require_jwt(client):
    r = client.get("/agent-control/v1/runs")
    assert r.status_code == 401


def test_cross_tenant_run_not_visible(client, db, admin_token):
    # Run dans un tenant B (installation distincte) — invisible pour l'admin local.
    inst_b = MCInstallation(
        external_tenant_id="tenant-b-runs",
        installation_key=f"tb-{uuid.uuid4().hex[:6]}",
        status="active",
    )
    db.add(inst_b)
    db.commit()
    agent_b = Agent(agent_key=f"tb:{uuid.uuid4().hex[:8]}", installation_id=inst_b.id)
    db.add(agent_b)
    db.commit()
    rid_b = uuid.uuid4()
    db.add(
        AgentRun(
            id=rid_b, installation_id=inst_b.id, agent_id=agent_b.id, state="running", version=1
        )
    )
    db.commit()

    # L'admin local (tenant `local`) ne voit pas le run du tenant B.
    lst = client.get("/agent-control/v1/runs", headers=auth(admin_token)).json()
    assert all(item["id"] != str(rid_b) for item in lst["items"])
    # Accès direct → 404 (pas de fuite d'existence, pas de 403 distinct).
    r = client.get(f"/agent-control/v1/runs/{rid_b}", headers=auth(admin_token))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
    tl = client.get(f"/agent-control/v1/runs/{rid_b}/timeline", headers=auth(admin_token))
    assert tl.status_code == 404
