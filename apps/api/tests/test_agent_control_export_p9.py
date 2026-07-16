"""P9 — export CSV des coûts (`GET /reports/export.csv`).

Ferme le gap assumé au Gate P7 : la route figurait dans la matrice
capacités×routes (§8, `view_costs`) mais n'était pas implémentée. Ce module
prouve :

- l'export réel, streamé (`text/csv`), en-tête + lignes, coût en chaîne décimale ;
- la **réconciliation** : la somme des coûts exportés == agrégat `/usage` ;
- la capacité `view_costs` fail-closed (viewer refusé, pm autorisé) ;
- l'**isolation tenant** : les consommations d'un autre tenant n'apparaissent
  jamais dans l'export du tenant courant (ADR-0003) ;
- les filtres (`agent_id`) identiques à `/usage`.
"""
import csv
import io
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from apps.api.core.security import generate_agent_credential
from apps.api.models import (
    LOCAL_INSTALLATION_ID,
    Agent,
    AgentCredential,
    AgentUsageRecord,
    MCInstallation,
)

CRED_HDR = "X-Agent-Credential"
_T0 = datetime(2026, 7, 15, 10, 0, 0, tzinfo=UTC)


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_agent_with_cred(db, *, tenant=LOCAL_INSTALLATION_ID):
    agent = Agent(agent_key=f"local:exp-{uuid.uuid4().hex[:8]}", installation_id=tenant)
    db.add(agent)
    db.commit()
    key_prefix, secret, secret_hash = generate_agent_credential()
    db.add(
        AgentCredential(
            agent_id=agent.id,
            key_prefix=key_prefix,
            secret_hash=secret_hash,
            scopes=["ingest", "commands"],
        )
    )
    db.commit()
    return agent, secret


def _usage_ev(agent_key, seq, *, input_tokens, output_tokens):
    return {
        "event_id": str(uuid.uuid4()),
        "agent_key": agent_key,
        "sequence": seq,
        "event_type": "usage.recorded",
        "occurred_at": _T0.isoformat(),
        "payload": {
            "provider": "anthropic",
            "model": "claude-sonnet",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "calls": 1,
        },
    }


def _ingest(client, secret, events):
    return client.post(
        "/agent-control/v1/ingest/events",
        json={"events": events},
        headers={CRED_HDR: secret},
    )


def _parse_csv(text: str) -> tuple[list[str], list[dict]]:
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    return reader.fieldnames or [], rows


def test_export_csv_streams_and_reconciles(client, db, admin_token):
    """L'export renvoie un CSV réel dont la somme des coûts == agrégat /usage."""
    agent, secret = _make_agent_with_cred(db)
    events = [
        _usage_ev(agent.agent_key, 1, input_tokens=1000, output_tokens=500),
        _usage_ev(agent.agent_key, 2, input_tokens=2000, output_tokens=1000),
    ]
    assert _ingest(client, secret, events).json()["accepted"] == 2

    resp = client.get(
        f"/agent-control/v1/reports/export.csv?agent_id={agent.id}", headers=auth(admin_token)
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers.get("content-disposition", "")

    header, rows = _parse_csv(resp.text)
    assert "cost" in header and "occurred_at" in header and "usage_id" in header
    assert len(rows) == 2
    # Coût en chaîne décimale (jamais float) et réconciliable avec /usage.
    export_sum = sum(Decimal(r["cost"]) for r in rows)
    usage = client.get(
        f"/agent-control/v1/usage?agent_id={agent.id}", headers=auth(admin_token)
    ).json()
    assert export_sum == Decimal(usage["summary"]["total_cost"]) == Decimal("31.5")


def test_export_csv_requires_view_costs(client, viewer_token, pm_token):
    """Fail-closed : viewer (sans view_costs) refusé, pm autorisé."""
    assert (
        client.get("/agent-control/v1/reports/export.csv", headers=auth(viewer_token)).status_code
        == 403
    )
    assert (
        client.get("/agent-control/v1/reports/export.csv", headers=auth(pm_token)).status_code
        == 200
    )


def test_export_csv_never_leaks_other_tenant(client, db, admin_token):
    """Les consommations d'un autre tenant n'apparaissent jamais dans l'export local."""
    inst_b = MCInstallation(
        external_tenant_id="tenant-b-p9",
        installation_key=f"tb9-{uuid.uuid4().hex[:6]}",
        status="active",
    )
    db.add(inst_b)
    db.commit()
    agent_b = Agent(agent_key=f"tb9:{uuid.uuid4().hex[:8]}", installation_id=inst_b.id)
    db.add(agent_b)
    db.commit()
    db.add(
        AgentUsageRecord(
            installation_id=inst_b.id,
            agent_id=agent_b.id,
            source_event_id="b-export-1",
            occurred_at=_T0,
            cost=Decimal("999"),
            pricing_version="x",
            total_tokens=1,
        )
    )
    db.commit()

    resp = client.get("/agent-control/v1/reports/export.csv", headers=auth(admin_token))
    assert resp.status_code == 200
    _, rows = _parse_csv(resp.text)
    # Aucune ligne du tenant B (ni son coût sentinelle, ni son agent).
    assert all(r["cost"] != "999" for r in rows)
    assert all(r["agent_id"] != str(agent_b.id) for r in rows)


def test_export_csv_unauthenticated_rejected(client):
    """Sans JWT hôte : refus (jamais d'export anonyme)."""
    assert client.get("/agent-control/v1/reports/export.csv").status_code in (401, 403)


def test_export_csv_matches_ingested_rows_count(client, db, admin_token):
    """Le nombre de lignes exportées == nombre de records DB du tenant/agent."""
    agent, secret = _make_agent_with_cred(db)
    _ingest(client, secret, [_usage_ev(agent.agent_key, 1, input_tokens=500, output_tokens=0)])
    db_count = len(
        db.scalars(
            select(AgentUsageRecord).where(AgentUsageRecord.agent_id == agent.id)
        ).all()
    )
    resp = client.get(
        f"/agent-control/v1/reports/export.csv?agent_id={agent.id}", headers=auth(admin_token)
    )
    _, rows = _parse_csv(resp.text)
    assert len(rows) == db_count == 1
