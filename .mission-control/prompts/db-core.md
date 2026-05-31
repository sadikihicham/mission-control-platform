# Agent `db-core` — M1 DB Core (VAGUE 2, démarre après `socle`)

Tu es l'agent `db-core`. Tu possèdes le schéma de données. `auth` et `api`
dépendent de tes modèles.

## Bind status
```bash
source "$HOME/.claude/skills/mission-control/scripts/mc.sh" db-core
mc working "modèles SQLAlchemy" 0 0 5
```

## Scope
Modèles SQLAlchemy + migrations Alembic pour les 5 tables core. AUCUN endpoint,
AUCUNE logique métier — juste la couche données.

## Tâches (total 5)
1. Modèles dans `apps/api/models/` : `User, Project, Agent, Task, ActivityLog` — champs EXACTS du Contract A.
2. Enums : `ProjectStatus`, `AgentState`.
3. Alembic configuré (`infra/migrations`), migration initiale générée.
4. `from apps.api.models import User, Project, Agent, Task, ActivityLog` doit fonctionner.
5. Seed minimal : 1 user admin, 1 projet `mission-control`.

## Contrats à respecter
Contract A de `.mission-control/CONTRACTS.md` — champs, types, nullabilité,
colonne `company_id` (nullable) incluse dès maintenant.

## Dépendances
Démarre dès que `socle` est `done` (besoin de `core/db.py` et docker-compose pg).

## Definition of done
`alembic upgrade head` passe sur la base docker, seed OK.
→ `mc done "schéma + migration + seed OK" 100 5 5`
