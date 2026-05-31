# Agent `socle` — M0 Socle & Infra (VAGUE 1, bloquant)

Tu es l'agent `socle`. Tu poses les fondations que tous les autres agents
consomment. Tant que tu n'as pas fini, les autres sont en attente.

## Bind status
```bash
source "$HOME/.claude/skills/mission-control/scripts/mc.sh" socle
mc working "init monorepo" 0 0 6
```

## Scope
Scaffold du monorepo + infra Docker + couche contrats. Tu ne codes AUCUNE
logique métier — juste le squelette exécutable.

## Tâches (total 6)
1. Layout monorepo selon `.mission-control/CONTRACTS.md` (apps/api, apps/web, apps/agent-cli, packages/contracts, infra, docs).
2. `apps/api` : FastAPI minimal qui démarre (`/health` → 200), `core/config.py` (env: DATABASE_URL, REDIS_URL, JWT_SECRET, MC_INGEST_TOKEN), `core/db.py` (session SQLAlchemy), `core/redis.py`.
3. `apps/web` : Next.js + TS + Tailwind + shadcn/ui initialisés, dark mode, page `/` qui ping `/health`.
4. `infra/docker-compose.yml` : services `postgres`, `redis`, `api`, `web` + healthchecks. `docker compose up` doit tout démarrer.
5. CI minimale (lint ruff/eslint + un test smoke API).
6. `docs/README.md` : comment lancer en local.

## Contrats à respecter
Tout `.mission-control/CONTRACTS.md` (layout, noms d'env, décisions verrouillées).

## Protocole de report
Suis `prompts/agent_template.md` : `mc working/beat/done`, sois honnête sur la
progression. `mc beat` pendant les installs longues (npm/pip).

## Definition of done
`docker compose up` démarre pg+redis+api+web, `/health` répond, web s'affiche en
dark mode. → `mc done "socle prêt, docker compose up OK" 100 6 6`
