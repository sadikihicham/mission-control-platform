# MVP — Contrats inter-modules (définis par l'orchestrateur, AVANT le code)

> Règle d'or : **personne ne change un contrat sans accord.** Les agents codent
> contre ces contrats, pas contre les implémentations des autres. Si un agent a
> besoin de modifier un contrat → `mc blocked "contrat X à étendre : <raison>"`.

## Décisions verrouillées (défauts retenus, §7 de la roadmap)

1. **Temps réel** : WebSocket **natif** (FastAPI `WebSocket` + client WS natif côté web). Pas de Socket.IO.
2. **Agent CLI** : **Python stdlib (`argparse`), zéro dépendance** — décision initiale (`Typer`)
   abandonnée en cours de build (cf. `apps/agent-cli/pyproject.toml` : `dependencies = []`).
3. **Multi-tenant** : colonne `company_id` (nullable) réservée dès maintenant sur `users`/`projects` ; **isolation (RLS) reportée en V1**.
4. **TUI** : on **réutilise le skill `mission-control`**. Le contrat heartbeat (D) est volontairement aligné sur le JSON `mc` pour que le TUI marche sans adaptation.

## Layout monorepo (posé par `socle`)

```
apps/api/{routers,services,models,schemas,realtime,core}
apps/web/{app,components,stores,lib}
apps/agent-cli/
packages/contracts/        # types TS générés depuis OpenAPI
infra/{docker-compose.yml,Dockerfile.api,Dockerfile.web,migrations}
docs/
```

---

## Contract A — Schéma DB (owner: `db-core`, consumers: `auth`, `api`)

Tables core MVP (SQLAlchemy + Alembic) :

- **users**: `id` (uuid pk), `email` (unique), `hashed_password`, `role` (str, défaut `admin`), `full_name` (null), `civility` (null — `mr|mrs|miss`, message d'accueil genré, migration `0004`), `company_id` (uuid null), `created_at`
- **projects**: `id` (uuid pk), `slug` (unique), `name`, `description` (null), `status` (enum: `proposed|validated|in_dev|done|archived`, défaut `in_dev`), `progress` (int 0-100, défaut 0), `repo` (null — `"owner/name"` GitHub, migration `0002`), `company_id` (uuid null), `created_at`, `updated_at`
- **agents**: `id` (uuid pk), `agent_key` (str unique — = champ `agent` du heartbeat), `project_id` (fk null), `state` (enum: `idle|working|blocked|done|error|stale`), `task` (null), `progress` (int défaut 0), `module` (null), `branch` (null), `blocker` (null), `meta` (jsonb défaut `{}`), `last_heartbeat` (ts null), `updated_at`
- **tasks**: `id` (uuid pk), `project_id` (fk), `agent_id` (fk null), `title`, `status` (str défaut `todo`), `created_at`
- **activity_logs**: `id` (uuid pk), `agent_id` (fk null), `project_id` (fk null), `type` (str), `payload` (jsonb), `created_at`

`db-core` expose les modèles importables : `from apps.api.models import User, Project, Agent, Task, ActivityLog`.

---

## Contract B — Auth (owner: `auth`, consumers: `api`, `dashboard`)

- `POST /auth/login` — body `{ "email": str, "password": str }` → `200 { "access_token": str, "token_type": "bearer" }` (`401` si identifiants invalides)
- `POST /auth/forgot-password` — body `{ "email": str }` → `200 { "message": str, "dev_token": str|null }`. Anti-énumération : réponse identique que l'email existe ou non. `dev_token` renvoyé uniquement hors production (pas de SMTP configuré).
- `POST /auth/reset-password` — body `{ "token": str, "new_password": str }` → `200 { "message": str }` (`400` si jeton invalide/expiré/déjà utilisé)
- `GET /auth/me` → `{ id, email, role, full_name, civility }` — utilisateur courant
- `GET /auth/users` → `[{ id, email, role, full_name, civility }]` — **admin uniquement**
- JWT Bearer, claims `{ "sub": <user_id>, "role": str, "exp": int }`, algo HS256, secret depuis env `JWT_SECRET`.
- Dépendance FastAPI réutilisable : `from apps.api.routers.auth import get_current_user, require_role` → `require_role(minimum)` autorise tout rôle ≥ `minimum`.
- RBAC (`viewer < developer < pm < cto < admin`, `apps/api/core/roles.py`) est **déjà implémenté**, pas reporté à plus tard — seuls le multi-tenant (`company_id`) et son isolation (RLS) restent en V1 (§7 ci-dessus).

---

## Contract C — REST (owner: `api`, consumers: `dashboard`)

Toutes routes protégées par `require_role` (viewer minimum) SAUF `/auth/*` (Contract B) et
l'ingest D.

- `GET  /projects` → `[ProjectSummary]` (résumé : `progress`, `tasks_total`/`tasks_done`, `agents_total`/`agents_active`/`agents_blocked`, `editable`, `repo`)
- `GET  /projects/{id}` → `ProjectDetail` (résumé + `tasks[]` + `agents[]` détaillés)
- `GET  /projects/{id}/git` → infos GitHub du dépôt lié (commits/branches/PRs), ou `{"available": false, "repo": null}` si aucun repo configuré
- `POST /projects` → `ProjectDetail` (`201`) — **pm minimum**
- `PATCH /projects/{id}` → `ProjectDetail` — **pm minimum** (`404` si projet issu du seed, non éditable — seuls les projets DB le sont)
- `DELETE /projects/{id}` → `204` — **pm minimum**
- `GET  /agents` → `[AgentOut]`
- `GET  /agents/{agent_key}/activity` → `[ActivityOut]` — historique heartbeats (60 derniers, plus récent en premier). Il n'y a **pas** de `GET /agents/{id}` (pas de détail agent unique, seul cet historique).
- `GET  /stats/dashboard` → KPIs MVP (`DashboardStats`) :
  `{ "agents_total": int, "agents_active": int, "agents_blocked": int, "agents_stale": int, "agents_done": int, "agents_error": int, "overall_progress": int }`

Schémas Pydantic exportés → OpenAPI → `packages/contracts` (types TS) pour `dashboard`.

---

## Contract D — Heartbeat ingest (owner: `api`, producer: `agent-cli`, → `realtime`)

**LE contrat critique. Aligné sur le JSON `mc` existant.**

- `POST /agents/heartbeat` (non authentifié JWT au MVP). Identité par agent (depuis
  `0005_agent_token`) : `MC_INGEST_TOKEN` en header `X-MC-Token` sert de secret
  **d'enrôlement** uniquement, opt-in via `X-MC-Enroll: 1`. Au 1er heartbeat d'un `agent_key`
  qui envoie ce header, le serveur émet un token propre à cet agent (`agent_token` dans la
  réponse, une seule fois) ; ce token remplace ensuite le secret partagé pour cet `agent_key`
  (`agents.token_hash`, SHA-256). Un client qui n'envoie jamais `X-MC-Enroll` (ancienne
  version d'`agent-cli`, script `curl` manuel) n'est jamais enrôlé et garde le comportement
  d'origine — secret partagé accepté à chaque appel. Révocation : `POST
  /agents/{agent_key}/revoke-token` (admin) remet l'agent en attente de ré-enrôlement.
- Body :
```json
{
  "agent": "string (= agent_key, requis)",
  "project": "string (slug projet, optionnel)",
  "state": "idle|working|blocked|done|error",
  "task": "string|null",
  "progress": 0,
  "tasks_done": 0,
  "tasks_total": 0,
  "module": "string|null",
  "branch": "string|null",
  "blocker": "string|null",
  "meta": {}
}
```
- Comportement `api` : upsert dans `agents` (par `agent_key`), set `last_heartbeat=now`, insert `activity_logs`, puis `PUBLISH` sur Redis (Contract E). `stale` n'est jamais envoyé par l'agent — il est **dérivé** côté serveur (silence > 30s en `working`).

---

## Contract E — WebSocket + Redis (owner: `realtime`, consumer: `dashboard`)

- Client se connecte : `GET /ws?token=<JWT>` (FastAPI WebSocket).
- Canal Redis pub/sub : `mc:events`.
- Messages serveur → client (JSON) :
```json
{ "type": "agent.update", "data": { <objet Agent complet> } }
{ "type": "agent.stale",  "data": { "agent_key": "...", "state": "stale" } }
{ "type": "stats.update", "data": { <KPIs Contract C /stats/dashboard> } }
{ "type": "refresh",      "data": { "source": "mc-files" } }
```
Pas de `project.update` (jamais émis) — les projets ne changent pas par ce canal, seul un
`refresh` générique invite le client à recharger. `refresh` est émis par le watcher fichiers
`mc` (`apps/api/realtime/ws.py`) quand `.mission-control/status/` change.
- Une tâche de fond `realtime` scanne `last_heartbeat` et émet `agent.stale` au franchissement du seuil 30s.
