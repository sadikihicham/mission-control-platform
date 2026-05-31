# Agent `auth` — M2 Auth (VAGUE 3, après `db-core`)

Tu es l'agent `auth`. Tu possèdes l'authentification. `api` et `dashboard`
dépendent du Contract B.

## Bind status
```bash
source "$HOME/.claude/skills/mission-control/scripts/mc.sh" auth
mc working "JWT login" 0 0 4
```

## Scope
`apps/api` — auth seulement. MVP = 1 rôle `admin`.

## Tâches (total 4)
1. `core/security.py` : hash password (passlib/bcrypt), création/décodage JWT (HS256, `JWT_SECRET`).
2. `POST /auth/login` (Contract B) → `{access_token, token_type}`.
3. Dépendance `get_current_user()` réutilisable (renvoie `User` ou 401).
4. Tests : login OK, mauvais mdp → 401, route protégée sans token → 401.

## Contrats à respecter
Contract B de `.mission-control/CONTRACTS.md`. N'invente PAS de RBAC fin (V1).

## Dépendances
Démarre quand `db-core` est `done` (modèle `User`).

## Definition of done
Login renvoie un JWT valide, `get_current_user` protège une route de test.
→ `mc done "auth JWT + get_current_user OK" 100 4 4`
