"""Modèles Agent Control V1 — socle tenancy (`installation_id`).

Ajouts **additifs** au schéma core (Contract A intact). Deux tables :

- `mc_installations` : une installation du module dans un tenant de la
  plateforme hôte. `installation_key` préfixe les clés d'agent
  (`<installation_key>:<local_key>`, ADR-0006). Le tenant est résolu serveur
  via `HostTenantPort` (ADR-0003) — jamais depuis un body client.
- `mc_user_mappings` : lie un utilisateur hôte (`external_user_id`) à une
  installation, avec un mapping optionnel vers l'`User` local (mode embarqué).

Aucune colonne `installation_id` n'est ajoutée aux tables V0 (`projects`,
`agents`, `tasks`) dans cette tranche — ça viendra avec les tables métier V1
(ADR-0007). Timezone-aware UTC partout ; pas de cascade destructive sur les
lignes tenant (FK `installation_id` en RESTRICT).
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.core.db import Base
from apps.api.models.tables import Agent, _uuid_pk

# Installation locale déterministe (mode autonome / dev). Doit rester alignée sur
# `integrations.local_adapter.LOCAL_INSTALLATION_ID` (= uuid5(NAMESPACE_URL,
# "agent-control/installation/local")) pour que l'adaptateur DB-backed et les
# tests host_adapter existants restent cohérents.
LOCAL_INSTALLATION_KEY = "local"
LOCAL_INSTALLATION_ID = uuid.UUID("c809b482-c662-5990-a436-999e973b437b")


class MCInstallation(Base):
    """Installation du module Agent Control dans un tenant hôte."""

    __tablename__ = "mc_installations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    # Identifiant tenant côté plateforme hôte (opaque, fourni par l'hôte).
    external_tenant_id: Mapped[str] = mapped_column(String(255), index=True)
    # Préfixe des clés d'agent `<installation_key>:<local_key>` (ADR-0006).
    installation_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    # active | suspended | archived (statut applicatif, fail-closed hors "active").
    status: Mapped[str] = mapped_column(String(20), default="active")
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    feature_flags: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # Archivage doux : jamais de hard-delete d'une installation (historique tenant).
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    mappings: Mapped[list["MCUserMapping"]] = relationship(back_populates="installation")


class MCUserMapping(Base):
    """Lien utilisateur hôte ↔ installation, avec mapping local optionnel."""

    __tablename__ = "mc_user_mappings"
    __table_args__ = (
        # Un `external_user_id` est unique DANS une installation, pas globalement :
        # deux installations peuvent partager la même clé locale sans collision.
        UniqueConstraint(
            "installation_id", "external_user_id", name="uq_user_mapping_installation_external"
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    installation_id: Mapped[uuid.UUID] = mapped_column(
        # RESTRICT : ne jamais supprimer en cascade les mappings d'une installation.
        ForeignKey("mc_installations.id", ondelete="RESTRICT"), index=True
    )
    external_user_id: Mapped[str] = mapped_column(String(255))
    # Mapping vers l'User local (mode embarqué). SET NULL : l'User est soft-deleted,
    # on conserve le mapping mais on relâche la référence.
    local_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Cache profil (dénormalisé, non autoritatif) — l'hôte reste la source de vérité.
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    installation: Mapped["MCInstallation"] = relationship(back_populates="mappings")


class AgentCredential(Base):
    """Credential individuel d'un agent (ADR-0004) — hashé, scopé, rotatif, révocable.

    Le secret brut n'est **jamais** persisté : seul son empreinte SHA-256
    (`secret_hash`) est stockée, exactement comme `PasswordResetToken` /
    l'enrôlement Contract D (`generate_reset_token` + `hash_reset_token`). Le
    secret complet (`<key_prefix>.<random>`) n'est renvoyé qu'une seule fois, à la
    création/rotation (`credential_created`). L'ingest V1 s'authentifie par ce
    credential : le serveur en dérive tenant + agent (jamais depuis un body).

    Machine d'état `credential` (§9) : `active → (revoked|expired)`, terminaux
    immuables. La rotation crée un **nouveau** credential et révoque l'ancien.
    """

    __tablename__ = "agent_credentials"

    id: Mapped[uuid.UUID] = _uuid_pk()
    # CASCADE : les credentials suivent leur agent (jamais du hard-delete d'agent
    # en pratique ; pas un historique métier/audit, un secret d'accès).
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    # Préfixe public opaque (ex. "ac_1a2b3c4d") : identifiant de lookup non secret,
    # transporté en clair dans le secret complet `<key_prefix>.<random>`.
    key_prefix: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    # Empreinte SHA-256 (hex, 64) du secret COMPLET. Le brut n'existe qu'en transit.
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # Scopes explicites (ex. ["ingest", "commands"]). Fail-closed si scope requis absent.
    scopes: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Révocation : non nul = refusé immédiatement au prochain appel (terminal).
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    agent: Mapped["Agent"] = relationship(back_populates="credentials")

    def is_usable(self, *, now: datetime | None = None) -> bool:
        """Vrai si le credential peut agir : ni révoqué, ni expiré (fail-closed).

        Un credential révoqué (`revoked_at`) ou expiré (`expires_at` dépassé) est
        refusé **immédiatement**, sans période de grâce.
        """
        moment = now or datetime.now(UTC)
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and self.expires_at <= moment:
            return False
        return True

    @property
    def status(self) -> str:
        """Statut dérivé (machine `credential`) : active|revoked|expired."""
        if self.revoked_at is not None:
            return "revoked"
        if self.expires_at is not None and self.expires_at <= datetime.now(UTC):
            return "expired"
        return "active"


class AgentEvent(Base):
    """Journal append-only des événements V1 ingérés (§8/§10 du contrat V1).

    Source de vérité historique : PostgreSQL. Les événements sont **persistés
    avant toute diffusion** (l'outbox est écrit dans la même transaction, ADR-0005).
    Idempotence par producteur : `(agent_id, event_id)` unique — rejouer le même
    batch ne duplique rien. `sequence` est monotone par agent (`agents.last_sequence`).

    Aucune cascade destructive : FK `agent_id`/`installation_id` en RESTRICT —
    l'historique n'est jamais effacé par la suppression d'un agent/tenant. Pas de
    prompt/secret brut : la redaction est appliquée en amont par le producteur/service.
    """

    __tablename__ = "agent_events"
    __table_args__ = (
        # Idempotence : un `event_id` est unique DANS la portée d'un agent.
        UniqueConstraint("agent_id", "event_id", name="uq_agent_events_agent_event"),
        # Pagination temporelle tenant-scoped (occurred_at DESC, id DESC).
        Index("ix_agent_events_installation_occurred", "installation_id", "occurred_at"),
        # Reprise/détection de trou par séquence agent.
        Index("ix_agent_events_agent_sequence", "agent_id", "sequence"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    # Tenant (installation) résolu serveur depuis le credential — jamais du body.
    installation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mc_installations.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), index=True
    )
    # Idempotency key du producteur (opaque, ex. uuid).
    event_id: Mapped[str] = mapped_column(String(255))
    sequence: Mapped[int] = mapped_column(BigInteger)
    event_type: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Contextuels (facultatifs). `run_id` : pas de FK ici — `agent_runs` arrive au
    # lot P4 ; on stocke l'uuid brut pour ne pas coupler l'ingest à une table
    # non encore livrée. Idem project_id/task_id (souples, non contraints V1).
    run_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    client_version: Mapped[str | None] = mapped_column(String(60), nullable=True)


class MCOutboxEvent(Base):
    """Outbox transactionnel (ADR-0005) : écrit avec le fait métier, relayé ensuite.

    Le relais (lot SP4/SP6) lit les lignes `pending`, publie vers Redis (canal V1
    `ac:events`) / notifications / webhooks, puis marque `published`. Livraison
    **au moins une fois** ; les consommateurs déduplifient par `event_id`. Un Redis
    indisponible ne perd jamais le fait métier (il reste `pending` en base).
    """

    __tablename__ = "mc_outbox_events"
    __table_args__ = (
        # Le relais balaye les lignes à publier par ordre de création.
        Index("ix_mc_outbox_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    installation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mc_installations.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    # `event_id` d'origine (idempotence côté consommateur / corrélation agent_events).
    event_id: Mapped[str] = mapped_column(String(255), index=True)
    event_type: Mapped[str] = mapped_column(String(80))
    # Topic WS V1 cible (fleet, agent:{id}, run:{id}, …) — validé serveur (§10).
    topic: Mapped[str] = mapped_column(String(160))
    sequence: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Charge à diffuser (le `data` du WsMessageV1), déjà redacted en amont.
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    # pending | published | failed
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentProjectAssignment(Base):
    """Affectation agent↔projet (rôle, capacité, statut) — plan de contrôle P4.

    Une seule affectation **active** par couple `(agent_id, project_id)` : garantie
    par un index unique partiel `WHERE status = 'active'` (migration 0013).
    L'historique des affectations terminées (`status='ended'`) est conservé —
    jamais de hard-delete. Tenant `installation_id` résolu serveur (ADR-0003).
    """

    __tablename__ = "agent_project_assignments"

    id: Mapped[uuid.UUID] = _uuid_pk()
    installation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mc_installations.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    # runner | owner | reviewer | contributor (chaîne libre bornée).
    role: Mapped[str] = mapped_column(String(40), default="runner", server_default="runner")
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # active | ended (fail-closed hors "active").
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentRun(Base):
    """Run borné d'un agent (schéma solution §8) — état serveur-autoritatif.

    `id` = clé de run fournie par le producteur (uuid côté agent) : idempotence
    naturelle et corrélation directe avec `agent_events.run_id` (P3, sans FK).
    L'état suit la machine `run` figée en P0 (`RUN_TRANSITIONS`, §9). Le serveur
    fait foi : une transition non autorisée est refusée (`state_conflict`), un
    état terminal est immuable. Un « retry » crée un NOUVEAU run lié via
    `retry_of_run_id` — il ne rouvre jamais un run terminal.

    Tenant `installation_id` résolu serveur (ADR-0003), jamais d'un body. FK
    projet/tâche en SET NULL : un run survit à la suppression de son projet/tâche
    (trace auditable préservée). `version` = verrou optimiste (transitions).
    """

    __tablename__ = "agent_runs"
    __table_args__ = (
        # Pagination tenant-scoped par récence (created_at DESC, id DESC).
        Index("ix_agent_runs_installation_created", "installation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    installation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mc_installations.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), index=True
    )
    external_run_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    # État courant (machine `run`) : queued|starting|running|waiting_approval|
    # blocked|succeeded|failed|cancelled|timed_out.
    state: Mapped[str] = mapped_column(String(30), default="queued", server_default="queued")
    retry_of_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    attempt: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    steps: Mapped[list["AgentRunStep"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="AgentRunStep.sequence",
    )


class AgentRunStep(Base):
    """Étape / tool call d'un run (schéma solution §8) — unique `(run_id, sequence)`.

    Aucun prompt/secret brut : uniquement des résumés (`input_summary` /
    `output_summary`). `state` simple : started|succeeded|failed (l'état complet
    du run vit dans `AgentRun`, pas ici).
    """

    __tablename__ = "agent_run_steps"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_agent_run_steps_run_sequence"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    step_type: Mapped[str] = mapped_column(String(40), default="step", server_default="step")
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state: Mapped[str] = mapped_column(String(20), default="started", server_default="started")
    tool_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    step_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    run: Mapped["AgentRun"] = relationship(back_populates="steps")
