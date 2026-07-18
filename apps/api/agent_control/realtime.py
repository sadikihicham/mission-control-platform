"""Temps réel V1 Agent Control (Contract E V1, §10) — WS + relais outbox.

Ferme le gap assumé au Gate P7 : le catalogue d'événements et l'enveloppe
`WsMessageV1` étaient figés mais aucun handler serveur ne diffusait, et l'outbox
(`mc_outbox_events`) s'accumulait sans être drainée. Ce module :

- **relais d'outbox** : draine périodiquement les lignes `pending` de
  `mc_outbox_events` et les publie sur le canal Redis V1 `ac:events`
  (persistance AVANT publication, ADR-0005 ; livraison au moins une fois, les
  consommateurs déduplifient par `event_id`). `SELECT ... FOR UPDATE SKIP LOCKED`
  rend le drain sûr même à plusieurs instances API ;
- **abonné Redis** `ac:events` : relaie chaque message aux clients WS **filtrés
  par tenant et topic souscrit** ;
- **endpoint** `/agent-control/ws?token=<jwt>&installation_id=<uuid>` : valide
  identité + tenant + capacité `view` avant d'accepter (fail-closed), n'expose
  JAMAIS le tenant d'un autre (le `tenant_id` de la connexion est résolu serveur,
  jamais lu du query au-delà d'un contrôle d'égalité), puis diffuse les topics
  autorisés que le client a souscrits.

Distinct du WS V0 (`realtime/ws.py`, canal `mc:events`) : aucun code partagé,
aucun canal partagé. Les événements V1 sont des signaux légers ; la donnée fait
foi via HTTP (le front invalide la query concernée et refetch la source).
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError
from sqlalchemy import select

from apps.api.core.agent_control_deps import _build_adapter
from apps.api.core.config import settings
from apps.api.core.db import get_sessionmaker
from apps.api.core.redis import AC_EVENTS_CHANNEL, get_async_redis
from apps.api.core.security import decode_token
from apps.api.integrations.capabilities import Capability
from apps.api.integrations.errors import HostIntegrationError
from apps.api.integrations.events_catalog import is_valid_topic
from apps.api.integrations.host_context import HostContext
from apps.api.models import MCOutboxEvent, User

router = APIRouter(tags=["agent-control-realtime"])

# Nombre max de topics souscrits par connexion (borne anti-abus).
_MAX_TOPICS_PER_CONN = 200
# Cadence du relais d'outbox (secondes) et taille de lot.
_RELAY_INTERVAL_SECONDS = 1.0
_RELAY_BATCH = 200
# Plafond de tentatives avant de marquer une ligne d'outbox `failed`.
_RELAY_MAX_ATTEMPTS = 8


class _AcConnection:
    """Une connexion WS consommatrice : tenant figé + topics souscrits."""

    __slots__ = ("ws", "tenant_id", "topics")

    def __init__(self, ws: WebSocket, tenant_id: str) -> None:
        self.ws = ws
        self.tenant_id = tenant_id
        self.topics: set[str] = set()


class AcConnectionManager:
    """Registre des connexions WS V1, indexées par tenant pour un fan-out borné.

    Un message n'est jamais envoyé à une connexion d'un autre tenant : le filtrage
    par `tenant_id` est la garantie d'isolation (jamais de canal partagé en clair).
    """

    def __init__(self) -> None:
        self._by_tenant: dict[str, set[_AcConnection]] = {}

    async def connect(self, ws: WebSocket, tenant_id: str) -> _AcConnection:
        await ws.accept()
        conn = _AcConnection(ws, tenant_id)
        self._by_tenant.setdefault(tenant_id, set()).add(conn)
        return conn

    def disconnect(self, conn: _AcConnection) -> None:
        bucket = self._by_tenant.get(conn.tenant_id)
        if bucket is not None:
            bucket.discard(conn)
            if not bucket:
                self._by_tenant.pop(conn.tenant_id, None)

    async def fanout(self, tenant_id: str, topic: str, raw: str) -> None:
        """Diffuse `raw` aux connexions du tenant abonnées au topic. Fail-closed."""
        dead: list[_AcConnection] = []
        for conn in list(self._by_tenant.get(tenant_id, ())):
            if topic not in conn.topics:
                continue
            try:
                await conn.ws.send_text(raw)
            except Exception:  # noqa: BLE001
                dead.append(conn)
        for conn in dead:
            self.disconnect(conn)

    def tenant_count(self) -> int:
        return len(self._by_tenant)


manager = AcConnectionManager()


# --- Authentification / résolution de contexte WS -----------------------------


def _resolve_ws_context(token: str, installation_id: str | None) -> HostContext:
    """Résout le `HostContext` d'une connexion WS depuis le JWT hôte, fail-closed.

    Vérifie ensuite que l'`installation_id` demandé (query) correspond bien à
    l'installation résolue serveur — jamais l'inverse (le query ne choisit pas le
    tenant, il ne peut que le confirmer). Toute incohérence → refus.

    Mode `jwt` (ADR-0010) : le jeton est celui de l'hôte, décodé par
    l'adaptateur lui-même — pas avec le JWT V0 de ce service (`decode_token`),
    qui ne s'applique qu'au mode `local` par défaut ci-dessous.
    """
    session_factory = get_sessionmaker()
    with session_factory() as db:
        adapter = _build_adapter(db)
        if settings.mc_host_adapter == "jwt":
            credential = token
        else:
            payload = decode_token(token)  # peut lever JWTError
            user_id = uuid.UUID(str(payload["sub"]))
            credential = db.get(User, user_id)
            # Un `user` absent/inactif fait lever `IdentityUnresolved`
            # (fail-closed) par l'adaptateur — inutile de dupliquer le contrôle.
        ctx = adapter.build_context(credential, request_id=str(uuid.uuid4()))
    # Le tenant est résolu serveur ; le query ne sert qu'à confirmer (ADR-0003).
    if installation_id and installation_id != ctx.installation.id:
        raise PermissionError("installation_id ne correspond pas au tenant résolu")
    return ctx


@router.websocket("/agent-control/ws")
async def agent_control_ws(
    ws: WebSocket,
    token: str | None = Query(default=None),
    installation_id: str | None = Query(default=None),
) -> None:
    """WS consommateur V1 : signaux temps réel tenant-scopés (invalidation ciblée).

    Protocole client → serveur (JSON) :
      `{"action":"subscribe","topics":["fleet","run:<id>"]}` / `"unsubscribe"`.
    Serveur → client : `WsMessageV1` (`{id,type,tenant_id,topic,sequence,data,occurred_at}`).
    Un `ping` client reçoit `{"type":"pong"}` (heartbeat applicatif).
    """
    if not token:
        await ws.close(code=4401)
        return
    try:
        ctx = _resolve_ws_context(token, installation_id)
    except JWTError:
        await ws.close(code=4401)  # token invalide
        return
    except PermissionError:
        await ws.close(code=4403)  # tenant demandé ≠ tenant résolu
        return
    except HostIntegrationError:
        await ws.close(code=4403)  # identité/tenant non résolu (fail-closed)
        return
    except Exception:  # noqa: BLE001 — toute autre erreur d'auth = refus
        await ws.close(code=4401)
        return

    # La capacité minimale de lecture est exigée pour recevoir le moindre signal.
    if not ctx.has(Capability.view):
        await ws.close(code=4403)
        return

    conn = await manager.connect(ws, ctx.installation.id)
    # Confirme au client le tenant résolu (il ne l'a jamais choisi lui-même).
    with contextlib.suppress(Exception):
        await ws.send_text(json.dumps({"type": "ready", "tenant_id": ctx.installation.id}))
    try:
        while True:
            raw = await ws.receive_text()
            _handle_client_message(conn, ctx, raw)
            # Réponse de heartbeat applicatif (le client peut aussi juste garder ouvert).
            with contextlib.suppress(Exception):
                if raw and '"ping"' in raw:
                    await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(conn)
    except Exception:  # noqa: BLE001
        manager.disconnect(conn)
        with contextlib.suppress(Exception):
            await ws.close()


def _handle_client_message(conn: _AcConnection, ctx: HostContext, raw: str) -> None:
    """Applique une commande de souscription. Topics invalides ignorés (fail-closed).

    Un topic paramétré (`project:{id}`, `agent:{id}`, `run:{id}`) est accepté sur
    la forme ; l'isolation reste garantie par le filtrage tenant du fan-out (un
    client ne reçoit jamais que les événements de SON tenant, quel que soit l'id).
    """
    try:
        msg = json.loads(raw)
    except (ValueError, TypeError):
        return
    if not isinstance(msg, dict):
        return
    action = msg.get("action")
    topics = msg.get("topics")
    if action not in ("subscribe", "unsubscribe") or not isinstance(topics, list):
        return
    for topic in topics:
        if not isinstance(topic, str) or not is_valid_topic(topic):
            continue
        if action == "subscribe":
            if len(conn.topics) < _MAX_TOPICS_PER_CONN:
                conn.topics.add(topic)
        else:
            conn.topics.discard(topic)


# --- Abonné Redis `ac:events` -------------------------------------------------


async def _ac_redis_subscriber() -> None:
    """Relaie chaque message `ac:events` aux clients WS filtrés (tenant + topic)."""
    pubsub = get_async_redis().pubsub()
    await pubsub.subscribe(AC_EVENTS_CHANNEL)
    async for msg in pubsub.listen():
        if msg.get("type") != "message":
            continue
        raw = msg["data"]
        try:
            data = json.loads(raw)
            tenant_id = str(data["tenant_id"])
            topic = str(data["topic"])
        except (ValueError, TypeError, KeyError):
            continue
        await manager.fanout(tenant_id, topic, raw)


# --- Relais d'outbox (persistance → publication) ------------------------------


def _ws_message(row: MCOutboxEvent) -> str:
    """Projette une ligne d'outbox en `WsMessageV1` sérialisé (jamais de tenant nul)."""
    occurred = row.created_at or datetime.now(UTC)
    return json.dumps(
        {
            "id": row.event_id,
            "type": row.event_type,
            "tenant_id": str(row.installation_id) if row.installation_id else "",
            "topic": row.topic,
            "sequence": row.sequence if row.sequence is not None else 0,
            "data": row.payload or {},
            "occurred_at": occurred.isoformat(),
        },
        default=str,
    )


async def _publish_pending_batch() -> int:
    """Draine un lot de lignes `pending` → Redis `ac:events`. Renvoie le nb publié.

    Chaque ligne est verrouillée `FOR UPDATE SKIP LOCKED` : deux instances API ne
    publient jamais la même ligne dans la même fenêtre. Une ligne sans tenant
    (installation_id nul) n'est pas diffusable en WS (pas de canal tenant) — elle
    est marquée `published` pour ne pas boucler (le fait métier reste en base).
    Un échec Redis laisse la ligne `pending` (attempts++), jamais perdue.
    """
    session_factory = get_sessionmaker()
    redis = get_async_redis()
    published = 0
    with session_factory() as db:
        rows = list(
            db.scalars(
                select(MCOutboxEvent)
                .where(MCOutboxEvent.status == "pending")
                .order_by(MCOutboxEvent.created_at)
                .limit(_RELAY_BATCH)
                .with_for_update(skip_locked=True)
            )
        )
        if not rows:
            return 0
        now = datetime.now(UTC)
        for row in rows:
            if not row.installation_id:
                row.status = "published"
                row.published_at = now
                continue
            try:
                await redis.publish(AC_EVENTS_CHANNEL, _ws_message(row))
            except Exception as exc:  # noqa: BLE001 — Redis indispo : on retente plus tard
                row.attempts = (row.attempts or 0) + 1
                row.last_error = str(exc)[:500]
                if row.attempts >= _RELAY_MAX_ATTEMPTS:
                    row.status = "failed"
                continue
            row.status = "published"
            row.published_at = now
            published += 1
        db.commit()
    return published


async def _outbox_relay() -> None:
    """Boucle du relais d'outbox : draine à cadence fixe, resiliente aux erreurs."""
    while True:
        await asyncio.sleep(_RELAY_INTERVAL_SECONDS)
        try:
            # Draine tant qu'il reste des lots pleins (rattrapage sans attendre).
            while await _publish_pending_batch() >= _RELAY_BATCH:
                pass
        except Exception:  # noqa: BLE001 — jamais laisser la boucle mourir
            continue


_tasks: list[asyncio.Task] = []


async def start() -> None:
    """Démarre l'abonné Redis V1 + le relais d'outbox (lifespan, main.py)."""
    _tasks.append(asyncio.create_task(_ac_redis_subscriber()))
    _tasks.append(asyncio.create_task(_outbox_relay()))


async def stop() -> None:
    for task in _tasks:
        task.cancel()
    _tasks.clear()
