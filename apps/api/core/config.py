"""Configuration centrale de l'API — chargée depuis l'environnement.

Noms d'env figés dans .mission-control/CONTRACTS.md (décisions verrouillées).
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Identité
    app_name: str = "Project Mission Control API"
    environment: str = "development"

    # Infra (Contract — voir CONTRACTS.md)
    database_url: str = "postgresql+psycopg://mc:mc@postgres:5432/mission_control"
    redis_url: str = "redis://redis:6379/0"

    # Sécurité
    jwt_secret: str = "dev-insecure-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12

    # Ingest heartbeat (Contract D)
    mc_ingest_token: str = "dev-ingest-token"

    # Agent Control V1 — sélection de l'adaptateur hôte (ADR-0001, contrat V1 §13).
    # `local` = mode embarqué/autonome résolu contre le registre DB (mc_installations
    # / mc_user_mappings). `jwt` = hôte réel (ADR-0010, ex. SGI) dont le JWT est
    # validé directement, sans passer par le JWT/les utilisateurs V0 de ce service.
    # Surchargeable via l'env MC_HOST_ADAPTER.
    mc_host_adapter: str = "local"

    # Adaptateur `jwt` (ADR-0010) : secret partagé avec la plateforme hôte pour
    # valider SES JWT (HS256, claims `sub`/`company_id`/`role`). Distinct de
    # `jwt_secret` ci-dessus, qui signe les JWT propres à ce service (V0).
    # Surchargeable via SGI_JWT_SECRET / SGI_JWT_ALGORITHM.
    sgi_jwt_secret: str = "dev-insecure-change-me"
    sgi_jwt_algorithm: str = "HS256"

    # Pont d'activation par tenant (ADR-0011) : secret partagé HMAC pour vérifier
    # POST /integrations/sgi/subscription-events (webhook sortant SGI → bascule de
    # `mc_installations.status`). Distinct de sgi_jwt_secret (identité utilisateur)
    # — celui-ci authentifie un appel machine-à-machine, jamais un utilisateur.
    # Surchargeable via SGI_WEBHOOK_SECRET.
    sgi_webhook_secret: str = "dev-insecure-change-me"

    # Ingest V1 (contrat V1 §8) : taille maximale d'un batch d'événements accepté
    # par POST /agent-control/v1/ingest/events. Au-delà → validation_error (422).
    mc_event_batch_max: int = 200

    # Contrôle P5 — file de commandes (contrat V1 §8, schéma solution §16).
    # Long poll borné de `GET /agent-control/v1/agent/commands` : durée maximale
    # d'attente serveur (secondes) quand aucune commande n'est livrable. Le client
    # peut demander moins via `?wait=`. Défaut 0 = réponse immédiate (les tests et
    # les producteurs bas-débit n'attendent pas). Surchargeable via l'env.
    mc_command_long_poll_seconds: int = 0
    # TTL par défaut d'une commande soumise (secondes) : au-delà, une commande
    # encore `queued|delivered` est marquée `expired` et n'est plus livrée.
    mc_command_default_ttl_seconds: int = 900
    # SLA par défaut d'une demande d'approbation (secondes) : au-delà, `expired`
    # (aucune décision positive possible — la commande liée est annulée).
    mc_approval_default_ttl_seconds: int = 3600
    # Effet appliqué quand AUCUNE politique ne correspond à `(agent, action)`.
    # `allow` (défaut) : la capacité `operate` gouverne déjà l'accès, les politiques
    # servent à restreindre/encadrer des actions ciblées. Basculer sur `deny` pour
    # un mode fail-closed strict (rien n'est autorisé sans politique explicite).
    mc_policy_default_effect: str = "allow"

    # Compatibilité Contract D (ADR-0002/0004) : autorise le secret global partagé
    # `MC_INGEST_TOKEN` pour l'enrôlement/heartbeat V0. True = compat maintenue (les
    # producteurs V0 fonctionnent inchangés). En production embarquée, désactiver
    # (fail-closed) pour n'accepter que les credentials individuels V1. N'affecte
    # PAS l'ingest V1, qui exige toujours un credential agent hashé.
    mc_global_ingest_enabled: bool = True

    # Rate-limit login (interne, hors CONTRACTS.md) : IP du peer TCP direct par défaut.
    # `X-Forwarded-For` n'est honoré que si ce peer figure ici (reverse proxy de
    # confiance placé devant l'API) — sinon un client peut forger l'en-tête pour
    # obtenir un nouveau compteur à chaque requête et contourner la limite. Vide par
    # défaut = ne jamais faire confiance à l'en-tête. Accepte des IP littérales ou des
    # noms résolus par DNS (ex. `["caddy"]` en prod co-hébergée, cf. auth._is_trusted_proxy
    # et docker-compose.prod-fronted.yml). Surchargeable via l'env TRUSTED_PROXIES (JSON).
    trusted_proxies: list[str] = []

    # Source des statuts du skill mission-control (fast-path lecture seule).
    # Alimente le dashboard tant que la pipeline DB/ingest (M3) n'est pas livrée.
    mc_status_dir: str = ".mission-control/status"
    mc_stale_seconds: int = 30

    # Intégration GitHub (optionnelle : augmente la limite de l'API GitHub).
    github_token: str | None = None

    # CORS (front Next.js). Plusieurs ports : Next bascule sur 3001/3002 si 3000
    # est occupé. Surchargeable via l'env CORS_ORIGINS (JSON).
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:3100",
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
