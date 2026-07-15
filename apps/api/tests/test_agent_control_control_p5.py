"""P5 (SP3) — commandes, approbations et politiques : le contrôle humain.

Gate P5 prouvé ici :

- **policy allow/deny/require_approval** : une politique `deny` bloque la création
  de la commande (403, aucune commande) ; `require_approval` retient la commande
  `queued` non livrable avec `approval_request_id` ; `allow` (ou défaut) la libère.
- **aucune commande risquée livrée sans décision valide** : tant qu'une approbation
  est `pending`, l'agent ne reçoit pas la commande ; après `approve`, il la reçoit ;
  après `reject`, elle est annulée.
- **pas de double décision** : verrou optimiste (`version`) — une seconde décision
  concurrente/périmée est refusée (`state_conflict`), au niveau HTTP ET au niveau DB.
- **idempotence** : rejouer une soumission ne crée pas de doublon.
- **isolation tenant** : approbations/politiques d'un autre tenant invisibles (404).
"""
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from apps.api.agent_control.control import commands as commands_service
from apps.api.core.db import get_sessionmaker
from apps.api.core.security import generate_agent_credential
from apps.api.integrations.errors import StateConflict
from apps.api.integrations.state_machines import CommandState
from apps.api.models import (
    LOCAL_INSTALLATION_ID,
    Agent,
    AgentCommand,
    AgentCredential,
    AgentPolicy,
    AgentRun,
    ApprovalRequest,
    MCInstallation,
)

CRED_HDR = "X-Agent-Credential"
_T0 = datetime(2026, 7, 15, 10, 0, 0, tzinfo=UTC)


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_agent_with_cred(db, *, tenant=LOCAL_INSTALLATION_ID, scopes=("ingest", "commands")):
    agent = Agent(agent_key=f"local:cmd-{uuid.uuid4().hex[:8]}", installation_id=tenant)
    db.add(agent)
    db.commit()
    key_prefix, secret, secret_hash = generate_agent_credential()
    db.add(
        AgentCredential(
            agent_id=agent.id,
            key_prefix=key_prefix,
            secret_hash=secret_hash,
            scopes=list(scopes),
        )
    )
    db.commit()
    return agent, secret


def _ev(agent_key, seq, event_type, *, run_id, occurred=None, payload=None, **top):
    return {
        "event_id": str(uuid.uuid4()),
        "agent_key": agent_key,
        "sequence": seq,
        "event_type": event_type,
        "occurred_at": (occurred or _T0).isoformat().replace("+00:00", "Z"),
        "payload": payload or {},
        "run_id": str(run_id),
        **top,
    }


def _make_run(client, db, secret, agent_key, *, project_id=None):
    """Crée un run running via ingest et renvoie son id."""
    rid = uuid.uuid4()
    events = [
        _ev(agent_key, 1, "run.queued", run_id=rid, **({"project_id": str(project_id)} if project_id else {})),
        _ev(agent_key, 2, "run.starting", run_id=rid),
        _ev(agent_key, 3, "run.running", run_id=rid),
    ]
    r = client.post(
        "/agent-control/v1/ingest/events", json={"events": events}, headers={CRED_HDR: secret}
    )
    assert r.status_code == 200, r.text
    return rid


def _submit(client, token, run_id, **body):
    body.setdefault("command_type", "shell.exec")
    return client.post(
        f"/agent-control/v1/runs/{run_id}/commands", json=body, headers=auth(token)
    )


def _poll(client, secret, **params):
    return client.get(
        "/agent-control/v1/agent/commands", params=params, headers={CRED_HDR: secret}
    )


# =============================================================================
# 1. Politiques : CRUD, rôles fail-closed, verrou optimiste
# =============================================================================


def test_policy_create_requires_admin(client, viewer_token, pm_token, admin_token):
    body = {"scope_type": "installation", "action_type": "shell.exec", "effect": "deny"}
    assert client.post("/agent-control/v1/policies", json=body, headers=auth(viewer_token)).status_code == 403
    assert client.post("/agent-control/v1/policies", json=body, headers=auth(pm_token)).status_code == 403
    r = client.post("/agent-control/v1/policies", json=body, headers=auth(admin_token))
    assert r.status_code == 201, r.text
    assert r.json()["effect"] == "deny" and r.json()["version"] == 1


def test_policy_invalid_effect_rejected(client, admin_token):
    r = client.post(
        "/agent-control/v1/policies",
        json={"effect": "maybe"},
        headers=auth(admin_token),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_policy_project_scope_requires_scope_id(client, admin_token):
    r = client.post(
        "/agent-control/v1/policies",
        json={"scope_type": "project", "effect": "deny"},
        headers=auth(admin_token),
    )
    assert r.status_code == 422


def test_policy_update_optimistic_lock(client, admin_token):
    created = client.post(
        "/agent-control/v1/policies",
        json={"effect": "allow", "action_type": "shell.exec"},
        headers=auth(admin_token),
    ).json()
    pid = created["id"]
    # Bonne version → succès, version incrémentée.
    ok = client.patch(
        f"/agent-control/v1/policies/{pid}",
        json={"version": 1, "priority": 500},
        headers=auth(admin_token),
    )
    assert ok.status_code == 200 and ok.json()["priority"] == 500 and ok.json()["version"] == 2
    # Version périmée → 409 (édition concurrente).
    stale = client.patch(
        f"/agent-control/v1/policies/{pid}",
        json={"version": 1, "priority": 1},
        headers=auth(admin_token),
    )
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "state_conflict"


def test_policy_delete_disables(client, admin_token):
    created = client.post(
        "/agent-control/v1/policies",
        json={"effect": "deny", "action_type": "x"},
        headers=auth(admin_token),
    ).json()
    pid = created["id"]
    assert client.delete(f"/agent-control/v1/policies/{pid}", headers=auth(admin_token)).status_code == 204
    # Disparaît de la liste (status disabled, jamais évaluée).
    listed = client.get("/agent-control/v1/policies", headers=auth(admin_token)).json()
    ids = [p["id"] for p in listed["items"] if p["status"] == "active"]
    assert pid not in ids


# =============================================================================
# 2. Soumission de commande : allow / deny / require_approval
# =============================================================================


def test_command_allow_full_lifecycle(client, db, admin_token):
    """allow (défaut) : livrée immédiatement, ACK puis résultat."""
    agent, secret = _make_agent_with_cred(db)
    rid = _make_run(client, db, secret, agent.agent_key)

    r = _submit(client, admin_token, rid, command_type="noop", payload={"x": 1})
    assert r.status_code == 201, r.text
    cmd = r.json()
    assert cmd["status"] == "queued" and cmd["approval_request_id"] is None
    assert cmd["policy_effect"] == "allow" and cmd["released_at"] is not None
    cid = cmd["id"]

    # L'agent récupère la commande (queued → delivered).
    polled = _poll(client, secret).json()["items"]
    assert [c["id"] for c in polled] == [cid]
    assert polled[0]["status"] == "delivered"

    # ACK puis résultat.
    ack = client.post(f"/agent-control/v1/agent/commands/{cid}/ack", headers={CRED_HDR: secret})
    assert ack.status_code == 200 and ack.json()["status"] == "acknowledged"
    res = client.post(
        f"/agent-control/v1/agent/commands/{cid}/result",
        json={"status": "success", "result_payload": {"ok": True}},
        headers={CRED_HDR: secret},
    )
    assert res.status_code == 200 and res.json()["status"] == "succeeded"
    assert res.json()["result_status"] == "success"


def test_command_deny_blocks_creation(client, db, admin_token):
    """deny : la commande n'est jamais créée (403), l'agent ne reçoit rien."""
    agent, secret = _make_agent_with_cred(db)
    rid = _make_run(client, db, secret, agent.agent_key)
    client.post(
        "/agent-control/v1/policies",
        json={"scope_type": "agent", "scope_id": str(agent.id), "action_type": "rm.rf", "effect": "deny"},
        headers=auth(admin_token),
    )
    r = _submit(client, admin_token, rid, command_type="rm.rf")
    assert r.status_code == 403 and r.json()["error"]["code"] == "permission_denied"
    # Aucune commande matérialisée pour cet agent.
    n = db.scalar(select(func.count()).select_from(AgentCommand).where(AgentCommand.agent_id == agent.id))
    assert n == 0
    assert _poll(client, secret).json()["items"] == []


def test_command_require_approval_held_until_decision(client, db, admin_token):
    """require_approval : commande retenue queued+approval, NON livrée sans décision."""
    agent, secret = _make_agent_with_cred(db)
    rid = _make_run(client, db, secret, agent.agent_key)
    client.post(
        "/agent-control/v1/policies",
        json={"action_type": "deploy.prod", "effect": "require_approval", "risk_level": "high"},
        headers=auth(admin_token),
    )
    r = _submit(client, admin_token, rid, command_type="deploy.prod")
    assert r.status_code == 201, r.text
    cmd = r.json()
    assert cmd["status"] == "queued"
    assert cmd["approval_request_id"] is not None
    assert cmd["released_at"] is None
    assert cmd["policy_effect"] == "require_approval" and cmd["risk_level"] == "high"

    # GATE : l'agent ne reçoit PAS la commande tant que pas de décision positive.
    assert _poll(client, secret).json()["items"] == []

    # L'approbation est bien en attente et listée.
    approvals = client.get("/agent-control/v1/approvals", headers=auth(admin_token)).json()["items"]
    ap = next(a for a in approvals if a["id"] == cmd["approval_request_id"])
    assert ap["status"] == "pending" and ap["risk_level"] == "high"


def test_command_released_after_approval(client, db, admin_token):
    """Après approbation valide, la commande devient livrable à l'agent."""
    agent, secret = _make_agent_with_cred(db)
    rid = _make_run(client, db, secret, agent.agent_key)
    client.post(
        "/agent-control/v1/policies",
        json={"action_type": "deploy.prod", "effect": "require_approval"},
        headers=auth(admin_token),
    )
    cmd = _submit(client, admin_token, rid, command_type="deploy.prod").json()
    aid = cmd["approval_request_id"]

    # Toujours rien livré avant décision.
    assert _poll(client, secret).json()["items"] == []

    ap = client.get(f"/agent-control/v1/approvals/{aid}", headers=auth(admin_token)).json()
    decided = client.post(
        f"/agent-control/v1/approvals/{aid}/approve",
        json={"version": ap["version"], "comment": "ok go"},
        headers=auth(admin_token),
    )
    assert decided.status_code == 200 and decided.json()["status"] == "approved"

    # Désormais livrable.
    polled = _poll(client, secret).json()["items"]
    assert [c["id"] for c in polled] == [cmd["id"]]
    assert polled[0]["status"] == "delivered"


def test_command_cancelled_after_rejection(client, db, admin_token):
    """Après rejet, la commande est annulée et jamais livrée."""
    agent, secret = _make_agent_with_cred(db)
    rid = _make_run(client, db, secret, agent.agent_key)
    client.post(
        "/agent-control/v1/policies",
        json={"action_type": "deploy.prod", "effect": "require_approval"},
        headers=auth(admin_token),
    )
    cmd = _submit(client, admin_token, rid, command_type="deploy.prod").json()
    aid = cmd["approval_request_id"]
    ap = client.get(f"/agent-control/v1/approvals/{aid}", headers=auth(admin_token)).json()
    rej = client.post(
        f"/agent-control/v1/approvals/{aid}/reject",
        json={"version": ap["version"]},
        headers=auth(admin_token),
    )
    assert rej.status_code == 200 and rej.json()["status"] == "rejected"
    # Commande annulée, agent ne reçoit rien.
    got = client.get("/agent-control/v1/approvals", headers=auth(admin_token))
    assert got.status_code == 200
    fresh = db.get(AgentCommand, uuid.UUID(cmd["id"]))
    db.refresh(fresh)
    assert fresh.status == "cancelled"
    assert _poll(client, secret).json()["items"] == []


def test_policy_priority_resolution_deny_wins(client, db, admin_token):
    """Résolution déterministe : la politique de plus haute priorité l'emporte."""
    agent, secret = _make_agent_with_cred(db)
    rid = _make_run(client, db, secret, agent.agent_key)
    # allow large (priorité basse) vs deny ciblé (priorité haute) → deny gagne.
    client.post(
        "/agent-control/v1/policies",
        json={"action_type": "*", "effect": "allow", "priority": 10},
        headers=auth(admin_token),
    )
    client.post(
        "/agent-control/v1/policies",
        json={"action_type": "danger", "effect": "deny", "priority": 900},
        headers=auth(admin_token),
    )
    assert _submit(client, admin_token, rid, command_type="danger").status_code == 403
    assert _submit(client, admin_token, rid, command_type="safe").status_code == 201


# =============================================================================
# 3. Pas de double décision (verrou optimiste)
# =============================================================================


def test_no_double_decision_http(client, db, admin_token):
    """HTTP : deux décisions avec la même version → la seconde est refusée (409)."""
    agent, secret = _make_agent_with_cred(db)
    rid = _make_run(client, db, secret, agent.agent_key)
    client.post(
        "/agent-control/v1/policies",
        json={"action_type": "twice", "effect": "require_approval"},
        headers=auth(admin_token),
    )
    cmd = _submit(client, admin_token, rid, command_type="twice").json()
    aid = cmd["approval_request_id"]

    first = client.post(
        f"/agent-control/v1/approvals/{aid}/approve", json={"version": 1}, headers=auth(admin_token)
    )
    assert first.status_code == 200 and first.json()["status"] == "approved"
    # Deuxième décision (rejet) avec la version périmée → refus.
    second = client.post(
        f"/agent-control/v1/approvals/{aid}/reject", json={"version": 1}, headers=auth(admin_token)
    )
    assert second.status_code == 409 and second.json()["error"]["code"] == "state_conflict"
    # La décision positive tient : la commande reste libérée (non annulée).
    fresh = db.get(AgentCommand, uuid.UUID(cmd["id"]))
    db.refresh(fresh)
    assert fresh.status == "queued" and fresh.released_at is not None


def test_no_double_decision_concurrent_db(db):
    """DB : deux sessions lisant version=1 → un seul UPDATE conditionnel gagne."""
    # Approbation pending v1 posée directement.
    aid = uuid.uuid4()
    agent = Agent(agent_key=f"local:conc-{uuid.uuid4().hex[:6]}", installation_id=LOCAL_INSTALLATION_ID)
    db.add(agent)
    db.commit()
    db.add(
        ApprovalRequest(
            id=aid,
            installation_id=LOCAL_INSTALLATION_ID,
            agent_id=agent.id,
            action_type="race",
            title="race",
            status="pending",
            version=1,
        )
    )
    db.commit()

    Session = get_sessionmaker()

    def _conditional_approve(session, expected_version, target):
        res = session.execute(
            update(ApprovalRequest)
            .where(
                ApprovalRequest.id == aid,
                ApprovalRequest.status == "pending",
                ApprovalRequest.version == expected_version,
            )
            .values(status=target, version=ApprovalRequest.version + 1)
            .execution_options(synchronize_session=False)
        )
        session.commit()
        return res.rowcount

    with Session() as s1, Session() as s2:
        # Les deux "lisent" v1 (pending), puis tentent de décider concurremment.
        r1 = _conditional_approve(s1, 1, "approved")
        r2 = _conditional_approve(s2, 1, "rejected")
    assert {r1, r2} == {1, 0}  # exactement une décision appliquée
    db.expire_all()
    final = db.get(ApprovalRequest, aid)
    assert final.status == "approved" and final.version == 2


def test_approve_expired_is_refused(client, db, admin_token):
    """Une approbation dont le SLA est dépassé ne peut plus être décidée (fail-closed)."""
    agent, secret = _make_agent_with_cred(db)
    rid = _make_run(client, db, secret, agent.agent_key)
    client.post(
        "/agent-control/v1/policies",
        json={"action_type": "slow", "effect": "require_approval"},
        headers=auth(admin_token),
    )
    cmd = _submit(client, admin_token, rid, command_type="slow").json()
    aid = uuid.UUID(cmd["approval_request_id"])
    # Force l'expiration.
    db.execute(
        update(ApprovalRequest)
        .where(ApprovalRequest.id == aid)
        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    db.commit()
    r = client.post(
        f"/agent-control/v1/approvals/{aid}/approve", json={"version": 1}, headers=auth(admin_token)
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "state_conflict"
    # Commande annulée (jamais libérée).
    fresh = db.get(AgentCommand, uuid.UUID(cmd["id"]))
    db.refresh(fresh)
    assert fresh.status == "cancelled" and fresh.released_at is None


# =============================================================================
# 4. Idempotence, expiration, machine d'état, scope agent
# =============================================================================


def test_command_idempotent_submission(client, db, admin_token):
    agent, secret = _make_agent_with_cred(db)
    rid = _make_run(client, db, secret, agent.agent_key)
    key = f"idem-{uuid.uuid4().hex[:8]}"
    first = _submit(client, admin_token, rid, command_type="noop", idempotency_key=key)
    assert first.status_code == 201
    second = _submit(client, admin_token, rid, command_type="noop", idempotency_key=key)
    assert second.status_code == 200  # rejeu idempotent
    assert first.json()["id"] == second.json()["id"]
    n = db.scalar(
        select(func.count()).select_from(AgentCommand).where(AgentCommand.idempotency_key == key)
    )
    assert n == 1


def test_command_expires_before_delivery(client, db, admin_token):
    agent, secret = _make_agent_with_cred(db)
    rid = _make_run(client, db, secret, agent.agent_key)
    cmd = _submit(client, admin_token, rid, command_type="noop").json()
    cid = uuid.UUID(cmd["id"])
    # Force le TTL dans le passé.
    db.execute(
        update(AgentCommand).where(AgentCommand.id == cid).values(
            expires_at=datetime.now(UTC) - timedelta(seconds=1)
        )
    )
    db.commit()
    # Le poll ne la livre pas et la marque expirée.
    assert _poll(client, secret).json()["items"] == []
    fresh = db.get(AgentCommand, cid)
    db.refresh(fresh)
    assert fresh.status == "expired"


def test_command_ack_requires_delivered(client, db, admin_token):
    """Machine d'état : acquitter une commande non livrée est refusé (409)."""
    agent, secret = _make_agent_with_cred(db)
    rid = _make_run(client, db, secret, agent.agent_key)
    cmd = _submit(client, admin_token, rid, command_type="noop").json()
    # queued (pas encore delivered) → ack interdit.
    r = client.post(
        f"/agent-control/v1/agent/commands/{cmd['id']}/ack", headers={CRED_HDR: secret}
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "state_conflict"


def test_agent_commands_requires_commands_scope(client, db, admin_token):
    """Un credential sans scope `commands` ne peut pas récupérer la file."""
    agent, secret = _make_agent_with_cred(db, scopes=("ingest",))
    r = _poll(client, secret)
    assert r.status_code == 403 and r.json()["error"]["code"] == "permission_denied"


def test_operator_cancel_command(client, db, admin_token):
    """Annulation opérateur (service) : queued → cancelled."""
    agent, secret = _make_agent_with_cred(db)
    rid = _make_run(client, db, secret, agent.agent_key)
    cmd = _submit(client, admin_token, rid, command_type="noop").json()

    from apps.api.core.agent_control_deps import _build_adapter
    from apps.api.models import User

    admin = db.scalar(select(User).where(User.email == "admin@mc.local"))
    ctx = _build_adapter(db).build_context(admin, request_id="req-cancel")
    cancelled = commands_service.cancel_command(db, ctx, cmd["id"])
    assert cancelled.status == "cancelled"
    assert _poll(client, secret).json()["items"] == []


# =============================================================================
# 5. Capacités et isolation tenant (fail-closed)
# =============================================================================


def test_submit_command_requires_operate(client, db, viewer_token, pm_token):
    agent, secret = _make_agent_with_cred(db)
    rid = _make_run(client, db, secret, agent.agent_key)
    assert _submit(client, viewer_token, rid, command_type="noop").status_code == 403  # pas operate
    assert _submit(client, pm_token, rid, command_type="noop").status_code == 201       # operate


def test_approve_requires_approve_capability(client, db, admin_token, viewer_token):
    agent, secret = _make_agent_with_cred(db)
    rid = _make_run(client, db, secret, agent.agent_key)
    client.post(
        "/agent-control/v1/policies",
        json={"action_type": "cap", "effect": "require_approval"},
        headers=auth(admin_token),
    )
    cmd = _submit(client, admin_token, rid, command_type="cap").json()
    aid = cmd["approval_request_id"]
    # viewer n'a pas la capacité approve.
    r = client.post(
        f"/agent-control/v1/approvals/{aid}/approve", json={"version": 1}, headers=auth(viewer_token)
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "permission_denied"


def test_commands_require_jwt(client):
    r = client.post(f"/agent-control/v1/runs/{uuid.uuid4()}/commands", json={"command_type": "x"})
    assert r.status_code == 401


def _tenant_b(db):
    inst_b = MCInstallation(
        external_tenant_id="tenant-b-p5",
        installation_key=f"tb5-{uuid.uuid4().hex[:6]}",
        status="active",
    )
    db.add(inst_b)
    db.commit()
    agent_b = Agent(agent_key=f"tb5:{uuid.uuid4().hex[:8]}", installation_id=inst_b.id)
    db.add(agent_b)
    db.commit()
    return inst_b, agent_b


def test_cross_tenant_approval_not_visible(client, db, admin_token):
    inst_b, agent_b = _tenant_b(db)
    ap_b = ApprovalRequest(
        installation_id=inst_b.id,
        agent_id=agent_b.id,
        action_type="x",
        title="B",
        status="pending",
        version=1,
    )
    db.add(ap_b)
    db.commit()
    # Non listée pour l'admin local.
    listed = client.get("/agent-control/v1/approvals", headers=auth(admin_token)).json()["items"]
    assert all(a["id"] != str(ap_b.id) for a in listed)
    # Accès direct → 404 (pas de fuite d'existence).
    assert client.get(f"/agent-control/v1/approvals/{ap_b.id}", headers=auth(admin_token)).status_code == 404
    # Décision cross-tenant → 404.
    dec = client.post(
        f"/agent-control/v1/approvals/{ap_b.id}/approve", json={"version": 1}, headers=auth(admin_token)
    )
    assert dec.status_code == 404


def test_cross_tenant_policy_not_listed(client, db, admin_token):
    inst_b, _ = _tenant_b(db)
    pol_b = AgentPolicy(installation_id=inst_b.id, effect="deny", action_type="secret")
    db.add(pol_b)
    db.commit()
    listed = client.get("/agent-control/v1/policies", headers=auth(admin_token)).json()["items"]
    assert all(p["id"] != str(pol_b.id) for p in listed)


def test_cross_tenant_command_not_delivered_to_other_agent(client, db, admin_token):
    """Une commande d'un agent B n'est jamais livrée à un agent local (isolation)."""
    inst_b, agent_b = _tenant_b(db)
    run_b = AgentRun(id=uuid.uuid4(), installation_id=inst_b.id, agent_id=agent_b.id, state="running", version=1)
    db.add(run_b)
    db.commit()
    db.add(
        AgentCommand(
            installation_id=inst_b.id,
            agent_id=agent_b.id,
            run_id=run_b.id,
            command_type="noop",
            status="queued",
            idempotency_key=f"b-{uuid.uuid4().hex[:8]}",
            released_at=datetime.now(UTC),
        )
    )
    db.commit()
    # Un agent local ne reçoit pas la commande du tenant B.
    agent_local, secret_local = _make_agent_with_cred(db)
    assert _poll(client, secret_local).json()["items"] == []


def test_evaluate_policy_is_audited(client, db, admin_token):
    """La décision de policy est tracée (ActivityLog policy.evaluated)."""
    from apps.api.models import ActivityLog

    agent, secret = _make_agent_with_cred(db)
    rid = _make_run(client, db, secret, agent.agent_key)
    _submit(client, admin_token, rid, command_type="audited")
    log = db.scalar(
        select(ActivityLog)
        .where(ActivityLog.agent_id == agent.id, ActivityLog.type == "policy.evaluated")
        .order_by(ActivityLog.created_at.desc())
    )
    assert log is not None
    assert log.payload["command_type"] == "audited"
    assert log.payload["effect"] in ("allow", "deny", "require_approval")


def test_transition_command_unit():
    """Transitions unitaires de la machine `command` (serveur autoritaire)."""
    cmd = AgentCommand(
        id=uuid.uuid4(), agent_id=uuid.uuid4(), command_type="x", status="queued",
        idempotency_key="k", version=1,
    )
    commands_service.transition_command(cmd, CommandState.delivered, at=_T0)
    assert cmd.status == "delivered" and cmd.delivered_at == _T0 and cmd.version == 2
    commands_service.transition_command(cmd, CommandState.acknowledged, at=_T0)
    assert cmd.status == "acknowledged"
    # queued → succeeded direct interdit depuis acknowledged? succeeded est permis.
    commands_service.transition_command(cmd, CommandState.succeeded, at=_T0)
    assert cmd.status == "succeeded"
    # Terminal : plus aucune transition.
    with pytest.raises(StateConflict):
        commands_service.transition_command(cmd, CommandState.failed, at=_T0)
