# MVP — Contrats inter-modules (définis par l'orchestrateur, AVANT le code)

> Règle d'or : **personne ne change un contrat sans accord.** Les agents codent
> contre ces contrats, pas contre les implémentations des autres. Si un agent a
> besoin de modifier un contrat → `mc blocked "contrat X à étendre : <raison>"`.

## Décisions verrouillées (défauts retenus, §7 de la roadmap)

1. **Temps réel** : WebSocket **natif** (FastAPI `WebSocket` + client WS natif côté web). Pas de Socket.IO.
2. **Agent CLI** : **Python + Typer**.
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

- **users**: `id` (uuid pk), `email` (unique), `hashed_password`, `role` (str, défaut `admin`), `company_id` (uuid null), `created_at`
- **projects**: `id` (uuid pk), `slug` (unique), `name`, `description` (null), `status` (enum: `proposed|validated|in_dev|done|archived`, défaut `in_dev`), `progress` (int 0-100, défaut 0), `company_id` (uuid null), `created_at`, `updated_at`
- **agents**: `id` (uuid pk), `agent_key` (str unique — = champ `agent` du heartbeat), `project_id` (fk null), `state` (enum: `idle|working|blocked|done|error|stale`), `task` (null), `progress` (int défaut 0), `module` (null), `branch` (null), `blocker` (null), `meta` (jsonb défaut `{}`), `last_heartbeat` (ts null), `updated_at`
- **tasks**: `id` (uuid pk), `project_id` (fk), `agent_id` (fk null), `title`, `status` (str défaut `todo`), `created_at`
- **activity_logs**: `id` (uuid pk), `agent_id` (fk null), `project_id` (fk null), `type` (str), `payload` (jsonb), `created_at`

`db-core` expose les modèles importables : `from apps.api.models import User, Project, Agent, Task, ActivityLog`.

---

## Contract B — Auth (owner: `auth`, consumers: `api`, `dashboard`)

- `POST /auth/login` — body `{ "email": str, "password": str }` → `200 { "access_token": str, "token_type": "bearer" }`
- JWT Bearer, claims `{ "sub": <user_id>, "role": str, "exp": int }`, algo HS256, secret depuis env `JWT_SECRET`.
- Dépendance FastAPI réutilisable : `from apps.api.core.security import get_current_user` → renvoie le `User` ou `401`.
- MVP = 1 rôle `admin`. RBAC fin reporté en V1.

---

## Contract C — REST (owner: `api`, consumers: `dashboard`)

Toutes routes protégées par `get_current_user` SAUF `/auth/login` et l'ingest D.

- `GET  /projects` → `[Project]`  · `POST /projects` → `Project`  · `GET /projects/{id}` → `Project`
- `GET  /agents` → `[Agent]`  · `GET /agents/{id}` → `Agent`
- `GET  /stats/dashboard` → KPIs MVP :
  `{ "projects_active": int, "projects_done": int, "agents_active": int, "agents_blocked": int, "agents_stale": int }`

Schémas Pydantic exportés → OpenAPI → `packages/contracts` (types TS) pour `dashboard`.

---

## Contract D — Heartbeat ingest (owner: `api`, producer: `agent-cli`, → `realtime`)

**LE contrat critique. Aligné sur le JSON `mc` existant.**

- `POST /agents/heartbeat` (non authentifié JWT au MVP ; secret partagé `MC_INGEST_TOKEN` en header `X-MC-Token`)
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
{ "type": "agent.update",   "data": { <objet Agent complet> } }
{ "type": "agent.stale",    "data": { "agent_key": "...", "state": "stale" } }
{ "type": "project.update", "data": { <objet Project> } }
{ "type": "stats.update",   "data": { <KPIs Contract C /stats/dashboard> } }
```
- Une tâche de fond `realtime` scanne `last_heartbeat` et émet `agent.stale` au franchissement du seuil 30s.
