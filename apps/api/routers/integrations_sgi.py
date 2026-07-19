"""Webhook entrant SGI → bascule de `mc_installations.status` (ADR-0011).

Pont d'activation par tenant : un admin SGI active/désactive la souscription
partagée `agent_control` → SGI notifie ce service par un appel machine-à-machine
signé HMAC (jamais un JWT utilisateur — pas d'utilisateur humain dans ce flux).

Authentification : en-tête `X-SGI-Signature: sha256=<hex-hmac-sha256>`, calculé
sur le corps brut exact de la requête avec `settings.sgi_webhook_secret`. Absente
ou invalide → 401, jamais de fallback vers un traitement du payload (fail-closed,
même philosophie que `routers/heartbeat.py`'s `X-MC-Token`).

Ne crée jamais de ligne `mc_installations` (ADR-0011 §2 — pas d'auto-provisioning) :
seule une installation déjà existante peut être basculée active/suspended.
"""
import hashlib
import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core.config import settings
from apps.api.core.db import get_db
from apps.api.models import MCInstallation
from apps.api.schemas.integrations_sgi import SubscriptionEventIn

router = APIRouter(tags=["integrations"])

_TARGET_ACTIVITY_KEY = "agent_control"


def _verify_signature(raw_body: bytes, signature: str | None) -> None:
    if not signature or not signature.startswith("sha256="):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "signature manquante ou malformée")
    expected = hmac.new(
        settings.sgi_webhook_secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature.removeprefix("sha256="), expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "signature invalide")


@router.post("/integrations/sgi/subscription-events", status_code=status.HTTP_200_OK)
async def sgi_subscription_event(
    request: Request,
    x_sgi_signature: str | None = Header(default=None, alias="X-SGI-Signature"),
    db: Session = Depends(get_db),
) -> dict:
    raw_body = await request.body()
    _verify_signature(raw_body, x_sgi_signature)

    body = SubscriptionEventIn.model_validate_json(raw_body)

    if body.activity_key != _TARGET_ACTIVITY_KEY:
        # Canal dédié à agent_control uniquement — pas générique aux autres
        # activités SGI. Répond succès pour ne pas faire échouer l'appelant sur
        # un événement hors périmètre, mais ne touche rien.
        return {"status": "ignored", "reason": "activity_key hors périmètre"}

    installation = db.scalar(
        select(MCInstallation).where(MCInstallation.external_tenant_id == body.company_id)
    )
    if installation is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "aucune installation existante pour ce company_id (pas d'auto-provisioning)",
        )

    installation.status = "active" if body.enabled else "suspended"
    db.commit()
    return {"status": "ok", "installation_status": installation.status}
