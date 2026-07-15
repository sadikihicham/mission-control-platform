# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**Project Mission Control** — a cockpit for supervising AI-driven (Claude Code agent) software development. Agents publish heartbeats; the platform persists them, derives KPIs, and pushes live updates to a dashboard. The codebase is in **French** (comments, docstrings, UI strings, commit messages) — match that when editing.

It is a monorepo built by 7 parallel agents against frozen inter-module contracts. **`.mission-control/CONTRACTS.md` is the source of truth for cross-module interfaces (DB schema, auth, REST routes, heartbeat payload, realtime events).** Do not change a contract's shape (env var names, payload fields, route signatures) without treating it as a deliberate, breaking decision — downstream modules code against it, not against implementations.

## Commands

Backend runs in Docker; frontend runs on the host.

```bash
make up        # postgres + redis + api (auto alembic upgrade + seed) → API on :8008
make web       # Next.js dev server (host) → :3100  (login: demo@infinity.ae / password)
make dev       # = make up, then run `make web` in another terminal
make logs      # follow API logs
make psql      # psql into the DB (no host port exposed)
make redis-cli # redis-cli
make seed      # re-run the idempotent seed
make full      # everything in containers incl. web (uses the `full` compose profile; long build)
make clean     # down + delete data volume
make help      # all targets
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

### Frontend — `apps/web/` (Next.js 14 App Router, TS, Tailwind; React Query + Zustand listed but the live dashboard hand-rolls its own state/WS in `app/page.tsx`)

- **`app/page.tsx`** — the whole dashboard: auth gate, polling/WS live updates, view switching. Single large client component.
- **`lib/api.ts`** — typed API client. JWT in `localStorage` (`mc_token`); a `401` clears the token and reloads (handles secret rotation). `wsUrl()` builds the WS URL. `canWrite`/`WRITE_ROLES` gate write UI.
- **`lib/i18n.tsx`** — trilingual (fr/en/ar, default fr); UI strings live here.
- **`lib/mc-data.ts`** — **mock** fleet data (`@ts-nocheck`) from the original design mockup; several "showcase" views (Shell counters, review badge) still render this mock, **not** live data. Live data flows through `Overview`/`Projects`/`AgentDetail`. Don't confuse the two when wiring a view to the backend.
- **`lib/mc.ts`** — pure UI helpers shared across views: status→display mapping, health counts, completion-color gradients, and formatters (`fmtAge`, `monogram`). No data, no I/O.
- **`components/mc/`** — view components (Overview, Projects, Depts, Hierarchy, Audit, Cost, Sentinel, Command palette, etc.).

### Other

- **`apps/agent-cli/`** — `mc-platform`, a **zero-dependency** (stdlib `argparse`+`urllib`) heartbeat client. Beyond the generic `report --state …`, it exposes convenience subcommands `working`/`blocked`/`done`/`idle`/`beat` (`beat` refreshes the timestamp while preserving other fields). Heartbeats are fire-and-forget: unreachable API prints a warning but exits 0 (never breaks an agent's flow). `hooks/` has Claude Code session hooks (`session_start.sh`→working, `pre_tool_use.sh`/`stop.sh`→beat).
- **`packages/contracts/`** — placeholder for TS types generated from the API's OpenAPI.
- **`infra/`** — `docker-compose.yml` (postgres/redis have no host ports; api maps host `8008`→container `8000`; `web` is behind the `full` profile), Dockerfiles, `api-entrypoint.sh`, Alembic migrations.

## Conventions

- Env var names and the heartbeat payload are frozen in `CONTRACTS.md` — the heartbeat body is intentionally aligned with the `mission-control` skill's JSON so the existing TUI works unchanged.
- Multi-tenancy: abandoned for this MVP — the reserved `company_id` column was never wired to a filter and was dropped (migration `0007_drop_company_id`). If multi-tenant work restarts, reintroduce the column together with an active RLS filter in the same change, not ahead of it.
- No cloud CI (removed — GitHub Actions runs never fired despite the repo being public, and blocked on an account-level billing issue outside this project). The gate is local, before every PR: `ruff check apps` + `pytest` (API), `npm run lint` + `npm run build` (web) — the same commands the removed workflow ran.
- Seed creates demo accounts (see `apps/api/seed.py`); default login `demo@infinity.ae` / `password`, plus role-specific accounts `admin/pm/cto/dev/viewer@mc.local`.
