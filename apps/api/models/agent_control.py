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
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.core.db import Base
from apps.api.models.tables import _uuid_pk

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
