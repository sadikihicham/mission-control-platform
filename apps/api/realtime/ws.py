"""Temps réel (Contract E) — WS + abonné Redis + détection stale. Owner : `realtime` (M4).

- `/ws?token=<JWT>` : fan-out des événements aux clients connectés.
- abonné Redis `mc:events` : relaie chaque message publié par `api` aux clients WS.
- scanner stale : un agent `working` silencieux > seuil passe `stale` (DB + event).
"""
import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError
from sqlalchemy import select

from apps.api.core.config import settings
from apps.api.core.db import get_sessionmaker
from apps.api.core.redis import EVENTS_CHANNEL, get_async_redis, publish_event
from apps.api.core.security import decode_token
from apps.api.models import Agent, AgentState
from apps.api.services.events import publish_stats
from apps.api.services.mc_sync import sync_once

router = APIRouter(tags=["realtime"])


class ConnectionManager:
    def __init__(self) -> None:
        self.active: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.active.discard(ws)

    async def broadcast(self, message: str) -> None:
        dead = []
        for ws in list(self.active):
            try:
                await ws.send_text(message)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket, token: str | None = Query(default=None)) -> None:
    if not token:
        await ws.close(code=4401)
        return
    try:
        decode_token(token)
    except JWTError:
        await ws.close(code=4401)
        return
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keepalive ; on ignore les messages client
    except WebSocketDisconnect:
        manager.disconnect(ws)


async def _redis_subscriber() -> None:
    pubsub = get_async_redis().pubsub()
    await pubsub.subscribe(EVENTS_CHANNEL)
    async for msg in pubsub.listen():
        if msg.get("type") == "message":
            await manager.broadcast(msg["data"])


async def _stale_scanner() -> None:
    session_factory = get_sessionmaker()
    while True:
        await asyncio.sleep(15)
        threshold = datetime.now(UTC) - timedelta(seconds=settings.mc_stale_seconds)
        with session_factory() as db:
            stale = db.scalars(
                select(Agent).where(
                    Agent.state == AgentState.working,
                    Agent.last_heartbeat.is_not(None),
                    Agent.last_heartbeat < threshold,
                )
            ).all()
            for agent in stale:
                agent.state = AgentState.stale
            if stale:
                db.commit()
                for agent in stale:
                    publish_event("agent.stale", {"agent_key": agent.agent_key, "state": "stale"})
                publish_stats()


def _status_signature() -> tuple:
    """Empreinte (nb fichiers + mtime max) du dossier de statuts mc."""
    d = Path(settings.mc_status_dir)
    if not d.is_dir():
        return (0, 0.0)
    files = list(d.glob("*.json"))
    mtime = max((f.stat().st_mtime for f in files), default=0.0)
    return (len(files), mtime)


async def _mc_file_watcher() -> None:
    """Sync fichiers mc → DB à chaque changement, puis émet `refresh` (push)."""
    session_factory = get_sessionmaker()
    with session_factory() as db:
        sync_once(db)  # sync initial au démarrage
    last = _status_signature()
    while True:
        await asyncio.sleep(2)
        sig = _status_signature()
        if sig != last:
            last = sig
            with session_factory() as db:
                sync_once(db)
            publish_event("refresh", {"source": "mc-files"})
            publish_stats()


_tasks: list[asyncio.Task] = []


async def start() -> None:
    _tasks.append(asyncio.create_task(_redis_subscriber()))
    _tasks.append(asyncio.create_task(_stale_scanner()))
    _tasks.append(asyncio.create_task(_mc_file_watcher()))


async def stop() -> None:
    for task in _tasks:
        task.cancel()
    _tasks.clear()
