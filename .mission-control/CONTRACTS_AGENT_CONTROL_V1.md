# Contrat Agent Control V1 — intégration hôte, routes, événements, tenancy

> **Statut** : figé au Gate P0 (SP1). Source de vérité du module Agent Control.
> **Compatibilité** : les contrats V0 A–E (`.mission-control/CONTRACTS.md`) restent
> intacts et prioritaires pour tout producteur/écran existant. En cas de
> contradiction : **A–E pour la compatibilité V0**, **ce contrat pour le neuf**,
> puis code et analyse.
> **Primitives exécutables** : `apps/api/integrations/**` (importables, testées).
> **Exemples** : `docs/agent-control/examples/v1/examples.json`.
> **ADR** : `docs/agent-control/adr/**`.

Toute extension du Contract A (schéma DB) est **additive et versionnée**, jamais
une mutation — voir §12 et `docs/agent-control/adr/0007-extensions-additives-contract-a.md`.

---

## 1. Périmètre et principes

Agent Control est un **bounded context** de gouvernance d'agents monté dans une
plateforme métier hôte. Il ne possède ni l'identité, ni le tenant, ni les rôles
globaux, ni le shell : il les **consomme via des ports** (§3). Invariants durs :

1. Aucune identité ni permission ne vient d'un body utilisateur — tout est résolu
   serveur depuis le credential hôte (§3, §4).
2. Le tenant est résolu serveur, jamais accepté depuis un body (§11).
3. Les credentials agents sont individuels, hashés, scopés, rotatifs, révocables (§9, ADR-0004).
4. PostgreSQL est la source de vérité ; Redis est un transport ; publication via **outbox** (§10, ADR-0005).
5. Toute liste V1 est **paginée par curseur et ordonnée** (§7).
6. Toute erreur V1 porte un **code machine stable** en plus du message humain (§6).
7. Toute diffusion WS exige **tenant + topic autorisés** (§10).
8. Fail-closed partout : identité, tenant ou capacité manquante ⇒ refus.

---

## 2. Formes V0 gelées et dérives documentées

Les formes suivantes sont **gelées telles quelles** par
`apps/api/tests/test_agent_control_v0_freeze.py`. SP1 ne les corrige pas ; il
empêche leur rupture accidentelle. Les corrections éventuelles seront des
décisions explicites d'un autre lot avec adaptateur de compatibilité.

| # | Dérive | Forme HTTP (Contract C, `lib/api.ts`) | Forme ingest/WS (Contract D/E) | Décision |
|---|---|---|---|---|
| D1 | Identifiant d'agent | `agent` | `agent_key` | Gelé. Les deux coexistent ; aucun renommage. Le DTO V1 réintroduit `agent_key` explicitement. |
| D2 | Horodatage d'agent | `updated_at` | `last_heartbeat` | Gelé. Les deux coexistent. |
| D3 | KPIs dashboard | `DashboardStats` = **7 champs** (`agents_total, agents_active, agents_blocked, agents_stale, agents_done, agents_error, overall_progress`) | idem via `stats.update` | État réel = 7. `AGENTS.md` en décrit 5 → **doc périmée**, à corriger par le lead (§14). |
| D4 | `company_id` | retiré (migration `0007_drop_company_id`) | — | `AGENTS.md` le décrit encore → **doc périmée**. V1 réintroduit l'isolation via `installation_id` (ADR-0003), pas via l'ancienne colonne. |
| D5 | CI | gate 100 % locale (`ruff`+`pytest`+lint/build web), Actions retirée (PR #11) | — | `AGENTS.md` décrit encore GitHub Actions → **doc périmée**. |
| D6 | Enveloppe d'erreur | `{"detail": ...}` (défaut FastAPI) | idem | Gelé pour V0. L'enveloppe V1 `{"error": {...}}` (§6) ne s'applique **que** sous `/agent-control/v1`. |
| D7 | Canal Redis / WS | `/ws`, canal `mc:events`, types `agent.update|agent.stale|stats.update|refresh` | idem | Gelé. V1 utilise `/agent-control/ws` + canal `ac:events` + types du catalogue (§10) — **jamais** le même canal. |

Producteurs V0 préservés : CLI `mc-platform`, fichiers `.mission-control/status/`,
`POST /agents/heartbeat` avec secret partagé (opt-in enrôlement). Voir ADR-0002.

---

## 3. Ports d'intégration hôte

Interfaces `Protocol` dans `apps/api/integrations/ports.py`. Adaptateur de
référence `local` dans `apps/api/integrations/local_adapter.py`. Sélection par
`MC_HOST_ADAPTER` (config, pas de `if embedded` dans le domaine — ADR-0001).

| Port | Rôle | Ne fait jamais |
|---|---|---|
| `HostIdentityPort` | `resolve_identity(credential) -> UserRef` : valide JWT/session hôte, retourne `external_user_id`, email, nom, statut. | recopier mot de passe / secret SSO |
| `HostTenantPort` | `resolve_tenant(user, installation_key) -> (InstallationRef, TenantRef)` ; `user_belongs_to_tenant(...)`. | accepter un tenant depuis un body |
| `HostPermissionPort` | `capabilities_for(user, tenant) -> frozenset[Capability]` : traduit permissions hôte → capacités module. | laisser l'UI décider seule (l'API vérifie toujours) |
| `HostNavigationPort` | `register_module(base_path, routes, badges)` ; `open_route(path)`. | dupliquer topbar/profil/langue/logout |
| `HostNotificationPort` | `notify(recipient, subject, body, idempotency_key) -> id` : notif in-app/email idempotente. | dupliquer sur même `idempotency_key` |

**Adaptateur local** (`LocalHostAdapter`) : réutilise `User`, le JWT local, le
RBAC existant ; expose un tenant unique `local` (installation déterministe, pas de
ligne DB requise). Fail-closed : user absent/inactif → `IdentityUnresolved` ;
installation désactivée ou clé inconnue → `TenantUnresolved` ; rôle inconnu →
aucune capacité.

---

## 4. HostContext

`apps/api/integrations/host_context.py` — modèle **immuable**, résolu serveur,
passé en paramètre explicite aux services (jamais reconstruit depuis un body).

```
HostContext:
  request_id: str                    # corrélation (repris dans erreurs/audit/events)
  installation: InstallationRef      # id, installation_key, external_tenant_id, status
  tenant: TenantRef                  # external_tenant_id, name, slug, status, feature_flags
  user: UserRef                      # external_user_id, local_user_id?, email?, display_name?, status
  capabilities: frozenset[Capability]
  locale: str = "fr"                 # fr|en|ar
  timezone: str = "UTC"              # IANA (ex. Asia/Dubai)
```

`installation_key` préfixe les clés d'agent : `<installation_key>:<local_key>`
(ADR-0006). Exemple JSON : clé `context_response`.

---

## 5. Capacités et matrice capacités × routes

Capacités (`apps/api/integrations/capabilities.py`) :
`view`, `operate`, `manage_agents`, `manage_projects`, `approve`, `view_costs`, `admin`.

Mapping RBAC hôte → capacités (adaptateur local, ADR-0008) :

| Rôle hôte | Capacités |
|---|---|
| `viewer` | view |
| `developer` | view, operate |
| `pm` | view, operate, manage_projects, approve, view_costs |
| `cto` | view, operate, manage_projects, manage_agents, approve, view_costs |
| `admin` | toutes |

Un rôle inconnu/absent → **aucune** capacité (fail-closed). Mapping monotone avec
la hiérarchie existante `viewer<developer<pm<cto<admin`.

**Matrice capacités × routes** : autoritative dans
`apps/api/integrations/permissions.py::ROUTE_CAPABILITIES`, exhaustive sur les
routes §7, vérifiée par `test_agent_control_permissions.py`. Chaque route exige
**une** capacité, ou est authentifiée par **credential agent** (`AGENT_CREDENTIAL`,
routes `/ingest/*` et `/agent/commands*` — hors RBAC utilisateur). Extrait :

| Route | Capacité |
|---|---|
| `GET /agent-control/v1/context` · `/capabilities` · `/health` | view |
| `POST /agent-control/v1/installations/{id}/activate` | admin |
| `GET /agents` · `/agents/{id}` · `/agents/{id}/health` | view |
| `POST /agents` · `PATCH /agents/{id}` · credentials · suspend/resume/archive | manage_agents |
| `POST /ingest/events` · `/ingest/heartbeat` · `GET /agent/commands` · ack · result | agent credential |
| `GET /projects*` · `/tasks/{id}` · `/runs*` | view |
| `POST/PATCH/DELETE /projects*` · `POST /projects/{id}/tasks` · `PATCH /tasks/{id}` · `/assign` | manage_projects |
| `POST /runs/{id}/commands` | operate |
| `POST /approvals/{id}/approve|reject` | approve |
| `GET /approvals*` · `/policies` · `/alerts` · `/dashboard` · `/audit` | view |
| `POST/PATCH/DELETE /policies*` | admin |
| `POST /alerts/{id}/acknowledge|resolve` | operate |
| `GET /usage` · `/budgets` · `POST/PATCH /budgets` · `/reports/export.csv` | view_costs |

L'UI **peut** masquer une action ; l'API **vérifie toujours** côté serveur.

---

## 6. Enveloppe d'erreur, codes et statuts

Sous `/agent-control/v1` uniquement (`apps/api/integrations/envelopes.py`) :

```json
{ "error": { "code": "permission_denied", "message": "…", "request_id": "…", "details": {} } }
```

`code` est une valeur de contrat stable — jamais renommée ni recyclée.
Correspondance indicative code → HTTP (`HTTP_STATUS_BY_CODE`) :

| Code | HTTP | Sens |
|---|---|---|
| `unauthenticated` | 401 | identité absente/invalide |
| `credential_invalid` | 401 | credential agent invalide |
| `credential_revoked` | 403 | credential révoqué/expiré |
| `permission_denied` | 403 | capacité requise absente |
| `tenant_required` | 403 | aucun contexte tenant résolu |
| `tenant_forbidden` | 403 | accès hors tenant courant |
| `not_found` | 404 | ressource absente **dans le tenant** |
| `validation_error` | 422 | corps/paramètres invalides |
| `conflict` | 409 | conflit d'unicité générique |
| `idempotency_conflict` | 409 | clé d'idempotence rejouée avec charge différente |
| `sequence_out_of_order` | 409 | séquence ancienne/dupliquée |
| `state_conflict` | 409 | transition d'état interdite |
| `approval_required` | 409 | action bloquée en attente de décision |
| `budget_exceeded` | 409 | dépassement budget bloquant |
| `rate_limited` | 429 | quota dépassé |
| `not_implemented` | 501 | route V1 déclarée mais non encore livrée |
| `internal_error` | 500 | erreur serveur |

V0 conserve `{"detail": ...}` (dérive D6). Ne pas mélanger.

---

## 7. Routes V1 et pagination

Base : `/agent-control/v1`. Liste complète et capacité associée : §5 + `ROUTE_CAPABILITIES`.

**Pagination par curseur** (toutes les listes) — `PageInfo` :

- requête : `?cursor=<opaque>&limit=<1..200, défaut 50>` + filtres bornés (voir ci-dessous) ;
- réponse : `{ "items": [...], "page_info": { "next_cursor": str|null, "limit": int, "has_more": bool } }` ;
- **ordre stable** obligatoire ; `next_cursor` opaque (base64url) encode la dernière clé de tri ; le client ne fabrique jamais de curseur ;
- clés de tri par collection : listes temporelles (runs, events/timeline, audit, usage, alerts) = `(occurred_at|created_at DESC, id DESC)` ; registres (agents, projects, tasks, policies, budgets) = `(created_at DESC, id DESC)` ; timeline = `(sequence ASC)`.

**Filtres bornés** (enumérés, jamais champ libre non validé) — exemples : agents
`status`, `state`, `environment`, `project_id` ; runs `state`, `project_id`,
`agent_id`, `from`/`to` ; usage/budgets `scope`, `period`, `project_id`,
`agent_id` ; audit `actor_type`, `action`, `from`/`to`.

DTO d'entrée/sortie par domaine : formes de référence en §13 + exemples JSON
(`examples.json`). Le tenant n'apparaît **jamais** en query/body : il vient du contexte.

---

## 8. Ingest V1 (authentifié par credential agent)

- `POST /ingest/events` — **batch borné** (`MC_EVENT_BATCH_MAX`, défaut 200),
  séquencé et idempotent. Corps : `{ "events": [EventEnvelopeV1, ...] }`.
  Réponse : `{ "accepted", "duplicates", "rejected", "last_sequence" }`.
- `POST /ingest/heartbeat` — état courant tenant-aware (voir `ingest_heartbeat_v1`).
- `GET /agent/commands` — long poll borné (`MC_COMMAND_LONG_POLL_SECONDS`).
- `POST /agent/commands/{id}/ack` · `POST /agent/commands/{id}/result`.

Serveur (schéma §9) : authentifie le credential, **dérive tenant/agent**, refuse
un `agent_key` différent de l'identité (`permission_denied`), déduplique
`event_id` (`idempotency_conflict`), rejette une séquence ancienne/dupliquée
(`sequence_out_of_order`) via `agents.last_sequence`, **persiste avant
publication** (outbox), n'autorise jamais le payload à changer son tenant.

---

## 9. Machines d'état

`apps/api/integrations/state_machines.py`. États terminaux **immuables** ; un
retry crée une nouvelle entité liée (`retry_of_run_id`), il ne rouvre rien.

- **Run** : `queued → starting → running → (waiting_approval|blocked) → running → (succeeded|failed|cancelled|timed_out)`. Terminaux : succeeded, failed, cancelled, timed_out.
- **Commande** : `queued → delivered → acknowledged → (succeeded|failed)` ; `queued|delivered → (expired|cancelled)`. Une commande risquée reste `queued` avec `approval_request_id` jusqu'à décision.
- **Approbation** : `pending → (approved|rejected|expired|cancelled)`. Décision définitive, version optimiste, acteur + commentaire audités.
- **Alerte** : `open → acknowledged → resolved` ; `open → resolved`. Terminal : resolved.
- **Credential** : `active → (revoked|expired)`. Terminaux : revoked, expired. La rotation crée un **nouveau** credential et révoque l'ancien.

---

## 10. Temps réel V1, événements, idempotence, reprise, redaction

**Endpoint** : `/agent-control/ws?token=<host-jwt>&installation_id=<uuid>`.
Distinct de `/ws` V0. Le serveur valide identité + tenant + capacité avant
d'accepter, puis vérifie **chaque** topic.

**Enveloppe événement V1** (`EventEnvelopeV1`) — producteur → serveur :
obligatoires `event_id, agent_key, sequence, event_type, occurred_at, payload` ;
contextuels `run_id, project_id, task_id, trace_id, client_version`. Le serveur
ajoute `tenant_id` (installation), `received_at`, `request_id` à la persistance
(`agent_events`).

**Message WS** (`WsMessageV1`) : `{ id, type, tenant_id, topic, sequence, data, occurred_at }`.
Toujours estampillé `tenant_id` ; **jamais** diffusé sans tenant ni topic autorisé.

**Topics** (`events_catalog.py`) : `fleet`, `approvals` (scalaires),
`project:{id}`, `agent:{id}`, `run:{id}` (paramétrés). Le client ne choisit jamais
un tenant arbitraire.

**Types d'événements** : catalogue gelé `EVENT_TYPES` (agent.*, run.*,
run.step.*, command.*, approval.*, alert.*, usage.recorded, budget.*). Disjoint
des types V0 (`agent.update|agent.stale|stats.update|refresh`).

**Idempotence / séquence / reprise** : `event_id` unique par producteur ;
`sequence` monotone par agent (`agents.last_sequence`) ; reprise via
`last_event_id` (rejoue depuis `agent_events`) ou refresh HTTP si trou détecté
(discontinuité de `sequence`). Heartbeat WS, backoff avec jitter, fallback polling.

**Outbox** (ADR-0005) : écriture métier + `mc_outbox_events` dans la **même**
transaction, puis relais vers Redis/notifications/webhooks ; un Redis indisponible
ne perd jamais le fait métier.

**Redaction** : aucun prompt, secret, token, output sensible brut par défaut dans
`payload`, `data`, logs ou audit (`before/after` redacted, IP hashée).

---

## 11. Conventions tenant (host-owned)

- Le tenant est **résolu serveur** via `HostTenantPort` depuis le credential/JWT +
  `installation_id`. Jamais lu depuis un query/body (ADR-0003).
- Chaque service V1 reçoit un `HostContext` explicite et filtre **toutes** ses
  requêtes par `installation_id` (HTTP, WS, cache, export).
- Nouvelles données V1 : `installation_id` (≈ `company_id`) obligatoire au niveau
  applicatif ; colonne **nullable** en base pour compatibilité V0 (ADR-0007).
- Fail-closed : contexte tenant absent → `tenant_required` (403) ; ressource d'un
  autre tenant → `not_found` (404, pas 403, pour ne pas divulguer l'existence).
- Une entité introuvable **dans le tenant courant** répond `not_found`, jamais la
  donnée d'un autre tenant.

---

## 12. Extensions du Contract A (additives, versionnées)

Aucune mutation de colonne/route/payload existant. Ajouts additifs seulement
(ADR-0007). Tables existantes conservées ; `agent_key` reste global et unique,
généré `<installation_key>:<local_key>` (ADR-0006). Détail des colonnes/tables et
liste de migrations (0008+) : §13 + `docs/agent-control/adr/0007-...` + handoff SP1.

---

## 13. DTO de référence (formes de contrat)

Formes minimales que les DTO V1 doivent respecter. Exemples valides et validés :
`docs/agent-control/examples/v1/examples.json` (test
`test_agent_control_v1_contracts.py`). L'argent est une **chaîne décimale** (fils
non applicable ici : coûts fournisseurs multi-devises), jamais un float.

- **Contexte** : `context_response` (= HostContext) ; `capabilities_response`.
- **Registre** : `agent_out` (id, agent_key, installation_id, display_name,
  runtime, provider, client_version, environment, capabilities[], status registre
  `active|suspended|revoked|archived`, state live, last_heartbeat, last_sequence,
  registered_by/at, revoked_at, project_ids[], created/updated_at) ;
  `agent_create` (local_key → agent_key dérivé) ; `credential_created` (secret
  **affiché une seule fois**, key_prefix, scopes, expires_at).
- **Orchestration** : `run_out` (state machine §9, version optimiste,
  retry_of_run_id) ; `run_step` (sequence, step_type, tool_name, durée, résumés
  redacted) ; timeline = liste paginée de steps/events.
- **Contrôle** : `command_out` (status machine §9, idempotency_key,
  approval_request_id) ; `approval_out` (risk_level, version, décision auditée) ;
  `policy_out` (scope, effect `allow|deny|require_approval`, priorité, version).
- **Coûts** : `budget_out` (montant/consommation en décimal string, thresholds
  50/80/100, on_exceed `alert|require_approval|block_new_runs`) ; `usage_record`
  (tokens/tool_calls/durée, cost décimal, source_event_id, pricing_version) ;
  `alert_out` (severity, dedup_key, machine §9).
- **Audit** : `audit_entry` (actor_type, action, target, before/after redacted,
  ip_hash, request_id).
- **Événements/ingest** : `event_envelope`, `ingest_events_request/response`,
  `ingest_heartbeat_v1`, `ws_message`.

---

## 14. Fichiers transverses à intégrer par le lead

SP1 ne touche pas ces fichiers (propriété orchestrateur). Changements exacts
requis, détaillés dans le handoff SP1 : `apps/api/core/config.py` (nouvelles
variables §13 du schéma), `apps/api/main.py` (montage routeurs V1 + WS V1 — SP3/SP4),
`apps/api/models/__init__.py` (export nouveaux modèles — SP2),
`apps/api/requirements.txt` (**aucun ajout requis par SP1**),
`AGENTS.md` (corriger dérives D3/D4/D5). Migrations 0008+ : lot SP2.
