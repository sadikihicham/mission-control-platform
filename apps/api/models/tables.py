"""Modèles SQLAlchemy 2.x — schéma core MVP (Contract A).

Owner : agent `db-core`. Consommé par `auth` (User) et `api` (tous).
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
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

if TYPE_CHECKING:
    # Référence croisée pour la relation `Agent.credentials` (défini dans
    # `agent_control.py`). Import type-only : aucun cycle à l'exécution.
    from apps.api.models.agent_control import AgentCredential


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
    # Tenant Agent Control V1 (extension ADDITIVE, migration 0016) : nullable en
    # base pour compat V0 (ADR-0007), obligatoire au niveau applicatif pour toute
    # lecture/mutation V1. Résolu serveur depuis le JWT (ADR-0003), jamais d'un
    # body. RESTRICT : jamais de cascade destructive sur une installation tenant.
    installation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mc_installations.id", ondelete="RESTRICT"), nullable=True, index=True
    )
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

    # --- Registre Agent Control V1 (extensions ADDITIVES, migration 0011) ---
    # Toutes nullables/défaultées : un producteur V0 (heartbeat/sync fichier) ne
    # renseigne jamais ces colonnes et garde exactement son comportement. Le
    # registre V1 (route `manage_agents`) les gère ; l'ingest V1 fait avancer
    # `last_sequence` et `last_heartbeat` de façon monotone (cf. ADR-0009).
    #
    # Tenant V1 : nullable en base (compat V0, ADR-0007), obligatoire au niveau
    # applicatif pour toute donnée V1. Résolu serveur depuis le credential/JWT
    # (ADR-0003), jamais depuis un body. RESTRICT : jamais de cascade destructive
    # sur une installation tenant.
    installation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mc_installations.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    runtime: Mapped[str | None] = mapped_column(String(60), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(60), nullable=True)
    client_version: Mapped[str | None] = mapped_column(String(60), nullable=True)
    environment: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Capacités déclarées de l'agent (ex. ["code", "shell"]) — liste validée.
    capabilities: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    # Statut REGISTRE (distinct de `state` live) : active|suspended|revoked|archived.
    # Fail-closed hors "active" côté ingest/commandes (lot ultérieur).
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
    registered_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Plus haute séquence ingérée pour cet agent : rejette tout événement V1
    # d'une séquence ≤ (monotone, ne régresse jamais — §8/§10 du contrat V1).
    last_sequence: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project | None"] = relationship(back_populates="agents")
    credentials: Mapped[list["AgentCredential"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )


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
    # Tenant Agent Control V1 (extension ADDITIVE, migration 0016) : nullable en
    # base pour compat V0 (ADR-0007). Redondant avec `project.installation_id`
    # mais matérialisé pour borner les requêtes tâche par tenant sans jointure
    # systématique. Cohérence garantie côté service (une tâche hérite du tenant
    # de son projet). RESTRICT : jamais de cascade destructive sur un tenant.
    installation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mc_installations.id", ondelete="RESTRICT"), nullable=True, index=True
    )
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
