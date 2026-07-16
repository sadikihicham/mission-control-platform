# Agent Control V1 — Feature flag, canary, rollback, backup/restore et migration V0→V1

> Ferme le gap assumé au Gate P7 : **SP7 §14-15** (feature flag par tenant,
> canary, rollback, backup/restore ; migration CLI/credentials V0→V1 et date de
> désactivation du secret global). Rédigé en P9. Document opérationnel : il décrit
> les mécanismes **réellement présents** dans le code et signale explicitement ce
> qui reste à câbler.

Principe directeur (rappel Contract V1) : **toutes les extensions V1 sont
additives** (ADR-0007). Aucune colonne/route/payload V0 n'est mutée. Le V0
(`/agents/heartbeat`, `/ws`, canal `mc:events`) continue de fonctionner inchangé.
Conséquence : le rollback d'Agent Control V1 ne casse jamais le socle V0.

---

## 14. Feature flag par tenant, canary, métriques de succès, rollback

### 14.1 Points de bascule (flags)

Trois leviers, du plus grossier au plus fin :

| Levier | Portée | Où | Effet |
|---|---|---|---|
| `MC_HOST_ADAPTER` | processus (toutes installations) | `settings.mc_host_adapter` (`core/config.py`) | Sélectionne l'adaptateur hôte (`local` par défaut). Point d'extension pour un adaptateur `jwt` d'un hôte réel — sans toucher au domaine (ADR-0001). |
| `MCInstallation.status` | **par tenant** | table `mc_installations` (`active|suspended|archived`) | `suspended`/`archived` → le `DbHostAdapter` ne résout plus de contexte pour ce tenant → **toutes** les routes V1 répondent fail-closed (`tenant_required`). Coupe le module pour un tenant sans toucher aux autres. |
| `MCInstallation.feature_flags` (JSONB) | **par tenant** | table `mc_installations`, propagé dans `TenantRef.feature_flags` (`HostContext`) | Drapeaux fins lisibles par le domaine/front via le contexte. Réservé aux bascules de sous-fonctionnalités par tenant (le socle `feature_flags={}` = comportement par défaut). |

**Activation d'un tenant** : `POST /agent-control/v1/installations/{id}/activate`
(capacité `admin`, un admin n'active que **son** installation — fail-closed
ADR-0003). Passe `status` à `active`.

**Canary via `status`** : le déroulé progressif se pilote par la population des
`mc_installations` en `active`. Un tenant reste `suspended` tant qu'il n'est pas
dans la vague canary, puis passe `active`. La désactivation d'un tenant est
immédiate et locale (repasser `status` à `suspended`).

> Limite connue (à câbler avant GA) : `feature_flags` est **propagé** jusqu'au
> `HostContext` mais aucun garde applicatif ne lit encore un flag nommé précis
> pour masquer une sous-fonctionnalité. Le grain de bascule effectif aujourd'hui
> est l'installation (`status`), pas un flag nommé. Ajouter un garde = lire
> `ctx.tenant.feature_flags["<nom>"]` au point de décision voulu (aucune migration
> requise, la colonne existe).

### 14.2 Montée embarquée vs standalone

Le frontend se monte sous `/agent-control` soit en **standalone** (dev : résout
`locale/installation/capabilities` via `GET /agent-control/v1/context`, réutilise
le JWT hôte), soit **embarqué** dans un shell hôte (`AgentControlProvider
embedded`, l'hôte fournit `locale/installationId/capabilities` + callback de
navigation). Basculer embedded↔standalone est une bascule de **montage front**,
sans changement d'API : rollback = remonter la page racine hôte précédente.

### 14.3 Métriques de succès (canary)

À surveiller par tenant pendant une vague canary (toutes dérivées de données déjà
persistées, aucune donnée mock) :

- **ingest** : taux `accepted` vs `rejected`/`duplicates` sur `POST /ingest/events`
  (réponse `{accepted, duplicates, rejected, last_sequence}`) ; un pic de
  `sequence_out_of_order`/`idempotency_conflict` signale un producteur mal
  configuré, pas une régression serveur.
- **outbox** : profondeur de `mc_outbox_events.status='pending'` (doit rester
  basse ; une croissance monotone = relais arrêté ou Redis down — voir 14.5).
- **temps réel** : nombre de connexions `/agent-control/ws` acceptées vs fermetures
  `4401`/`4403` (auth/tenant). Des `4403` massifs = mauvais `installation_id`
  côté client.
- **coûts** : réconciliation `somme(agent_usage_records.cost)` == agrégat `/usage`
  (invariant Gate P6) ; tout écart = anomalie de comptage.
- **budgets/alertes** : alertes `open` non acquittées, franchissements
  `budget.exceeded`.
- **latence** p95 des routes de lecture (`/dashboard`, `/agents`, `/runs`).

### 14.4 Rollback

Le rollback est **gradué** — préférer le cran le plus fin qui résout l'incident :

1. **Rollback tenant (le plus fin, sans redéploiement)** : passer le tenant
   incriminé `mc_installations.status='suspended'`. Effet immédiat, isolé à ce
   tenant. Aucune donnée perdue (persistée). C'est le premier réflexe canary.
2. **Rollback fonctionnel (front)** : redémonter la page hôte précédente / retirer
   la route `/agent-control` du shell. L'API V1 reste debout (inoffensive si non
   appelée). Réversible sans migration.
3. **Rollback processus** : redéployer l'image API antérieure. Comme les tables
   V1 sont additives, une image plus ancienne **ignore** simplement les tables
   0008+ ; le V0 fonctionne. Les lignes V1 restent en base (aucune corruption).
4. **Rollback schéma (dernier recours, rarement nécessaire)** : `alembic downgrade`
   des migrations V1 (voir 14.6). N'est requis que si une migration V1 pose
   problème en soi — jamais pour désactiver la fonctionnalité (crans 1-3 suffisent).

**Invariant temps réel** : le canal V1 `ac:events` et l'endpoint
`/agent-control/ws` sont **strictement disjoints** du V0 (`mc:events`, `/ws`).
Arrêter le relais d'outbox / le WS V1 n'affecte jamais le temps réel V0. À l'arrêt
du relais, les faits métier restent `pending` dans `mc_outbox_events` et seront
diffusés à la reprise (livraison au moins une fois, dedup consommateur par
`event_id`).

### 14.5 Exploitation du relais d'outbox

Le relais (`agent_control/realtime.py`, démarré au lifespan) draine
`mc_outbox_events.status='pending'` vers Redis `ac:events` puis marque
`published`. `SELECT ... FOR UPDATE SKIP LOCKED` rend le drain sûr à plusieurs
instances API. En cas de Redis indisponible : la ligne reste `pending`
(`attempts++`) et sera réessayée ; au-delà de `_RELAY_MAX_ATTEMPTS` (8) elle passe
`failed` (à rejouer manuellement après correction). **Aucun fait métier n'est
jamais perdu** (persistance avant publication, ADR-0005).

Diagnostic rapide :

```sql
-- profondeur de file et plus vieux pending
SELECT status, count(*), min(created_at) FROM mc_outbox_events GROUP BY status;
-- lignes en échec définitif
SELECT id, event_type, attempts, last_error FROM mc_outbox_events WHERE status='failed';
```

### 14.6 Ordre des migrations V1 (pour downgrade)

Additives, à dérouler/annuler dans l'ordre inverse au downgrade :

`0008_mc_installations` → `0009_mc_user_mappings` → `0010_tasks_hierarchy` →
`0011_agent_registry_credentials` → `0012_agent_events_outbox` →
`0013_agent_runs` → `0014_commands_policies_approvals` →
`0015_costs_budgets_alerts_audit` → `0016_project_task_install_id`.

`alembic downgrade <rev>` retire les tables/colonnes V1 sans toucher au socle V0.
`0016` ne fait qu'ajouter `installation_id` (nullable) à `projects`/`tasks` : son
downgrade retire la colonne, jamais les lignes.

---

## 15. Migration CLI / credentials V0 → V1 et coupure du secret global

### 15.1 Deux régimes d'authentification producteur

| Régime | Auth | Endpoints | Statut |
|---|---|---|---|
| **V0 (compat)** | secret **global partagé** `MC_INGEST_TOKEN` en header `X-MC-Token` | `POST /agents/heartbeat`, `/ws`, canal `mc:events` | Maintenu inchangé (ADR-0002). |
| **V1** | **credential agent individuel** (hashé, scopes, expiration) en header `X-Agent-Credential` | `POST /agent-control/v1/ingest/events`·`/ingest/heartbeat`, `GET /agent/commands`, ack/result | Cible. N'accepte **jamais** le secret global (ADR-0004). |

Le credential V1 est émis par `POST /agent-control/v1/agents/{id}/credentials`
(capacité `manage_agents`). Le secret **n'est affiché qu'une seule fois** à la
création (`credential_created`: `secret`, `key_prefix`, `scopes`, `expires_at`) ;
seul son hash est stocké. Machine d'état credential : `active → (revoked|expired)`,
terminaux immuables ; la **rotation** crée un nouveau credential et révoque
l'ancien (`POST .../credentials/{credential_id}/rotate`).

### 15.2 Procédure de migration (par tenant, sans coupure)

1. **Enrôler** chaque producteur dans le registre V1 : créer/mapper son `agent`
   (clé namespacée `<installation_key>:<local_key>`, ADR-0006) et émettre un
   credential individuel. Distribuer le secret au producteur (une seule fois).
2. **Basculer le producteur** sur l'ingest V1 (`X-Agent-Credential`, enveloppes
   `EventEnvelopeV1` séquencées/idempotentes). Le V0 reste disponible en parallèle
   pendant la bascule (double régime toléré).
3. **Observer** : `accepted`/`rejected` de l'ingest V1 par agent, séquence
   monotone (`agents.last_sequence`), absence de `sequence_out_of_order`.
4. **Retirer** l'usage du secret global producteur par producteur (chacun n'a plus
   besoin de `MC_INGEST_TOKEN` une fois passé en credential individuel).

Le CLI producteur (`apps/agent-cli`, `mc-platform`) reste compatible V0
(fire-and-forget, aucune dépendance). Son évolution vers l'ingest V1 (credential
individuel + séquence) est **additive** : les sous-commandes existantes
(`working`/`blocked`/`done`/`beat`) continuent de viser `/agents/heartbeat` tant
que le tenant n'a pas coupé le secret global.

### 15.3 Coupure du secret global (`MC_GLOBAL_INGEST_ENABLED`)

Le flag `mc_global_ingest_enabled` (`core/config.py`, défaut `True`) est le **point
de contrôle prévu** pour n'accepter, en production embarquée, que les credentials
individuels V1 :

- `True` (défaut) : le heartbeat/enrôlement V0 via `MC_INGEST_TOKEN` reste accepté
  (compat, les producteurs V0 fonctionnent inchangés).
- `False` (cible GA) : refuser le secret global partagé (fail-closed) ; seuls les
  credentials individuels V1 restent valides. **N'affecte jamais l'ingest V1**, qui
  exige toujours un credential agent hashé.

**Date de désactivation** : après migration de **tous** les producteurs d'un
tenant sur des credentials individuels (étape 15.2.4 terminée), et une fenêtre
d'observation sans trafic V0 résiduel sur `/agents/heartbeat`. Recommandation :
basculer `MC_GLOBAL_INGEST_ENABLED=false` par environnement embarqué une fois le
canary de ce tenant validé.

> Limite connue (à câbler avant de s'appuyer dessus en prod) : le flag est
> **déclaré et documenté** mais son enforcement dans le handler V0
> `/agents/heartbeat` (`routers/heartbeat.py`) **n'est pas encore branché** — le
> heartbeat V0 compare toujours `X-MC-Token` à `MC_INGEST_TOKEN`
> inconditionnellement. Câblage requis : refuser (401) quand
> `settings.mc_global_ingest_enabled is False`. Tant que ce garde n'est pas posé,
> la coupure du secret global se fait par **rotation de `MC_INGEST_TOKEN`** (le
> secret partagé change, les producteurs V0 non migrés perdent l'accès) plutôt que
> par le flag. À traiter dans une tranche de durcissement dédiée (hors P9, qui ne
> modifie pas le contrat V0).

---

## Backup / restore

Le socle est **PostgreSQL source de vérité** ; Redis n'est qu'un transport
(reconstruit, jamais sauvegardé comme source). Un backup/restore Postgres cohérent
suffit à restaurer l'intégralité de l'état Agent Control.

### Sauvegarde

```bash
# Dump logique complet (schéma + données). Depuis l'hôte du conteneur postgres :
docker compose exec -T postgres pg_dump -U mc -Fc mission_control > mc_$(date +%F).dump
```

`pg_dump -Fc` (format custom) permet un restore sélectif et compressé. Inclut
toutes les tables V0 **et** V1 (0008+) : registre, credentials (hash seulement,
aucun secret en clair), events, outbox, runs, commandes, politiques, approbations,
coûts, budgets, alertes, audit.

### Restauration

```bash
# Base neuve puis restore (arrêter l'API pendant l'opération) :
docker compose exec -T postgres createdb -U mc mission_control_restore
docker compose exec -T postgres pg_restore -U mc -d mission_control_restore --clean --if-exists < mc_2026-07-16.dump
```

Points d'attention :

- **Redis** : après restore, le canal `ac:events` est vide ; les lignes
  `mc_outbox_events.status='pending'` seront **rediffusées** par le relais au
  démarrage (livraison au moins une fois, dedup consommateur par `event_id`).
  Aucune action manuelle requise. Les lignes déjà `published` ne sont pas
  rediffusées.
- **Secrets credentials** : seuls les **hash** sont sauvegardés/restaurés. Un
  credential dont le secret en clair a été perdu ne peut pas être « récupéré » —
  il faut le **faire tourner** (`rotate`) pour émettre un nouveau secret.
- **Séquences d'ingest** : `agents.last_sequence` est restauré ; un producteur qui
  rejoue d'anciens événements (< dernière séquence) est correctement rejeté
  (`sequence_out_of_order`) — le restore ne rouvre pas la fenêtre d'idempotence.
- **Cohérence tenant** : le restore préserve `installation_id` sur toutes les
  tables V1 ; l'isolation reste garantie (aucun mélange cross-tenant introduit par
  un restore).

### Test de restauration (recommandé avant GA)

Restaurer un dump sur une base jetable, démarrer l'API pointée dessus, et vérifier
les invariants Gate : réconciliation des coûts (`/usage`), isolation tenant
(cross-tenant → 404), et drain de l'outbox (profondeur `pending` qui décroît).
