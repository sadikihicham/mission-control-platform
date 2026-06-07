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
