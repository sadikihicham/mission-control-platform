# Project Mission Control

Cockpit de supervision du développement logiciel piloté par IA (agents Claude Code).

> **Statut : Vague 1 (M0 · Socle) en place.** Les modules métier (DB, auth, API,
> temps réel, dashboard) sont à venir — voir `.mission-control/CONTRACTS.md` et
> `.mission-control/prompts/`.

## Stack

- **Frontend** : Next.js 14, TypeScript, TailwindCSS, React Query, Zustand
- **Backend** : FastAPI, SQLAlchemy 2, Pydantic, WebSocket natif
- **Données** : PostgreSQL 16 · **Temps réel** : Redis pub/sub
- **CLI agent** : Python + Typer (à venir, module M5)

## Démarrer en local

```bash
make up      # backend : postgres + redis + api (migre + seed auto) → http://localhost:8008
make web     # frontend : Next.js dev → http://localhost:3000
# ou en une fois : make dev   (puis `make web` dans un autre terminal)
make help    # toutes les commandes
```

- **Web** → http://localhost:3000 — login : `admin@mc.local` / `admin`
- **API** → http://localhost:8008/health · docs http://localhost:8008/docs
- Postgres/Redis : réseau interne uniquement (ports hôte 5432/6379 souvent occupés) → `make psql`, `make redis-cli`

> Le frontend conteneurisé est optionnel (build long) : `make full`.

## Développer hors Docker

API :
```bash
pip install -r apps/api/requirements.txt
uvicorn apps.api.main:app --reload      # depuis la racine du repo
pytest -q
```

Web :
```bash
cd apps/web && npm install && npm run dev
```

## Architecture des dossiers

```
apps/api/         FastAPI — gateway, services, modèles, schémas, realtime, core
apps/web/         Next.js — dashboard
apps/agent-cli/   CLI `mc-platform` (heartbeats agents)        [M5]
packages/contracts/  Types TS générés depuis l'OpenAPI         [généré]
infra/            docker-compose, Dockerfiles, migrations Alembic
docs/             documentation technique
.mission-control/ contrats inter-modules + prompts d'agents + board mc
```

## Orchestration

Le développement est piloté par 7 agents parallèles. Contrats et prompts dans
`.mission-control/`. Suivi live : `mc dash` depuis ce dossier.
