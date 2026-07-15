# ADR-0007 — Extensions du Contract A additives et versionnées

Statut : accepté (SP1, Gate P0)
Date : 2026-07-15

## Contexte

V1 a besoin de registre agent enrichi, runs, étapes, commandes, approbations,
politiques, usage, budgets, alertes, audit, outbox, installations et mappings
utilisateur. Le Contract A (schéma DB, `.mission-control/CONTRACTS.md`) est gelé :
« changer une forme = décision cassante délibérée ».

## Décision

Toute évolution du schéma pour V1 est **strictement additive et versionnée** :

- **aucune** colonne existante n'est renommée, retypée ou supprimée ; **aucune**
  route/payload existant n'est muté ;
- les colonnes ajoutées aux tables existantes (`projects`, `agents`, `tasks`) sont
  **nullable** pour préserver les lignes V0 ; `installation_id`/`company_id` est
  obligatoire **applicativement** pour les nouvelles données, nullable en base ;
- les nouvelles entités vont dans de **nouvelles tables** ;
- chaque changement est couvert par les tests de compatibilité V0 (ADR-0002).

Tête Alembic actuelle : `0007_drop_company_id`. Les migrations V1 démarrent à
`0008` (lot SP2 `agent-control-data` — SP1 n'écrit aucune migration).

### Migrations additives nécessaires (à réaliser par SP2, ≥ 0008)

| # | Contenu |
|---|---|
| 0008 | `mc_installations`, `mc_user_mappings` |
| 0009 | `agents` +colonnes : `installation_id`, `display_name`, `description`, `runtime`, `provider`, `client_version`, `environment`, `capabilities` (JSONB), `status` (registre), `registered_by`, `registered_at`, `revoked_at`, `last_sequence` |
| 0010 | `agent_credentials` |
| 0011 | `agent_project_assignments` |
| 0012 | `projects` +colonnes : `external_ref`, `owner_user_ref`, `environment`, `archived_at`, `company_id` (nullable) |
| 0013 | `tasks` +colonnes : `parent_id`, `description`, `priority`, `progress`, `position`, `acceptance_criteria`, `due_at`, `started_at`, `completed_at`, `updated_at`, `archived_at` (statut : ensemble validé, lecture compatible des valeurs historiques) |
| 0014 | `agent_runs` |
| 0015 | `agent_run_steps` |
| 0016 | `agent_events` (append-only, idempotence par producteur/séquence) |
| 0017 | `agent_commands` |
| 0018 | `approval_requests` |
| 0019 | `agent_policies` |
| 0020 | `agent_usage_records` |
| 0021 | `agent_budgets` |
| 0022 | `agent_alerts` |
| 0023 | `mc_audit_logs` |
| 0024 | `mc_outbox_events` |

Le numérotage est indicatif ; SP2 réconcilie les têtes avant de figer. Regrouper
plusieurs tables par migration est acceptable si additif et testé.

## Conséquences

- Aucune rupture V0 ; rollback simple (drop des nouvelles tables/colonnes).
- `company_id`/`installation_id` nullable en base ⇒ le filtre tenant est
  **applicatif** (ADR-0003), à couvrir par des tests cross-tenant (gate P1).

## Alternatives rejetées

- `NOT NULL` immédiat sur `installation_id` : casse les lignes V0 existantes.
  Rejeté au profit du nullable + garde applicative.
