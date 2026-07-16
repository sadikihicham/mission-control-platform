# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**Project Mission Control** — a cockpit for supervising AI-driven (Claude Code agent) software development. Agents publish heartbeats; the platform persists them, derives KPIs, and pushes live updates to a dashboard. The codebase is in **French** (comments, docstrings, UI strings, commit messages) — match that when editing.

It is a monorepo built by 7 parallel agents against frozen inter-module contracts. **`.mission-control/CONTRACTS.md` is the source of truth for cross-module interfaces (DB schema, auth, REST routes, heartbeat payload, realtime events).** Do not change a contract's shape (env var names, payload fields, route signatures) without treating it as a deliberate, breaking decision — downstream modules code against it, not against implementations.

A second module, **Agent Control**, was added later by its own phased build (see Architecture below) with its own frozen contract file — don't confuse the two.

## Commands

Backend runs in Docker; frontend runs on the host.

```bash
make up        # postgres + redis + api (auto alembic upgrade + seed) → API on :8008
make web       # Next.js dev server (host) → :3100  (login: whichever admin account exists in the DB — seed no longer creates one, see Conventions)
make dev       # = make up, then run `make web` in another terminal
make logs      # follow API logs
make psql      # psql into the DB (no host port exposed)
make redis-cli # redis-cli
make seed      # re-run the idempotent seed
make full      # everything in containers incl. web (uses the `full` compose profile; long build)
make clean     # down + delete data volume
make help      # all targets
make down      # stop the backend
make restart   # = down + up
make ps        # container status
make contracts # regenerate TS types from the OpenAPI (packages/contracts + lib/contracts.ts)
```

**Tests (integration, real DB):**
```bash
make test                          # spins up ephemeral mc_test DB in the api container, runs pytest
pytest -q                          # host-side: requires DATABASE_URL pointing at a DB whose name contains "test"
pytest apps/api/tests/test_auth.py -q
pytest apps/api/tests/test_auth.py::test_login_ok -q   # single test
```
Tests refuse to run unless `DATABASE_URL` contains the substring `"test"` (guard against wiping a real DB — see `apps/api/tests/conftest.py`). The schema is dropped + recreated + seeded once per session. `TestClient` is used without a context manager, so the lifespan (Redis subscriber, stale scanner, file watcher) does **not** start — HTTP tests have no Redis dependency.

**Lint:**
```bash
ruff check apps          # Python (config in pyproject.toml: E,F,I,UP,B; line-length 100, target py312)
cd apps/web && npm run lint && npm run build   # web (next lint + build)
```

**Migrations (Alembic):**
```bash
alembic upgrade head                              # from repo root (prepend_sys_path=., script_location=infra/migrations)
alembic revision -m "description"                 # new migration in infra/migrations/versions/
```
The api container runs `alembic upgrade head` then `seed` on startup via `infra/api-entrypoint.sh`. The repo is volume-mounted into the container, so code/migrations/`.mission-control/status` are live-editable in dev.

**Agent CLI (heartbeat producer):**
```bash
PYTHONPATH=apps/agent-cli python3 -m mc_platform working "task desc" 45 3 7   # state task progress done total
```

## Architecture

### Backend — `apps/api/` (FastAPI, SQLAlchemy 2, Pydantic v2)

- **`main.py`** — app + lifespan + `GET /health`. On startup it launches three background asyncio tasks (in `realtime/ws.py`): a Redis subscriber, a stale-agent scanner (sweeps every 15s, flips silent `working` agents to `stale`), and an mc-file watcher (polls `MC_STATUS_DIR` every 2s).
- **`core/`** — `config.py` (pydantic-settings, env-driven; defaults match Docker), `db.py` (**lazy** engine/session — importing models never opens a connection), `redis.py` (sync `publish_event` for ingest, async client for the realtime subscriber), `security.py` (bcrypt + JWT HS256 + reset-token hashing), `roles.py` (RBAC hierarchy `viewer<developer<pm<cto<admin`).
- **`models/`** — `tables.py` (User, Project, Agent, Task, ActivityLog, PasswordResetToken), `enums.py`. Import via `from apps.api.models import User, Project, Agent, ...`. `User.full_name`/`User.civility` (migration `0004`) drive the gendered welcome message in the UI.
- **`routers/`** — `auth.py` (login, forgot/reset-password, `get_current_user`, `require_role(min)` factory, `/auth/me`, `/auth/users` [admin-only]), `agents.py` (`/agents`, `/stats/dashboard`, `/agents/{key}/activity`), `projects.py` (read for viewer, CRUD for pm+, plus `/projects/{id}/git`), `heartbeat.py` (the ingest endpoint). `/stats/dashboard` returns `DashboardStats`: `agents_total`, `agents_active`, `agents_blocked`, `agents_stale`, `agents_done`, `agents_error`, `overall_progress`.
- **`services/`** — business logic kept out of routers: `agents_db.py`, `projects.py`, `mc_sync.py` (file→DB sync), `events.py` (`publish_stats`), `git.py` (GitHub API with in-memory TTL cache), `project_seed.py` (static project→task→subtask→agent fixtures from the MVP orchestration, slated to be replaced by live DB data).
- **`schemas/`** — Pydantic DTOs (→ OpenAPI → intended source for `packages/contracts` TS types).

**Two agent sources, one table.** The `agents` table is fed by *both* (a) the `mission-control` skill's JSON status files in `.mission-control/status/` (synced by `services/mc_sync.py`, watched every 2s) and (b) `mc-platform` heartbeats hitting `POST /agents/heartbeat`. Fields outside Contract A (`label`, `tasks_done`, `tasks_total`) live in the agent's `meta` JSONB column.

**Realtime flow (Contract E).** Ingest/sync write to Postgres, then `publish_event(...)` to the Redis `mc:events` channel (sync, non-blocking — a dead Redis never fails an ingest). The async subscriber in `ws.py` fans every message out to connected `/ws` clients. Event types: `agent.update`, `agent.stale`, `stats.update`, `refresh`. The `/ws?token=<JWT>` endpoint validates the JWT then ignores client messages (keepalive only).

**Auth specifics.** `state="stale"` is **server-derived** (silence > `MC_STALE_SECONDS`, default 30s) and is rejected by the ingest endpoint. The heartbeat endpoint is **not** JWT-protected — it uses a shared secret in the `X-MC-Token` header (`MC_INGEST_TOKEN`). Everything else requires a Bearer JWT. `forgot-password` is anti-enumeration (identical response regardless of email existence) and, outside production, returns the raw reset token in `dev_token` since there's no SMTP.

### Agent Control — embeddable V1 module (`apps/api/agent_control/` + `apps/web/app/agent-control/`)

A second bounded context, built later as its own phased chantier (gates P0→P9, one specialized sub-agent per concern under `.claude/agents/agent-control-*.md`, orchestrated by `agent-control-orchestrator`; design docs in `docs/agent-control/` — numbered analysis/schema/prompts plus ADRs `0001`-`0009`, release/rollback plan in `08_RELEASE_ROLLBACK.md`). Its goal: turn the MVP cockpit into a business module embeddable in a host platform — identity, tenant, roles and navigation are **host-owned**, this module never owns them (ports/adapters). Its contract is frozen separately in **`.mission-control/CONTRACTS_AGENT_CONTROL_V1.md`** — a sibling of the V0 `CONTRACTS.md`, not a replacement; don't conflate the two when checking a shape.

**Tenant model, reintroduced differently from V0.** New tables `mc_installations` / `mc_user_mappings` carry an `installation_id` — **not** the old dropped `company_id`. Per `docs/agent-control/adr/0003-tenant-host-owned.md`: the tenant is resolved **server-side** via `HostTenantPort`/`HostContext` from the host credential, never accepted from a request body/query, and every service filters by it. Fail-closed: no tenant context → 403 `tenant_required`; a resource belonging to another tenant → **404, never 403** (don't leak existence). Gate P8 (migration `0016_project_task_install_id.py`) retrofitted the pre-existing V0 `projects`/`tasks` tables with a nullable `installation_id` FK and exposed them tenant-scoped under `/agent-control/v1/projects*`/`/tasks*`.

**Code layout.** `apps/api/agent_control/{control,ingest,operations,overview,projects,registry,runs}/` (routes/service/schemas per sub-domain), `apps/api/models/agent_control.py` (14 tables: installations, user mappings, agent credentials/events, outbox, runs/steps, policies, approvals, commands, usage/budgets/alerts, audit log), `apps/api/integrations/` (`HostTenantPort` and friends, `local_adapter.py`, capabilities/permissions/envelopes/errors), `apps/api/core/agent_control_deps.py`, `apps/api/routers/agent_control_context.py`. Migrations `0008`→`0016`.

**Frontend.** A parallel embedded surface at `apps/web/app/agent-control/*` (own `layout.tsx` + routes: agents, projects, runs, alerts, approvals, audit, costs, settings), `apps/web/components/agent-control/*`, `apps/web/lib/agent-control/*` — this is where **React Query is actually used** (`hooks.ts`/`provider.tsx`), unlike the legacy dashboard which hand-rolls its state. Meant to be mounted by a host app via `<AgentControlProvider embedded>`, not as a standalone page.

**Realtime (Gate P9).** The V1 channel is now wired end-to-end: the outbox (`apps/api/agent_control/operations/outbox.py`, table `mc_outbox_events`) is drained via `SELECT ... FOR UPDATE SKIP LOCKED` and relayed onto the Redis `ac:events` channel — strictly disjoint from the V0 `mc:events`/`/ws` channel, no shared code — then fanned out over `/agent-control/ws` (identity/tenant/capability checked fail-closed before accept, filtered per tenant+topic). The frontend uses this for targeted React Query invalidation, with a 60s poll as a fallback net, not the primary path anymore. Also shipped in P9: `reports/export.csv` (streamed, tenant-scoped) and a Playwright + axe-core E2E/a11y suite run against an isolated stack (ports 8009/3200, own DB/redis) — never the shared dev stack.

`MC_GLOBAL_INGEST_ENABLED` (default `true`) gates the V0 heartbeat's shared-secret fallback in `apps/api/routers/heartbeat.py`: set to `false` to fail-closed reject `X-MC-Token`-only enrollment/heartbeats for never-seen agents, while already-enrolled agents keep working on their individual per-agent token regardless. Does not affect V1 ingest, which always requires an individual agent credential.

**Test convention specific to this module:** cross-tenant access always asserts **404, never 403** (see `test_agent_control_projects_p8.py`) — don't regress to 403 when adding endpoints here.

### Frontend — `apps/web/` (Next.js 14 App Router, TS, Tailwind; the legacy dashboard hand-rolls its own state/WS in `app/page.tsx` — React Query is used by the newer Agent Control module above, Zustand remains unused)

- **`app/page.tsx`** — the whole dashboard: auth gate, polling/WS live updates, view switching. Single large client component.
- **`lib/api.ts`** — typed API client. JWT in `localStorage` (`mc_token`); a `401` clears the token and reloads (handles secret rotation). `wsUrl()` builds the WS URL. `canWrite`/`WRITE_ROLES` gate write UI.
- **`lib/i18n.tsx`** — trilingual (fr/en/ar, default fr); UI strings live here.
- **`lib/contracts.ts`** — TS types generated from the API's OpenAPI (see `packages/contracts/` below); `lib/api.ts` re-exports DTOs from here instead of hand-duplicating them.
- **`lib/mc.ts`** — pure UI helpers shared across views: status→display mapping, health counts, completion-color gradients, and formatters (`fmtAge`, `monogram`). No data, no I/O.
- **`components/mc/`** — view components (Overview, Projects, Depts, Hierarchy, `HierarchyFlow`, Audit, Cost, Sentinel, Command palette, etc.).

### Other

- **`apps/agent-cli/`** — `mc-platform`, a **zero-dependency** (stdlib `argparse`+`urllib`) heartbeat client. Beyond the generic `report --state …`, it exposes convenience subcommands `working`/`blocked`/`done`/`idle`/`beat` (`beat` refreshes the timestamp while preserving other fields). Heartbeats are fire-and-forget: unreachable API prints a warning but exits 0 (never breaks an agent's flow). `hooks/` has Claude Code session hooks (`session_start.sh`→working, `pre_tool_use.sh`/`stop.sh`→beat).
- **`packages/contracts/`** — no longer a placeholder: `generate.py` produces `openapi.json`/`types.ts` from the running API, regenerated via `make contracts`; `apps/web/lib/contracts.ts` is the in-tree copy the web app imports.
- **`infra/`** — `docker-compose.yml` (compose project pinned to `name: agent-control` to avoid colliding with a co-hosted SGI stack; postgres/redis have no host ports; api maps host `8008`→container `8000`; `web` is behind the `full` profile), plus prod-only `docker-compose.prod.yml`, `docker-compose.prod-fronted.yml`, `deploy-prod.sh`, Dockerfiles, `api-entrypoint.sh`, Alembic migrations.

## Conventions

- Env var names and the heartbeat payload are frozen in `CONTRACTS.md` — the heartbeat body is intentionally aligned with the `mission-control` skill's JSON so the existing TUI works unchanged.
- Multi-tenancy: abandoned for the original MVP usage — the reserved `company_id` column was never wired to a filter and was dropped (migration `0007_drop_company_id`). That verdict still stands for the legacy `agents`/`projects`/`tasks` code paths. The **Agent Control** module (see Architecture) later reintroduced real, actively-filtered tenant isolation via `installation_id` — deliberately not `company_id` (`docs/agent-control/adr/0003-tenant-host-owned.md`). Read that ADR before touching tenant logic anywhere in the repo.
- Agent Control test suite: 16 `apps/api/tests/test_agent_control_*.py` files, including cross-tenant isolation tests that assert **404, never 403** (see the Architecture subsection above), plus a separate Playwright/a11y suite under `apps/web/e2e/`.
- No cloud CI (removed — GitHub Actions runs never fired despite the repo being public, and blocked on an account-level billing issue outside this project). The gate is local, before every PR: `ruff check apps` + `pytest` (API), `npm run lint` + `npm run build` (web) — the same commands the removed workflow ran.
- `apps/api/seed.py` no longer creates any demo user account (intentional — they kept reappearing on every reseed after being deleted). Dev login uses whichever admin account exists in the DB (created manually). Tests get their own disposable `admin/pm/viewer@mc.local` accounts via `conftest.py`'s `_seed_role_accounts()`, decoupled from the dev seed.
