"""Point d'entrée FastAPI — API Gateway de Project Mission Control.

Lancement : `uvicorn apps.api.main:app --reload`

Routers :
- fast-path (mc-bridge) : GET /agents, /projects, /stats lus des statuts mc.
- auth (M2)     : /auth/login, /auth/me + get_current_user.
- ingest (M3)   : POST /agents/heartbeat → DB + publish Redis.
- realtime (M4) : WS /ws + abonné Redis + scanner stale (démarrés au lifespan).
"""
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.agent_control import realtime as agent_control_realtime
from apps.api.agent_control.control import agent_routes as agent_control_agent_cmd_router
from apps.api.agent_control.control import routes as agent_control_control_router
from apps.api.agent_control.ingest import routes as agent_control_ingest_router
from apps.api.agent_control.operations import routes as agent_control_operations_router
from apps.api.agent_control.overview import routes as agent_control_overview_router
from apps.api.agent_control.projects import routes as agent_control_projects_router
from apps.api.agent_control.registry import routes as agent_control_registry_router
from apps.api.agent_control.runs import routes as agent_control_runs_router
from apps.api.core.config import settings
from apps.api.integrations.envelopes import ErrorBody, ErrorEnvelope
from apps.api.integrations.errors import HostIntegrationError
from apps.api.realtime import ws as ws_module
from apps.api.routers import agent_control_context as agent_control_context_router
from apps.api.routers import agents as agents_router
from apps.api.routers import auth as auth_router
from apps.api.routers import heartbeat as heartbeat_router
from apps.api.routers import projects as projects_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Démarre l'abonné Redis + le scanner stale (realtime V0 / M4).
    await ws_module.start()
    # Démarre le temps réel V1 Agent Control : abonné canal `ac:events` + relais
    # d'outbox (persistance → publication, Contract E V1 §10). Distinct du V0.
    await agent_control_realtime.start()
    yield
    await agent_control_realtime.stop()
    await ws_module.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HostIntegrationError)
async def _host_integration_error_handler(
    request: Request, exc: HostIntegrationError
) -> JSONResponse:
    """Traduit toute erreur d'intégration hôte (identité/tenant/permission) en
    enveloppe d'erreur V1 `{"error": {code, message, request_id, details}}` avec
    le statut HTTP associé. S'applique aussi aux erreurs levées dans les
    dépendances des routes `/agent-control/v1/*` (fail-closed)."""
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    body = ErrorEnvelope(
        error=ErrorBody(
            code=exc.code, message=exc.message, request_id=request_id, details=exc.details
        )
    )
    return JSONResponse(status_code=exc.http_status, content=body.model_dump(mode="json"))


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
# WS temps réel V1 Agent Control (`/agent-control/ws`) : signaux tenant-scopés
# (invalidation ciblée côté front). Canal `ac:events`, distinct du `/ws` V0.
app.include_router(agent_control_realtime.router)
# Agent Control V1 (contexte + capacités, lecture seule, tenant résolu serveur).
app.include_router(agent_control_context_router.router)
# Agent Control V1 — vue d'ensemble (P7) : /health, /dashboard (agrégats tenant
# dérivés serveur), activation d'installation (admin). Aucun compteur client.
app.include_router(agent_control_overview_router.router)
# Agent Control V1 — registre d'agents (P7) : liste/détail/santé (view),
# enregistrement/màj/credentials/cycle de vie (manage_agents). Tenant-scoped.
app.include_router(agent_control_registry_router.router)
# Agent Control V1 — projets & tâches (P8) : lecture (view) et mutation
# (manage_projects) tenant-scoped. Ferme le gap assumé en P7 : les tables V0
# projects/tasks portent désormais installation_id (migration 0016). Cross-tenant
# = 404 (ADR-0003).
app.include_router(agent_control_projects_router.router)
# Agent Control V1 — ingest (événements + heartbeat), authentifié par credential
# agent (hors JWT utilisateur). Distinct du heartbeat V0 `/agents/heartbeat`.
app.include_router(agent_control_ingest_router.router)
# Agent Control V1 — plan de contrôle des runs (lecture : liste, détail, timeline).
# Bornage tenant + capacité `view` (matrice figée §8). Les runs se créent par
# projection des événements d'ingest, pas par une route utilisateur (P4).
app.include_router(agent_control_runs_router.router)
# Agent Control V1 — contrôle humain (P5) : commandes (soumission opérateur via
# POST /runs/{id}/commands), approbations (décision versionnée) et politiques
# (allow|deny|require_approval). JWT hôte + capacité (operate/approve/admin/view).
app.include_router(agent_control_control_router.router)
# Agent Control V1 — file de commandes côté agent (récupération long poll, ACK,
# résultat). Authentifié par credential agent (scope `commands`), hors RBAC user.
app.include_router(agent_control_agent_cmd_router.router)
# Agent Control V1 — plan opérationnel (P6) : usage/coûts, budgets, alertes et
# audit append-only redacted. JWT hôte + capacité (view_costs/operate/view).
app.include_router(agent_control_operations_router.router)
