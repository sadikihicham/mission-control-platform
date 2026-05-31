"""Couche base de données — SQLAlchemy 2.x.

Engine/session créés **paresseusement** : importer les modèles (Base) ne doit
pas exiger un driver DB ni une connexion. Les MODÈLES sont la responsabilité de
l'agent `db-core` (Contract A).
"""
from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from apps.api.core.config import settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


class Base(DeclarativeBase):
    """Base déclarative partagée par tous les modèles (db-core)."""


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(), autoflush=False, autocommit=False, future=True
        )
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Dépendance FastAPI : ouvre une session par requête."""
    db = get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()
