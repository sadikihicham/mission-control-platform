# QA E2E Agent Control (Playwright) — P9, gap 3

Tests de bout en bout : **isolation multi-tenant** (aucune fuite UI), **multi-profil**
(capacités : admin vs viewer), **accessibilité** (axe-core, aucune violation
`critical`). Sur `/agent-control/**`.

## Ce que ça prouve

- `multi-tenant.spec.ts` : deux installations distinctes (Alpha = tenant local,
  Beta = `e2e-tenant-b`). Un utilisateur ne voit jamais, dans l'UI, les
  agents/projets de l'autre tenant (ADR-0003).
- `multi-profile.spec.ts` : le viewer ne voit aucune action de gestion et se voit
  refuser l'écran Coûts (`view_costs` absent) ; l'admin voit création de projet et
  export CSV. L'UI reflète les capacités ; l'API vérifie toujours.
- `a11y.spec.ts` : scan axe WCAG 2.0/2.1 A & AA sur dashboard/agents/projects/costs.
  Gate = zéro violation `critical` ; les `serious` sont attachées au rapport.

## Prérequis

- Navigateur : `npx playwright install chromium chromium-headless-shell`.
- Une stack **isolée** (API + web) sur des ports décalés, seedée avec deux tenants
  (`apps/api/e2e_seed.py`). Ne jamais viser la stack docker partagée.

## Lancer (stack isolée, ports décalés)

```bash
# 1. Base de test dédiée dans le postgres partagé (DB séparée, non destructif)
docker exec agent-control-postgres-1 sh -c \
  "psql -U mc -d mission_control -tc \"SELECT 1 FROM pg_database WHERE datname='mc_e2e'\" | grep -q 1 || createdb -U mc mc_e2e"

# 2. API isolée sur :8009 (migrations + seed + seed E2E 2 tenants), redis DB /1
docker run -d --name mc-e2e-api --network agent-control_default -p 8009:8000 \
  -v "$PWD":/app -w /app \
  -e DATABASE_URL=postgresql+psycopg://mc:mc@postgres:5432/mc_e2e \
  -e REDIS_URL=redis://redis:6379/1 \
  -e JWT_SECRET=e2e-secret -e MC_INGEST_TOKEN=e2e-ingest -e ENVIRONMENT=development \
  -e 'CORS_ORIGINS=["http://localhost:3200"]' \
  agent-control-ag-api sh -c \
  "alembic upgrade head && python -m apps.api.seed && python apps/api/e2e_seed.py && uvicorn apps.api.main:app --host 0.0.0.0 --port 8000"

# 3. Web isolé sur :3200, pointé sur l'API isolée, auto-login désactivé
cd apps/web
NEXT_PUBLIC_API_URL=http://localhost:8009 NEXT_PUBLIC_AUTO_LOGIN=0 npm run build
NEXT_PUBLIC_API_URL=http://localhost:8009 NEXT_PUBLIC_AUTO_LOGIN=0 npx next start -p 3200 &

# 4. Tests
E2E_BASE_URL=http://localhost:3200 E2E_API_URL=http://localhost:8009 npm run test:e2e

# 5. Démontage (les ressources mc_e2e / mc-e2e-api sont dédiées, non partagées)
docker rm -f mc-e2e-api ; docker exec agent-control-postgres-1 dropdb -U mc mc_e2e
```

L'auth E2E réutilise le JWT hôte : les tests obtiennent un token via `POST
/auth/login` puis l'injectent en `localStorage` (`mc_token`) avant navigation —
aucune dépendance à l'UI de connexion.
