"""Point d'entrée FastAPI — API Gateway de Project Mission Control.

Lancement : `uvicorn apps.api.main:app --reload`

Routers :
- fast-path (mc-bridge) : GET /agents, /projects, /stats lus des statuts mc.
- auth (M2)     : /auth/login, /auth/me + get_current_user.
- ingest (M3)   : POST /agents/heartbeat → DB + publish Redis.
- realtime (M4) : WS /ws + abonné Redis + scanner stale (démarrés au lifespan).
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.core.config import settings
from apps.api.realtime import ws as ws_module
from apps.api.routers import agents as agents_router
from apps.api.routers import auth as auth_router
from apps.api.routers import heartbeat as heartbeat_router
from apps.api.routers import projects as projects_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Démarre l'abonné Redis + le scanner stale (realtime / M4).
    await ws_module.start()
    yield
    await ws_module.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["infra"])
def health() -> dict[str, str]:
    """Healthcheck — utilisé par docker-compose et le front."""
    return {"status": "ok", "service": settings.app_name, "env": settings.environment}


# Fast-path : GET agents/projets/stats lus des statuts du skill mission-control.
app.include_router(agents_router.router)
app.include_router(projects_router.router)
# Auth (M2), ingest heartbeat (M3), temps réel (M4).
app.include_router(auth_router.router)
app.include_router(heartbeat_router.router)
app.include_router(ws_module.router)
