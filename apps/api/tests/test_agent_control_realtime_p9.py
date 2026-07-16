"""P9 — temps réel V1 Agent Control (`/agent-control/ws` + relais d'outbox).

Ferme le gap assumé au Gate P7 : catalogue/enveloppes figés mais aucun handler
serveur (le front retombait sur du polling) et l'outbox non drainée. Prouve :

- **handshake WS fail-closed** : token absent/invalide → refus ; `installation_id`
  ≠ tenant résolu serveur → refus (le query ne choisit jamais le tenant) ;
- **connexion valide** : le serveur confirme le `tenant_id` résolu (jamais choisi
  par le client) ;
- **souscription bornée** : topics hors catalogue ignorés (fail-closed) ;
- **isolation du fan-out** : un client d'un tenant ne reçoit JAMAIS l'événement
  d'un autre tenant, ni un topic non souscrit ;
- **relais d'outbox** : draine les lignes `pending` vers `ac:events`, projette un
  `WsMessageV1` estampillé tenant, marque `published` (persistance avant
  publication, livraison au moins une fois).
"""
import asyncio
import json
import uuid

import pytest
from starlette.websockets import WebSocketDisconnect

from apps.api.agent_control import realtime as rt
from apps.api.agent_control.operations.outbox import emit_outbox
from apps.api.models import LOCAL_INSTALLATION_ID, MCOutboxEvent

LOCAL = str(LOCAL_INSTALLATION_ID)


# --- Handshake WS -------------------------------------------------------------


def test_ws_rejects_missing_token(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/agent-control/ws") as ws:
            ws.receive_text()


def test_ws_rejects_invalid_token(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/agent-control/ws?token=not-a-jwt") as ws:
            ws.receive_text()


def test_ws_rejects_installation_mismatch(client, admin_token):
    other = "00000000-0000-0000-0000-000000000000"
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            f"/agent-control/ws?token={admin_token}&installation_id={other}"
        ) as ws:
            ws.receive_text()


def test_ws_accepts_and_confirms_resolved_tenant(client, admin_token):
    with client.websocket_connect(f"/agent-control/ws?token={admin_token}") as ws:
        ready = json.loads(ws.receive_text())
        assert ready["type"] == "ready"
        # Le tenant est résolu serveur, jamais choisi par le client.
        assert ready["tenant_id"] == LOCAL


def test_ws_matching_installation_id_is_accepted(client, admin_token):
    with client.websocket_connect(
        f"/agent-control/ws?token={admin_token}&installation_id={LOCAL}"
    ) as ws:
        ready = json.loads(ws.receive_text())
        assert ready["tenant_id"] == LOCAL


# --- Souscription (unité) -----------------------------------------------------


def test_subscribe_filters_out_invalid_topics():
    conn = rt._AcConnection(ws=None, tenant_id=LOCAL)
    run_id = str(uuid.uuid4())
    rt._handle_client_message(
        conn,
        None,
        json.dumps({"action": "subscribe", "topics": ["fleet", f"run:{run_id}", "nope!", 42]}),
    )
    assert "fleet" in conn.topics
    assert f"run:{run_id}" in conn.topics
    assert "nope!" not in conn.topics  # famille inconnue → rejeté
    # unsubscribe retire proprement.
    rt._handle_client_message(
        conn, None, json.dumps({"action": "unsubscribe", "topics": ["fleet"]})
    )
    assert "fleet" not in conn.topics


def test_subscribe_ignores_malformed_payload():
    conn = rt._AcConnection(ws=None, tenant_id=LOCAL)
    rt._handle_client_message(conn, None, "not json")
    rt._handle_client_message(conn, None, json.dumps({"action": "bogus", "topics": ["fleet"]}))
    rt._handle_client_message(conn, None, json.dumps(["fleet"]))
    assert conn.topics == set()


# --- Isolation du fan-out (unité) ---------------------------------------------


class _FakeWS:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_text(self, message: str) -> None:
        self.sent.append(message)


def _register(mgr: rt.AcConnectionManager, tenant: str, topics: set[str]) -> _FakeWS:
    ws = _FakeWS()
    conn = rt._AcConnection(ws, tenant)
    conn.topics = set(topics)
    mgr._by_tenant.setdefault(tenant, set()).add(conn)
    return ws


def test_fanout_never_crosses_tenant_boundary():
    async def scenario():
        mgr = rt.AcConnectionManager()
        a = _register(mgr, "tenant-A", {"fleet"})
        b = _register(mgr, "tenant-B", {"fleet"})
        await mgr.fanout("tenant-A", "fleet", "evt-A")
        return a.sent, b.sent

    sent_a, sent_b = asyncio.run(scenario())
    assert sent_a == ["evt-A"]
    assert sent_b == []  # tenant B ne reçoit jamais l'événement du tenant A


def test_fanout_respects_topic_subscription():
    async def scenario():
        mgr = rt.AcConnectionManager()
        subscribed = _register(mgr, "tenant-A", {"fleet"})
        other_topic = _register(mgr, "tenant-A", {"approvals"})
        await mgr.fanout("tenant-A", "fleet", "evt")
        return subscribed.sent, other_topic.sent

    got, not_subscribed = asyncio.run(scenario())
    assert got == ["evt"]
    assert not_subscribed == []  # topic non souscrit → pas de livraison


# --- Projection WsMessageV1 ---------------------------------------------------


def test_ws_message_projection_stamps_tenant():
    row = MCOutboxEvent(
        installation_id=LOCAL_INSTALLATION_ID,
        event_id="evt-1",
        event_type="alert.opened",
        topic="fleet",
        sequence=7,
        payload={"alert_id": "x"},
        status="pending",
    )
    msg = json.loads(rt._ws_message(row))
    assert msg["tenant_id"] == LOCAL  # jamais diffusé sans tenant
    assert msg["type"] == "alert.opened"
    assert msg["topic"] == "fleet"
    assert msg["sequence"] == 7
    assert msg["data"] == {"alert_id": "x"}
    assert msg["id"] == "evt-1"


# --- Relais d'outbox (drain → publish → published) ----------------------------


def test_outbox_relay_drains_pending_and_publishes(db, monkeypatch):
    row = emit_outbox(
        db,
        installation_id=LOCAL_INSTALLATION_ID,
        event_type="alert.opened",
        topic="fleet",
        payload={"alert_id": "abc"},
    )
    db.commit()
    row_id = row.id

    published: list[tuple[str, str]] = []

    class _FakeRedis:
        async def publish(self, channel: str, message: str) -> None:
            published.append((channel, message))

    monkeypatch.setattr(rt, "get_async_redis", lambda: _FakeRedis())
    n = asyncio.run(rt._publish_pending_batch())
    assert n >= 1

    # La ligne visée est désormais publiée (persistance avant publication).
    db.expire_all()
    refreshed = db.get(MCOutboxEvent, row_id)
    assert refreshed.status == "published"
    assert refreshed.published_at is not None

    # Le message diffusé porte le tenant et le canal V1.
    channels = {c for c, _ in published}
    assert rt.AC_EVENTS_CHANNEL in channels
    payloads = [json.loads(m) for _, m in published]
    assert any(p["tenant_id"] == LOCAL and p["type"] == "alert.opened" for p in payloads)


def test_outbox_relay_marks_untenanted_rows_published_without_publishing(db, monkeypatch):
    # Une ligne sans installation_id n'est pas diffusable (pas de canal tenant) :
    # elle est marquée published pour ne pas boucler, jamais diffusée.
    row = MCOutboxEvent(
        installation_id=None,
        event_id=f"orphan-{uuid.uuid4().hex[:8]}",
        event_type="alert.opened",
        topic="fleet",
        payload={},
        status="pending",
    )
    db.add(row)
    db.commit()
    row_id = row.id

    published: list = []

    class _FakeRedis:
        async def publish(self, channel: str, message: str) -> None:
            published.append(message)

    monkeypatch.setattr(rt, "get_async_redis", lambda: _FakeRedis())
    asyncio.run(rt._publish_pending_batch())

    db.expire_all()
    refreshed = db.get(MCOutboxEvent, row_id)
    assert refreshed.status == "published"
    # Aucun message diffusé ne référence cette ligne orpheline.
    assert all(row.event_id not in m for m in published)
