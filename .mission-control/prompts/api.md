# Agent `api` — M3 API (VAGUE 3, après `db-core`)

Tu es l'agent `api`. Tu possèdes les Contracts C et D. C'est le hub : tes
endpoints alimentent `dashboard` et reçoivent les heartbeats de `agent-cli`,
puis publient sur Redis pour `realtime`.

## Bind status
```bash
source "$HOME/.claude/skills/mission-control/scripts/mc.sh" api
mc working "schémas Pydantic + routers" 0 0 6
```

## Scope
`apps/api/{routers,services,schemas}` — REST + ingest. Tu n'implémentes PAS le
WS (c'est `realtime`) ni l'auth (c'est `auth`) — tu les CONSOMMES.

## Tâches (total 6)
1. Schémas Pydantic (Contracts C & D) → exportés à l'OpenAPI.
2. Router projets : `GET /projects`, `POST /projects`, `GET /projects/{id}` (protégés `get_current_user`).
3. Router agents : `GET /agents`, `GET /agents/{id}` (protégés).
4. `GET /stats/dashboard` → KPIs (Contract C).
5. `POST /agents/heartbeat` (Contract D, header `X-MC-Token`) : upsert agent par `agent_key`, set `last_heartbeat`, insert `activity_log`.
6. Après upsert heartbeat : `PUBLISH` sur Redis `mc:events` un message `agent.update` (Contract E) — la PUBLICATION t'incombe, l'abonnement WS incombe à `realtime`.

## Contrats à respecter
Contracts C et D (owner), publie le format E. Modèles importés de `db-core`,
auth importé de `auth`.

## Dépendances
Démarre quand `db-core` est `done`. Pour la tâche 6, coordonne le format avec
`realtime` (déjà figé dans Contract E).

## Definition of done
Heartbeat reçu → agent upserté en base → message publié sur Redis ; `/stats` et
les routers répondent authentifiés. → `mc done "REST + ingest + publish OK" 100 6 6`
