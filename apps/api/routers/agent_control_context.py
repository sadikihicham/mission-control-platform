"""Routes Agent Control V1 — contexte et capacités (lecture seule).

`GET /agent-control/v1/context` : le `HostContext` résolu serveur de l'appelant
(installation, tenant, utilisateur, capacités, locale, fuseau).
`GET /agent-control/v1/capabilities` : la liste des capacités accordées.

Ces routes ne s'appuient que sur les primitives figées au Gate P0 : aucune
donnée métier, aucune écriture. Le tenant est dérivé de l'identité (ADR-0003),
jamais d'un query/body. Fail-closed via `get_host_context`.
"""
from fastapi import APIRouter, Depends

from apps.api.core.agent_control_deps import get_host_context
from apps.api.integrations.host_context import HostContext

router = APIRouter(prefix="/agent-control/v1", tags=["agent-control"])


@router.get("/context", response_model=HostContext)
def get_context(ctx: HostContext = Depends(get_host_context)) -> HostContext:
    """Retourne le contexte hôte complet de la requête (résolu serveur)."""
    return ctx


@router.get("/capabilities")
def get_capabilities(ctx: HostContext = Depends(get_host_context)) -> dict:
    """Retourne la liste triée des capacités accordées à l'appelant."""
    return {"capabilities": sorted(c.value for c in ctx.capabilities)}
