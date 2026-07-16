"""P7 / SP7 — E2E vertical du plan de contrôle V1, 100 % via HTTP.

Prouve que les briques livrees se raccordent bout-en-bout, sans acces DB direct :
un admin enregistre un agent, emet un credential, l'agent ingere des evenements
`run.*` authentifie par CE credential, puis le run/dashboard/timeline refletent
le fait — le tout borne au tenant. Valide notamment que le credential emis par le
registre (P7) authentifie reellement l'ingest runtime (Contract D/§8).
"""
import uuid

HDR = "X-Agent-Credential"


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _event(agent_key, seq, event_type, run_id, *, payload=None):
    return {
        "event_id": str(uuid.uuid4()),
        "agent_key": agent_key,
        "sequence": seq,
        "event_type": event_type,
        "occurred_at": "2026-07-16T10:00:00Z",
        "payload": payload or {},
        "run_id": run_id,
    }


def test_e2e_register_credential_ingest_run_dashboard(client, admin_token, viewer_token):
    # 1) Admin enregistre un agent (cle derivee <installation_key>:<local_key>).
    reg = client.post(
        "/agent-control/v1/agents",
        json={"local_key": "e2e", "display_name": "E2E worker", "capabilities": ["code"]},
        headers=auth(admin_token),
    )
    assert reg.status_code == 201, reg.text
    agent = reg.json()
    agent_id, agent_key = agent["id"], agent["agent_key"]
    assert agent_key == "local:e2e"

    # 2) Admin emet un credential (secret affiche une seule fois).
    cr = client.post(
        f"/agent-control/v1/agents/{agent_id}/credentials",
        json={"scopes": ["ingest"]},
        headers=auth(admin_token),
    )
    assert cr.status_code == 201, cr.text
    secret = cr.json()["secret"]
    assert secret and "." in secret

    # 3) L'agent ingere run.running puis run.succeeded, authentifie par CE credential.
    run_id = str(uuid.uuid4())
    batch = {
        "events": [
            _event(agent_key, 1, "run.running", run_id, payload={"objective": "build E2E"}),
            _event(agent_key, 2, "run.succeeded", run_id, payload={"result_summary": "ok"}),
        ]
    }
    ing = client.post("/agent-control/v1/ingest/events", json=batch, headers={HDR: secret})
    assert ing.status_code in (200, 202), ing.text
    assert ing.json()["accepted"] == 2

    # 4) Le run projete est visible en lecture (borne tenant), etat terminal succeeded.
    runs = client.get("/agent-control/v1/runs", headers=auth(viewer_token))
    assert runs.status_code == 200
    match = [r for r in runs.json()["items"] if r["id"] == run_id]
    assert match, "run projete introuvable en lecture"
    assert match[0]["state"] == "succeeded"

    # 5) La timeline auditable expose les evenements (redacted), ordonnee par sequence.
    tl = client.get(f"/agent-control/v1/runs/{run_id}/timeline", headers=auth(viewer_token))
    assert tl.status_code == 200
    seqs = [i["sequence"] for i in tl.json()["items"]]
    assert seqs == sorted(seqs) and len(seqs) >= 2

    # 6) Le dashboard reflete l'agent et le run reels (agregats derives serveur).
    dash = client.get("/agent-control/v1/dashboard", headers=auth(admin_token)).json()
    assert dash["agents"]["total"] >= 1
    assert dash["runs"]["total"] >= 1
    assert dash["runs"]["succeeded"] >= 1


def test_e2e_ingest_rejected_for_foreign_agent_key(client, admin_token):
    """Un credential ne peut agir que pour SON agent : agent_key different rejete."""
    a = client.post(
        "/agent-control/v1/agents",
        json={"local_key": f"own-{uuid.uuid4().hex[:6]}"},
        headers=auth(admin_token),
    ).json()
    secret = client.post(
        f"/agent-control/v1/agents/{a['id']}/credentials",
        json={"scopes": ["ingest"]},
        headers=auth(admin_token),
    ).json()["secret"]
    # Evenement pretendant un autre agent_key que celui du credential.
    bad = {"events": [_event("local:someone-else", 1, "run.running", str(uuid.uuid4()))]}
    r = client.post("/agent-control/v1/ingest/events", json=bad, headers={HDR: secret})
    # Refuse (permission_denied) ou rejete sans projection — jamais accepte comme l'agent d'autrui.
    assert r.status_code in (200, 202, 403)
    if r.status_code in (200, 202):
        assert r.json()["accepted"] == 0
