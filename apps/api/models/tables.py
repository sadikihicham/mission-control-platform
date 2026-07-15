"""Modèles SQLAlchemy 2.x — schéma core MVP (Contract A).

Owner : agent `db-core`. Consommé par `auth` (User) et `api` (tous).
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.core.db import Base
from apps.api.models.enums import AgentState, ProjectStatus


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="admin")
    full_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Civilité : "mr" | "mrs" | "miss" — pilote le message d'accueil genré.
    civility: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # Désactivation = soft-delete (rubrique Administration) : jamais de hard-delete
    # d'un compte, un utilisateur inactif garde son historique mais ne peut plus
    # se connecter (cf. routers/auth.py login() + get_current_user()).
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = _uuid_pk()
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="project_status"), default=ProjectStatus.in_dev
    )
    progress: Mapped[int] = mapped_column(Integer, default=0)
    repo: Mapped[str | None] = mapped_column(String(255), nullable=True)  # "owner/name" GitHub
    # Projet de démonstration (vitrine d'orchestration) : persisté en DB mais non
    # éditable via l'API (le seed est la source, cf. services/projects.py). Ne
    # doit jamais être créé en production (seed refusé si ENVIRONMENT=prod).
    is_seed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    agents: Mapped[list["Agent"]] = relationship(back_populates="project")
    tasks: Mapped[list["Task"]] = relationship(back_populates="project")


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = _uuid_pk()
    agent_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    state: Mapped[AgentState] = mapped_column(
        Enum(AgentState, name="agent_state"), default=AgentState.idle
    )
    task: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    module: Mapped[str | None] = mapped_column(String(120), nullable=True)
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    blocker: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Identité par agent (Contract D) : hash SHA-256 du token émis à l'enrôlement.
    # None = agent pas encore enrôlé, le secret partagé MC_INGEST_TOKEN fait encore foi.
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    token_issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project | None"] = relationship(back_populates="agents")


class Task(Base):
    """Tâche ou sous-tâche persistée (hiérarchie à un niveau via `parent_id`).

    Étend Contract A de manière additive (migration `0010`) pour rendre la
    structure projet→tâche→sous-tâche réelle en base, en remplacement des
    fixtures Python statiques. Les TAUX/ÉTATS affichés restent superposés en
    live depuis la flotte d'agents (`agent_key`), la structure vient de la DB.
    """

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    # Sous-tâche : pointe la tâche parente (un seul niveau). NULL = tâche racine.
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True, index=True
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    # Clé naturelle stable par projet (ex. "M0", "M0.1") : sert d'ancre de seed
    # idempotent et d'identifiant stable côté frontend.
    code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    module: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="todo")
    progress: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Agent porteur attendu (clé globale Contract D, pas une FK) : l'état/taux
    # est superposé en live si un agent de cette clé existe dans la flotte.
    agent_key: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship(back_populates="tasks")
    subtasks: Mapped[list["Task"]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="Task.position",
        single_parent=True,
    )
    parent: Mapped["Task | None"] = relationship(back_populates="subtasks", remote_side=[id])


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PasswordResetToken(Base):
    """Jeton de réinitialisation de mot de passe — usage unique, à durée de vie courte.

    On ne stocke que le **hash** (SHA-256) du jeton brut ; le brut n'existe qu'en
    transit (lien envoyé à l'utilisateur). `used_at` non nul = déjà consommé.
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
