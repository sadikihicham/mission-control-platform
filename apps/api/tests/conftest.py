"""Harness de tests d'intégration.

Crée le schéma + seed sur une base de TEST éphémère (DATABASE_URL doit contenir
'test' — garde-fou pour ne jamais wiper une vraie base). TestClient sans
context manager → le lifespan (tâches realtime) n'est pas démarré, donc pas de
dépendance à Redis pour les tests HTTP.
"""
import os

# Defaults sûrs (CI/conteneur peuvent surcharger). On NE force PAS DATABASE_URL :
# il doit pointer une base de test explicite.
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("MC_INGEST_TOKEN", "test-ingest")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from apps.api import models  # noqa: E402,F401  (enregistre les tables)
from apps.api.core.config import settings  # noqa: E402
from apps.api.core.db import Base, get_engine, get_sessionmaker  # noqa: E402
from apps.api.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    if "test" not in settings.database_url:
        raise RuntimeError(
            f"Refus : DATABASE_URL doit pointer une base de TEST (contient 'test'). Reçu: {settings.database_url}"
        )
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    _seed_role_accounts()
    from apps.api.seed import run as seed_run
    seed_run()
    yield
    Base.metadata.drop_all(engine)


def _seed_role_accounts() -> None:
    """Comptes de rôle utilisés par admin_token/pm_token/viewer_token — propres
    aux tests, indépendants du seed dev (`apps.api.seed`) qui ne crée plus aucun
    compte de démo."""
    from apps.api.core.security import hash_password
    from apps.api.models import User

    Session = get_sessionmaker()
    with Session() as db:
        for email, pwd, role in [
            ("admin@mc.local", "admin", "admin"),
            ("pm@mc.local", "pm", "pm"),
            ("viewer@mc.local", "viewer", "viewer"),
        ]:
            if not db.query(User).filter_by(email=email).first():
                db.add(User(email=email, hashed_password=hash_password(pwd), role=role))
        db.commit()


@pytest.fixture
def db():
    Session = get_sessionmaker()
    with Session() as s:
        yield s


@pytest.fixture
def client():
    return TestClient(app)


def _token(client: TestClient, email: str, password: str) -> str:
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def make_user(db):
    """Crée un utilisateur jetable (email unique) — isole les tests qui mutent
    le mot de passe sans toucher aux comptes seedés partagés."""
    import uuid as _uuid

    from apps.api.core.security import hash_password
    from apps.api.models import User

    def _make(password: str = "initial1", role: str = "admin") -> str:
        email = f"reset-{_uuid.uuid4().hex[:8]}@mc.local"
        db.add(User(email=email, hashed_password=hash_password(password), role=role))
        db.commit()
        return email

    return _make


@pytest.fixture
def admin_token(client):
    return _token(client, "admin@mc.local", "admin")


@pytest.fixture
def pm_token(client):
    return _token(client, "pm@mc.local", "pm")


@pytest.fixture
def viewer_token(client):
    return _token(client, "viewer@mc.local", "viewer")


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
