"""P6 (SP6) — coûts, budgets, alertes et audit : le plan opérationnel.

Gate P6 prouvé ici :

- **coûts réconciliables** : l'agrégat `/usage` égale la somme des
  `agent_usage_records` ; le coût est `Decimal` (jamais float), reproductible
  depuis usage + `pricing_version` ; rejouer un événement `usage.recorded` ne
  double pas la consommation (idempotence par `source_event_id`).
- **alertes dédupliquées** : franchir deux fois le même seuil budget n'ouvre
  qu'une alerte ; ACK/résolution opérables.
- **redaction** : un secret/token/mot de passe/Bearer n'apparaît jamais dans un
  log d'audit ni une alerte (payloads piégés).
- **audit append-only** : aucune route de mutation ; le trigger DB refuse
  UPDATE/DELETE.
- **franchissement de seuil budget** : `block_new_runs` bloque la commande
  (`budget_exceeded`), `require_approval` la retient (approbation), en
  s'articulant avec le moteur de policy P5.
- **isolation tenant** et **capacités** (`view_costs`/`operate`) fail-closed.
"""
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import DBAPIError

from apps.api.agent_control.operations import alerts as alerts_service
from apps.api.agent_control.operations import audit as audit_service
from apps.api.agent_control.operations import pricing
from apps.api.core.db import get_sessionmaker
from apps.api.core.security import generate_agent_credential
from apps.api.models import (
    LOCAL_INSTALLATION_ID,
    Agent,
    AgentAlert,
    AgentBudget,
    AgentCredential,
    AgentUsageRecord,
    MCAuditLog,
    MCInstallation,
)

CRED_HDR = "X-Agent-Credential"
_T0 = datetime(2026, 7, 15, 10, 0, 0, tzinfo=UTC)


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _ctx(db, email: str = "admin@mc.local"):
    from apps.api.core.agent_control_deps import _build_adapter
    from apps.api.models import User

    user = db.scalar(select(User).where(User.email == email))
    return _build_adapter(db).build_context(user, request_id=f"req-{uuid.uuid4().hex[:6]}")


def _make_agent_with_cred(db, *, tenant=LOCAL_INSTALLATION_ID, scopes=("ingest", "commands")):
    agent = Agent(agent_key=f"local:usage-{uuid.uuid4().hex[:8]}", installation_id=tenant)
    db.add(agent)
    db.commit()
    key_prefix, secret, secret_hash = generate_agent_credential()
    db.add(
        AgentCredential(
            agent_id=agent.id, key_prefix=key_prefix, secret_hash=secret_hash, scopes=list(scopes)
        )
    )
    db.commit()
    return agent, secret


def _usage_ev(agent_key, seq, *, input_tokens, output_tokens, provider="anthropic",
              model="claude-sonnet", run_id=None, project_id=None, event_id=None):
    ev = {
        "event_id": event_id or str(uuid.uuid4()),
        "agent_key": agent_key,
        "sequence": seq,
        "event_type": "usage.recorded",
        "occurred_at": _T0.isoformat().replace("+00:00", "Z"),
        "payload": {
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "calls": 1,
        },
    }
    if run_id:
        ev["run_id"] = str(run_id)
    if project_id:
        ev["project_id"] = str(project_id)
    return ev


def _ingest(client, secret, events):
    return client.post(
        "/agent-control/v1/ingest/events", json={"events": events}, headers={CRED_HDR: secret}
    )


# =============================================================================
# 1. Usage : enregistrement, Decimal, pricing_version, réconciliation, idempotence
# =============================================================================


def test_usage_cost_is_decimal_and_reproducible():
    """Coût calculé en Decimal, reproductible depuis usage + pricing_version."""
    b = pricing.compute_cost(input_tokens=1000, output_tokens=1000, provider="anthropic", model="claude-sonnet")
    assert isinstance(b.cost, Decimal)
    # 1000/1000*3 + 1000/1000*15 = 18
    assert b.cost == Decimal("18.00000000")
    assert b.pricing_version == pricing.CURRENT_PRICING_VERSION
    # Reproductible : même entrée, même version → même coût.
    again = pricing.compute_cost(input_tokens=1000, output_tokens=1000, provider="anthropic", model="claude-sonnet")
    assert again.cost == b.cost


def test_usage_ingested_and_reconciles(client, db, admin_token):
    """La somme des records == agrégat /usage exposé (réconciliation)."""
    agent, secret = _make_agent_with_cred(db)
    events = [
        _usage_ev(agent.agent_key, 1, input_tokens=1000, output_tokens=500),
        _usage_ev(agent.agent_key, 2, input_tokens=2000, output_tokens=1000),
    ]
    r = _ingest(client, secret, events)
    assert r.status_code == 200 and r.json()["accepted"] == 2

    # Somme DB des records de cet agent.
    total_db = db.scalar(
        select(func.coalesce(func.sum(AgentUsageRecord.cost), 0)).where(
            AgentUsageRecord.agent_id == agent.id
        )
    )
    # 1000/1000*3+500/1000*15 = 3+7.5 = 10.5 ; 2000/1000*3+1000/1000*15 = 6+15 = 21 ; total 31.5
    assert Decimal(total_db) == Decimal("31.50000000")

    # Agrégat exposé filtré sur l'agent == somme des items.
    resp = client.get(f"/agent-control/v1/usage?agent_id={agent.id}", headers=auth(admin_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    items_sum = sum(Decimal(i["cost"]) for i in body["items"])
    assert Decimal(body["summary"]["total_cost"]) == items_sum == Decimal("31.5")
    assert body["summary"]["record_count"] == 2


def test_usage_replay_is_idempotent_no_double_count(client, db, admin_token):
    """Rejouer le même event_id ne double jamais la consommation."""
    agent, secret = _make_agent_with_cred(db)
    eid = str(uuid.uuid4())
    ev = _usage_ev(agent.agent_key, 1, input_tokens=1000, output_tokens=0, event_id=eid)
    assert _ingest(client, secret, [ev]).status_code == 200
    # Rejeu du même event_id (nouvelle requête) → dédupliqué par l'ingest.
    replay = _ingest(client, secret, [ev])
    assert replay.status_code == 200 and replay.json()["duplicates"] == 1
    n = db.scalar(
        select(func.count()).select_from(AgentUsageRecord).where(AgentUsageRecord.agent_id == agent.id)
    )
    assert n == 1


def test_usage_requires_view_costs(client, db, viewer_token, pm_token):
    """/usage exige la capacité view_costs (viewer refusé, pm autorisé)."""
    assert client.get("/agent-control/v1/usage", headers=auth(viewer_token)).status_code == 403
    assert client.get("/agent-control/v1/usage", headers=auth(pm_token)).status_code == 200


# =============================================================================
# 2. Budgets : CRUD, capacité, verrou optimiste, consommation
# =============================================================================


def test_budget_create_requires_view_costs(client, viewer_token, admin_token):
    body = {"scope_type": "installation", "amount_limit": "100.00", "on_exceed": "alert"}
    assert client.post("/agent-control/v1/budgets", json=body, headers=auth(viewer_token)).status_code == 403
    r = client.post("/agent-control/v1/budgets", json=body, headers=auth(admin_token))
    assert r.status_code == 201, r.text
    assert r.json()["on_exceed"] == "alert" and r.json()["version"] == 1
    # `consumed` est recalculé depuis les usages (chaîne décimale) — présent au create.
    assert "consumed" in r.json() and isinstance(r.json()["consumed"], str)


def test_budget_invalid_on_exceed_rejected(client, admin_token):
    r = client.post(
        "/agent-control/v1/budgets",
        json={"amount_limit": "10", "on_exceed": "explode"},
        headers=auth(admin_token),
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_budget_update_optimistic_lock(client, admin_token):
    created = client.post(
        "/agent-control/v1/budgets",
        json={"amount_limit": "50", "on_exceed": "alert"},
        headers=auth(admin_token),
    ).json()
    bid = created["id"]
    ok = client.patch(
        f"/agent-control/v1/budgets/{bid}",
        json={"version": 1, "amount_limit": "80"},
        headers=auth(admin_token),
    )
    assert ok.status_code == 200 and Decimal(ok.json()["amount_limit"]) == Decimal("80")
    assert ok.json()["version"] == 2
    stale = client.patch(
        f"/agent-control/v1/budgets/{bid}",
        json={"version": 1, "amount_limit": "1"},
        headers=auth(admin_token),
    )
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "state_conflict"


# =============================================================================
# 3. Seuils budget → alertes dédupliquées
# =============================================================================


def _make_budget(db, *, tenant=LOCAL_INSTALLATION_ID, amount, on_exceed="alert",
                 scope_type="installation", scope_id=None, thresholds=None):
    budget = AgentBudget(
        installation_id=tenant,
        scope_type=scope_type,
        scope_id=scope_id,
        amount_limit=Decimal(amount),
        on_exceed=on_exceed,
        thresholds=thresholds or [50, 80, 100],
    )
    db.add(budget)
    db.commit()
    return budget


def test_threshold_crossing_dedups_alerts(client, db, admin_token):
    """Franchir deux fois le même seuil n'ouvre qu'une alerte (dédup)."""
    # Budget scopé à l'agent frais → consommation isolée (pas de fuite inter-tests).
    agent, secret = _make_agent_with_cred(db)
    budget = _make_budget(db, amount="100", scope_type="agent", scope_id=agent.id)
    # 1er usage : coût 60 → 60% (franchit 50).
    _ingest(client, secret, [_usage_ev(agent.agent_key, 1, input_tokens=20000, output_tokens=0)])
    # anthropic/claude-sonnet input 3/1k → 20000/1000*3 = 60.
    # 2e usage : +5 → 65% (toujours >50, pas >80) : PAS de nouvelle alerte @50.
    _ingest(client, secret, [_usage_ev(agent.agent_key, 2, input_tokens=1000, output_tokens=133)])
    # 1000/1000*3 + 133/1000*15 ≈ 3 + 1.995 = 4.995 → total ≈ 64.995 (<80)

    alerts = db.scalars(
        select(AgentAlert).where(
            AgentAlert.installation_id == LOCAL_INSTALLATION_ID,
            AgentAlert.dedup_key == f"budget:{budget.id}:threshold:50",
        )
    ).all()
    assert len(alerts) == 1  # une seule alerte pour ce seuil, malgré deux franchissements
    assert alerts[0].alert_type == "budget_threshold" and alerts[0].status == "open"

    # Exposée via l'API et acquittable.
    listed = client.get("/agent-control/v1/alerts", headers=auth(admin_token)).json()["items"]
    assert any(a["dedup_key"] == f"budget:{budget.id}:threshold:50" for a in listed)


def test_threshold_100_emits_budget_exceeded_event(client, db, admin_token):
    """Dépasser 100% ouvre une alerte critique + événement outbox budget.exceeded."""
    from apps.api.models import MCOutboxEvent

    agent, secret = _make_agent_with_cred(db)
    budget = _make_budget(db, amount="10", scope_type="agent", scope_id=agent.id)
    # coût 30 → 300%.
    _ingest(client, secret, [_usage_ev(agent.agent_key, 1, input_tokens=10000, output_tokens=0)])
    exceeded = db.scalar(
        select(AgentAlert).where(
            AgentAlert.dedup_key == f"budget:{budget.id}:threshold:100"
        )
    )
    assert exceeded is not None and exceeded.severity == "critical"
    # Événement outbox budget.exceeded posé (persistance avant publication).
    ob = db.scalar(
        select(func.count()).select_from(MCOutboxEvent).where(MCOutboxEvent.event_type == "budget.exceeded")
    )
    assert ob >= 1


# =============================================================================
# 4. Gate budget × policy : block_new_runs et require_approval
# =============================================================================


def _make_run(client, db, secret, agent_key):
    rid = uuid.uuid4()
    events = [
        {"event_id": str(uuid.uuid4()), "agent_key": agent_key, "sequence": 1,
         "event_type": "run.queued", "occurred_at": _T0.isoformat().replace("+00:00", "Z"),
         "payload": {}, "run_id": str(rid)},
        {"event_id": str(uuid.uuid4()), "agent_key": agent_key, "sequence": 2,
         "event_type": "run.starting", "occurred_at": _T0.isoformat().replace("+00:00", "Z"),
         "payload": {}, "run_id": str(rid)},
        {"event_id": str(uuid.uuid4()), "agent_key": agent_key, "sequence": 3,
         "event_type": "run.running", "occurred_at": _T0.isoformat().replace("+00:00", "Z"),
         "payload": {}, "run_id": str(rid)},
    ]
    assert _ingest(client, secret, events).status_code == 200
    return rid


def test_budget_block_new_runs_blocks_command(client, db, admin_token):
    """Budget dépassé (block_new_runs) → soumission de commande refusée (budget_exceeded)."""
    agent, secret = _make_agent_with_cred(db)
    _make_budget(db, amount="5", on_exceed="block_new_runs", scope_type="agent", scope_id=agent.id)
    rid = _make_run(client, db, secret, agent.agent_key)
    # Consommation 30 >> 5 (dépassé) sur cet agent.
    _ingest(client, secret, [_usage_ev(agent.agent_key, 10, input_tokens=10000, output_tokens=0)])

    r = client.post(
        f"/agent-control/v1/runs/{rid}/commands",
        json={"command_type": "noop"},
        headers=auth(admin_token),
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "budget_exceeded"


def test_budget_require_approval_holds_command(client, db, admin_token):
    """Budget dépassé (require_approval) → commande retenue même si policy=allow."""
    agent, secret = _make_agent_with_cred(db, scopes=("ingest", "commands"))
    _make_budget(db, amount="5", on_exceed="require_approval", scope_type="agent", scope_id=agent.id)
    rid = _make_run(client, db, secret, agent.agent_key)
    _ingest(client, secret, [_usage_ev(agent.agent_key, 10, input_tokens=10000, output_tokens=0)])

    r = client.post(
        f"/agent-control/v1/runs/{rid}/commands",
        json={"command_type": "noop"},
        headers=auth(admin_token),
    )
    assert r.status_code == 201, r.text
    cmd = r.json()
    # Retenue : approval_request_id posé, non libérée (released_at None).
    assert cmd["approval_request_id"] is not None
    assert cmd["released_at"] is None
    assert cmd["policy_effect"] == "require_approval"
    # L'agent ne la reçoit pas tant qu'elle n'est pas approuvée.
    polled = client.get("/agent-control/v1/agent/commands", headers={CRED_HDR: secret})
    assert polled.json()["items"] == []


def test_no_budget_means_no_gate(client, db, admin_token):
    """Sans budget, la soumission de commande n'est pas affectée (allow immédiat)."""
    agent, secret = _make_agent_with_cred(db)
    rid = _make_run(client, db, secret, agent.agent_key)
    r = client.post(
        f"/agent-control/v1/runs/{rid}/commands",
        json={"command_type": "noop"},
        headers=auth(admin_token),
    )
    assert r.status_code == 201 and r.json()["released_at"] is not None


# =============================================================================
# 5. Alertes : ACK / résolution, capacité, dédup après résolution
# =============================================================================


def test_alert_acknowledge_and_resolve(client, db, admin_token):
    agent, secret = _make_agent_with_cred(db)
    budget = _make_budget(db, amount="10", scope_type="agent", scope_id=agent.id)
    _ingest(client, secret, [_usage_ev(agent.agent_key, 1, input_tokens=10000, output_tokens=0)])
    alert = db.scalar(
        select(AgentAlert).where(AgentAlert.dedup_key == f"budget:{budget.id}:threshold:50")
    )
    aid = str(alert.id)
    ack = client.post(f"/agent-control/v1/alerts/{aid}/acknowledge", headers=auth(admin_token))
    assert ack.status_code == 200 and ack.json()["status"] == "acknowledged"
    res = client.post(f"/agent-control/v1/alerts/{aid}/resolve", headers=auth(admin_token))
    assert res.status_code == 200 and res.json()["status"] == "resolved"


def test_alert_ack_requires_operate(client, db, viewer_token):
    """Acquitter une alerte exige la capacité `operate` (viewer refusé)."""
    # Ouvre une alerte directement (service) pour tester la capacité d'ACK.
    alert, _ = alerts_service.open_alert(
        db, installation_id=LOCAL_INSTALLATION_ID, alert_type="budget_threshold",
        dedup_key=f"cap-{uuid.uuid4().hex[:8]}", title="x",
    )
    db.commit()
    r = client.post(f"/agent-control/v1/alerts/{alert.id}/acknowledge", headers=auth(viewer_token))
    assert r.status_code == 403 and r.json()["error"]["code"] == "permission_denied"


def test_alert_dedup_reopens_after_resolution(db):
    """Après résolution, la même condition peut rouvrir une NOUVELLE alerte."""
    ctx = _ctx(db)
    key = f"cond-{uuid.uuid4().hex[:8]}"
    a1, created1 = alerts_service.open_alert(
        db, installation_id=LOCAL_INSTALLATION_ID, alert_type="t", dedup_key=key, title="1"
    )
    db.commit()
    assert created1
    # Re-détection avant résolution → dédupliqué (même alerte).
    a2, created2 = alerts_service.open_alert(
        db, installation_id=LOCAL_INSTALLATION_ID, alert_type="t", dedup_key=key, title="2"
    )
    db.commit()
    assert not created2 and a2.id == a1.id
    # Résolution puis nouvelle détection → nouvelle alerte autorisée.
    alerts_service.resolve_alert(db, ctx, str(a1.id))
    a3, created3 = alerts_service.open_alert(
        db, installation_id=LOCAL_INSTALLATION_ID, alert_type="t", dedup_key=key, title="3"
    )
    db.commit()
    assert created3 and a3.id != a1.id


# =============================================================================
# 6. Audit : append-only (API + trigger DB) et redaction (payloads piégés)
# =============================================================================


def test_audit_written_on_command_submission(client, db, admin_token):
    agent, secret = _make_agent_with_cred(db)
    rid = _make_run(client, db, secret, agent.agent_key)
    client.post(
        f"/agent-control/v1/runs/{rid}/commands",
        json={"command_type": "auditme"},
        headers=auth(admin_token),
    )
    entry = db.scalar(
        select(MCAuditLog).where(MCAuditLog.action == "command.submitted")
        .order_by(MCAuditLog.created_at.desc())
    )
    assert entry is not None and entry.after["command_type"] == "auditme"
    # Exposé via l'API d'audit (lecture, capacité view).
    listed = client.get("/agent-control/v1/audit?action=command.submitted", headers=auth(admin_token))
    assert listed.status_code == 200 and len(listed.json()["items"]) >= 1


def test_audit_redacts_trapped_secrets(db):
    """Un secret/token/Bearer piégé n'atteint jamais le journal d'audit."""
    secret_value = "SEKRET-TOKEN-98765"
    entry = audit_service.write_audit(
        db,
        installation_id=LOCAL_INSTALLATION_ID,
        action="credential.created",
        actor_type="user",
        actor_id="tester",
        target_type="credential",
        target_id="cred-1",
        before={"password": secret_value, "api_key": f"ac_deadbeef.{secret_value}"},
        after={"note": f"Bearer {secret_value}", "nested": {"token": secret_value, "ok": "public"}},
        ip="203.0.113.7",
        metadata={"session": secret_value, "benign": "kept"},
    )
    db.commit()
    db.refresh(entry)
    blob = json.dumps([entry.before, entry.after, entry.audit_metadata])
    assert secret_value not in blob  # jamais en clair, sous aucune clé
    assert entry.before["password"] == "[redacted]"
    assert entry.after["nested"]["token"] == "[redacted]"
    assert entry.after["nested"]["ok"] == "public"  # champ anodin conservé
    assert entry.audit_metadata["benign"] == "kept"
    # IP jamais en clair : uniquement son empreinte.
    assert entry.ip_hash is not None and entry.ip_hash != "203.0.113.7" and len(entry.ip_hash) == 64


def test_alert_details_are_redacted(db):
    """Les détails d'alerte sont redacted (opérable sans exposer de secret)."""
    secret_value = "ALERT-SECRET-4242"
    alert, _ = alerts_service.open_alert(
        db,
        installation_id=LOCAL_INSTALLATION_ID,
        alert_type="budget_threshold",
        dedup_key=f"redact-{uuid.uuid4().hex[:8]}",
        title="seuil",
        details={"api_token": secret_value, "threshold": 80, "note": f"Bearer {secret_value}"},
    )
    db.commit()
    db.refresh(alert)
    blob = json.dumps(alert.details)
    assert secret_value not in blob
    assert alert.details["api_token"] == "[redacted]"
    assert alert.details["threshold"] == 80


def test_audit_append_only_no_update_via_db(db):
    """Le trigger DB refuse tout UPDATE d'une ligne d'audit (append-only)."""
    entry = audit_service.write_audit(
        db, installation_id=LOCAL_INSTALLATION_ID, action="budget.updated", target_id="b1"
    )
    db.commit()
    Session = get_sessionmaker()
    with Session() as s:
        with pytest.raises(DBAPIError):
            s.execute(update(MCAuditLog).where(MCAuditLog.id == entry.id).values(action="tampered"))
            s.commit()
        s.rollback()
    # La ligne est intacte.
    db.expire_all()
    fresh = db.get(MCAuditLog, entry.id)
    assert fresh.action == "budget.updated"


def test_audit_append_only_no_delete_via_db(db):
    """Le trigger DB refuse tout DELETE d'une ligne d'audit (append-only)."""
    entry = audit_service.write_audit(
        db, installation_id=LOCAL_INSTALLATION_ID, action="policy.evaluated", target_id="p1"
    )
    db.commit()
    Session = get_sessionmaker()
    with Session() as s:
        with pytest.raises(DBAPIError):
            s.execute(delete(MCAuditLog).where(MCAuditLog.id == entry.id))
            s.commit()
        s.rollback()
    db.expire_all()
    assert db.get(MCAuditLog, entry.id) is not None


def test_audit_no_mutation_route_exists(client, admin_token):
    """Aucune route de mutation d'audit (append-only côté API)."""
    fake = uuid.uuid4()
    assert client.delete(f"/agent-control/v1/audit/{fake}", headers=auth(admin_token)).status_code in (404, 405)
    assert client.patch(f"/agent-control/v1/audit/{fake}", json={}, headers=auth(admin_token)).status_code in (404, 405)


# =============================================================================
# 7. Isolation tenant (fail-closed)
# =============================================================================


def _tenant_b(db):
    inst_b = MCInstallation(
        external_tenant_id="tenant-b-p6",
        installation_key=f"tb6-{uuid.uuid4().hex[:6]}",
        status="active",
    )
    db.add(inst_b)
    db.commit()
    return inst_b


def test_cross_tenant_usage_and_budget_not_visible(client, db, admin_token):
    """Usages/budgets/alertes d'un autre tenant invisibles pour l'admin local."""
    inst_b = _tenant_b(db)
    agent_b = Agent(agent_key=f"tb6:{uuid.uuid4().hex[:8]}", installation_id=inst_b.id)
    db.add(agent_b)
    db.commit()
    db.add(
        AgentUsageRecord(
            installation_id=inst_b.id, agent_id=agent_b.id, source_event_id="b-1",
            occurred_at=_T0, cost=Decimal("999"), pricing_version="x", total_tokens=1,
        )
    )
    budget_b = AgentBudget(installation_id=inst_b.id, amount_limit=Decimal("1"), on_exceed="alert")
    db.add(budget_b)
    db.commit()

    # /usage local : ne compte jamais le tenant B.
    summary = client.get("/agent-control/v1/usage", headers=auth(admin_token)).json()["summary"]
    assert Decimal(summary["total_cost"]) < Decimal("999")
    # /budgets local : le budget B n'apparaît pas.
    budgets = client.get("/agent-control/v1/budgets", headers=auth(admin_token)).json()["items"]
    assert all(b["id"] != str(budget_b.id) for b in budgets)
    # Accès direct au budget B → 404 (pas de fuite d'existence).
    assert client.patch(
        f"/agent-control/v1/budgets/{budget_b.id}", json={"version": 1, "amount_limit": "2"},
        headers=auth(admin_token),
    ).status_code == 404
