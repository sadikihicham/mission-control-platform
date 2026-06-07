// @ts-nocheck
// Données mock du design Claude (flotte d'agents) — vendu tel quel pour les vues vitrines.
// mc-data.jsx — mock fleet of Claude Code agents for Mission Control
// Exposed on window so other babel scripts can read it.

const MODELS = ["claude-sonnet-4.5", "claude-opus-4.1", "claude-haiku-4"];

// ---- log line helpers -------------------------------------------------
// kind: system | thinking | command | tool | output | success | error | diff
function L(kind, text) { return { kind, text }; }

const SEED_LOGS = {
  running_auth: [
    L("system", "● Session resumed · claude-sonnet-4.5 · cwd ~/acme/api"),
    L("thinking", "Reading auth middleware and current token strategy…"),
    L("tool", "Read  src/auth/middleware.ts  (218 lines)"),
    L("tool", "Read  src/auth/jwt.ts  (96 lines)"),
    L("thinking", "Current setup issues short-lived access tokens with no refresh. I'll add a rotating refresh-token store."),
    L("command", "$ npm run typecheck"),
    L("output", "  ✓ tsc --noEmit  (0 errors, 3.4s)"),
    L("tool", "Edit  src/auth/jwt.ts  +42 −7"),
    L("tool", "Write src/auth/refreshStore.ts  (new, 88 lines)"),
    L("command", "$ npm test -- auth"),
    L("output", "  PASS  src/auth/jwt.test.ts (12)"),
    L("output", "  PASS  src/auth/refresh.test.ts (8)"),
    L("success", "  20 passing · refresh rotation verified"),
    L("thinking", "Wiring refresh endpoint into the router and updating the OpenAPI spec…"),
  ],
  running_darkmode: [
    L("system", "● Session resumed · claude-sonnet-4.5 · cwd ~/acme/dashboard"),
    L("thinking", "Auditing color tokens used across components for theme extraction."),
    L("command", "$ rg --count 'bg-white|text-black' src | wc -l"),
    L("output", "  147"),
    L("tool", "Edit  src/styles/tokens.css  +63 −0"),
    L("tool", "Edit  src/components/Sidebar.tsx  +8 −8"),
    L("thinking", "Migrating hard-coded hex values to semantic tokens, batch 3 of 9."),
    L("tool", "Edit  src/components/Card.tsx  +5 −5"),
    L("tool", "Edit  src/components/Table.tsx  +11 −11"),
  ],
  running_tests: [
    L("system", "● Session resumed · claude-opus-4.1 · cwd ~/acme/payments"),
    L("thinking", "Mapping the payments API surface to find untested branches."),
    L("command", "$ npx vitest run --coverage payments"),
    L("output", "  Coverage: 61.2% lines · target 85%"),
    L("tool", "Write tests/payments/refund.spec.ts  (new, 134 lines)"),
    L("tool", "Write tests/payments/webhook.spec.ts (new, 201 lines)"),
    L("command", "$ npx vitest run payments"),
    L("output", "  PASS  refund.spec.ts (9)"),
    L("error", "  FAIL  webhook.spec.ts › retries on 5xx — timeout 5000ms"),
    L("thinking", "Webhook retry uses real timers. Switching to fake timers and advancing the clock."),
  ],
  running_i18n: [
    L("system", "● Session resumed · claude-sonnet-4.5 · cwd ~/acme/web"),
    L("thinking", "Extracting hard-coded strings into message catalogs."),
    L("tool", "Write locales/en.json  (+312 keys)"),
    L("tool", "Write locales/fr.json  (+312 keys, machine-drafted)"),
    L("command", "$ npm run i18n:lint"),
    L("output", "  ⚠ 4 keys missing pluralization rules"),
    L("thinking", "Adding ICU plural forms for cart and notification counts."),
  ],
  running_perf: [
    L("system", "● Session resumed · claude-opus-4.1 · cwd ~/acme/dashboard"),
    L("thinking", "Profiling initial render with React DevTools trace."),
    L("command", "$ npm run build && npx source-map-explorer"),
    L("output", "  main.js 842kB → recharts 311kB, moment 64kB"),
    L("thinking", "moment is only used in two places — replacing with native Intl."),
    L("tool", "Edit  src/utils/date.ts  +18 −44"),
    L("tool", "Edit  src/views/Reports.tsx  +3 −6"),
  ],
  running_sec: [
    L("system", "● Session resumed · claude-haiku-4 · cwd ~/acme/api"),
    L("command", "$ npm audit --json"),
    L("output", "  7 vulnerabilities (2 high, 5 moderate)"),
    L("thinking", "Bumping transitive deps that don't break the lockfile resolution."),
    L("tool", "Edit  package.json  +6 −6"),
    L("command", "$ npm install && npm audit"),
    L("output", "  2 vulnerabilities (0 high, 2 moderate)"),
  ],
  blocked_checkout: [
    L("system", "● Session resumed · claude-opus-4.1 · cwd ~/acme/api"),
    L("thinking", "Reproduced the race condition: two concurrent writes to the orders row."),
    L("tool", "Edit  src/checkout/reserve.ts  +29 −11"),
    L("thinking", "The fix needs a new unique index. This requires a production migration."),
    L("command", "$ npx prisma migrate dev --name order_lock"),
    L("error", "  ⚠ This migration alters a table with 2.4M rows and will lock writes."),
    L("system", "⏸ Paused — awaiting human approval to run migration on production."),
  ],
  blocked_react: [
    L("system", "● Session resumed · claude-sonnet-4.5 · cwd ~/acme/web"),
    L("thinking", "React 19 codemod complete; removing deprecated lifecycle shims."),
    L("tool", "Edit  src/legacy/LegacyProvider.tsx  +0 −210"),
    L("thinking", "12 legacy component files are now dead code and can be deleted."),
    L("system", "⏸ Paused — awaiting approval to delete 12 files (−1,840 lines)."),
  ],
  waiting_migrate: [
    L("system", "● Queued — waiting for a free worker slot (position 1)."),
  ],
  waiting_ci: [
    L("system", "● Queued — waiting for a free worker slot (position 2)."),
  ],
  done_images: [
    L("system", "● Session complete · claude-sonnet-4.5"),
    L("success", "  Built responsive image pipeline · 38 assets optimized · −62% bytes"),
    L("command", "$ git push origin feat/image-pipeline"),
    L("success", "  PR #1284 opened · CI green"),
  ],
  done_docs: [
    L("system", "● Session complete · claude-haiku-4"),
    L("success", "  Generated API reference for 64 endpoints from OpenAPI spec."),
    L("command", "$ git push origin docs/api-reference"),
    L("success", "  PR #1279 opened · CI green"),
  ],
};

// streaming line pools — appended to running agents over time
const STREAM_POOL = [
  L("thinking", "Re-running the affected test suite to confirm the change holds."),
  L("command", "$ npm test -- --changed"),
  L("output", "  ✓ 41 passing"),
  L("tool", "Edit  src/index.ts  +4 −2"),
  L("thinking", "Updating the changelog and inline docs for the new behavior."),
  L("tool", "Read  docs/architecture.md"),
  L("command", "$ npm run lint -- --fix"),
  L("output", "  ✓ no problems"),
  L("tool", "Edit  CHANGELOG.md  +6 −0"),
  L("thinking", "Verifying the public API surface stayed backward compatible."),
  L("command", "$ npx api-extractor run"),
  L("output", "  ✓ no breaking changes detected"),
  L("success", "  Step complete — moving to the next item."),
];

function mkAgent(o) {
  return Object.assign({
    pinned: false,
    pendingAction: null,
    steps: [],
    filesChanged: 0, additions: 0, deletions: 0,
    files: [],
  }, o);
}

const AGENTS = [
  mkAgent({
    id: "a-auth", role: "developer", name: "refactor-auth", model: MODELS[0],
    task: "Refactor authentication to rotating JWT refresh tokens",
    repo: "acme/api", branch: "feat/jwt-refresh", status: "running",
    progress: 68, step: "Wiring refresh endpoint into router",
    tokensIn: 184200, tokensOut: 41800, cost: 2.71, startedMin: 23,
    filesChanged: 6, additions: 214, deletions: 58,
    steps: [
      { label: "Audit current token strategy", done: true },
      { label: "Add rotating refresh-token store", done: true },
      { label: "Update JWT issue/verify", done: true },
      { label: "Wire refresh endpoint", done: false, active: true },
      { label: "Update OpenAPI spec", done: false },
      { label: "Open pull request", done: false },
    ],
    files: [
      { path: "src/auth/jwt.ts", add: 42, del: 7 },
      { path: "src/auth/refreshStore.ts", add: 88, del: 0 },
      { path: "src/auth/middleware.ts", add: 31, del: 22 },
      { path: "src/routes/auth.ts", add: 38, del: 12 },
    ],
    logs: SEED_LOGS.running_auth,
  }),
  mkAgent({
    id: "a-checkout", role: "engineer", name: "fix-checkout-bug", model: MODELS[1],
    task: "Fix race condition in checkout reservation flow",
    repo: "acme/api", branch: "fix/order-lock", status: "blocked",
    progress: 54, step: "Awaiting approval to run migration",
    tokensIn: 98400, tokensOut: 22100, cost: 3.18, startedMin: 41,
    filesChanged: 2, additions: 29, deletions: 11,
    steps: [
      { label: "Reproduce race condition", done: true },
      { label: "Patch reservation logic", done: true },
      { label: "Add unique index (migration)", done: false, active: true, blocked: true },
      { label: "Verify under load", done: false },
    ],
    files: [
      { path: "src/checkout/reserve.ts", add: 29, del: 11 },
    ],
    logs: SEED_LOGS.blocked_checkout,
    pendingAction: {
      type: "migration", risk: "high",
      title: "Run production database migration",
      command: "npx prisma migrate deploy --name order_lock",
      detail: "Adds a UNIQUE index on orders(cart_id, status). Alters a table with ~2.4M rows and will hold a write lock for an estimated 8–14s. Recommended during low-traffic window.",
    },
  }),
  mkAgent({
    id: "a-dark", role: "designer", name: "add-dark-mode", model: MODELS[0],
    task: "Implement dark mode across the customer dashboard",
    repo: "acme/dashboard", branch: "feat/dark-mode", status: "running",
    progress: 35, step: "Migrating hard-coded colors → tokens (3/9)",
    tokensIn: 71200, tokensOut: 18900, cost: 1.12, startedMin: 11,
    filesChanged: 14, additions: 121, deletions: 96,
    steps: [
      { label: "Extract color tokens", done: true },
      { label: "Build theme provider", done: true },
      { label: "Migrate components to tokens", done: false, active: true },
      { label: "Add theme toggle UI", done: false },
      { label: "Visual regression pass", done: false },
    ],
    files: [
      { path: "src/styles/tokens.css", add: 63, del: 0 },
      { path: "src/components/Sidebar.tsx", add: 8, del: 8 },
      { path: "src/components/Card.tsx", add: 5, del: 5 },
      { path: "src/components/Table.tsx", add: 11, del: 11 },
    ],
    logs: SEED_LOGS.running_darkmode,
  }),
  mkAgent({
    id: "a-tests", role: "tester", name: "test-payments-api", model: MODELS[1],
    task: "Raise payments API test coverage from 61% to 85%",
    repo: "acme/payments", branch: "test/payments-coverage", status: "running",
    progress: 47, step: "Fixing flaky webhook retry test",
    tokensIn: 142800, tokensOut: 38600, cost: 4.02, startedMin: 29,
    filesChanged: 3, additions: 335, deletions: 4,
    steps: [
      { label: "Map untested branches", done: true },
      { label: "Add refund tests", done: true },
      { label: "Add webhook tests", done: false, active: true },
      { label: "Hit 85% coverage gate", done: false },
    ],
    files: [
      { path: "tests/payments/refund.spec.ts", add: 134, del: 0 },
      { path: "tests/payments/webhook.spec.ts", add: 201, del: 4 },
    ],
    logs: SEED_LOGS.running_tests,
  }),
  mkAgent({
    id: "a-react", role: "developer", name: "upgrade-react-19", model: MODELS[0],
    task: "Upgrade the web app to React 19 and remove legacy shims",
    repo: "acme/web", branch: "chore/react-19", status: "blocked",
    progress: 80, step: "Awaiting approval to delete dead code",
    tokensIn: 211000, tokensOut: 52300, cost: 3.64, startedMin: 52,
    filesChanged: 9, additions: 64, deletions: 210,
    steps: [
      { label: "Run React 19 codemod", done: true },
      { label: "Fix breaking type changes", done: true },
      { label: "Remove legacy provider", done: true },
      { label: "Delete dead legacy files", done: false, active: true, blocked: true },
      { label: "Open pull request", done: false },
    ],
    files: [
      { path: "src/legacy/LegacyProvider.tsx", add: 0, del: 210 },
    ],
    logs: SEED_LOGS.blocked_react,
    pendingAction: {
      type: "delete", risk: "medium",
      title: "Delete 12 legacy files",
      command: "git rm src/legacy/**/*.tsx  (12 files, −1,840 lines)",
      detail: "These files are no longer imported after the React 19 migration. Deletion is reversible via git, but touches shared legacy utilities — worth a glance before approving.",
    },
  }),
  mkAgent({
    id: "a-i18n", role: "designer", name: "i18n-rollout", model: MODELS[0],
    task: "Set up internationalization and extract all UI strings",
    repo: "acme/web", branch: "feat/i18n", status: "running",
    progress: 58, step: "Adding ICU plural rules",
    tokensIn: 88300, tokensOut: 31200, cost: 1.49, startedMin: 18,
    filesChanged: 5, additions: 640, deletions: 28,
    steps: [
      { label: "Install i18n framework", done: true },
      { label: "Extract strings to catalog", done: true },
      { label: "Add plural / format rules", done: false, active: true },
      { label: "Wire language switcher", done: false },
    ],
    files: [
      { path: "locales/en.json", add: 312, del: 0 },
      { path: "locales/fr.json", add: 312, del: 0 },
      { path: "src/i18n/config.ts", add: 16, del: 0 },
    ],
    logs: SEED_LOGS.running_i18n,
  }),
  mkAgent({
    id: "a-perf", role: "analyst", name: "perf-audit-dash", model: MODELS[1],
    task: "Audit and cut dashboard initial bundle size",
    repo: "acme/dashboard", branch: "perf/bundle-diet", status: "running",
    progress: 41, step: "Replacing moment with native Intl",
    tokensIn: 124500, tokensOut: 29800, cost: 3.31, startedMin: 14,
    filesChanged: 4, additions: 21, deletions: 56,
    steps: [
      { label: "Profile initial render", done: true },
      { label: "Identify heavy deps", done: true },
      { label: "Replace moment → Intl", done: false, active: true },
      { label: "Lazy-load charts", done: false },
      { label: "Re-measure & report", done: false },
    ],
    files: [
      { path: "src/utils/date.ts", add: 18, del: 44 },
      { path: "src/views/Reports.tsx", add: 3, del: 6 },
    ],
    logs: SEED_LOGS.running_perf,
  }),
  mkAgent({
    id: "a-sec", role: "security", name: "security-patch", model: MODELS[2],
    task: "Patch dependency vulnerabilities flagged by npm audit",
    repo: "acme/api", branch: "chore/sec-patch", status: "running",
    progress: 76, step: "Re-running audit after bumps",
    tokensIn: 41200, tokensOut: 9800, cost: 0.38, startedMin: 6,
    filesChanged: 2, additions: 6, deletions: 6,
    steps: [
      { label: "Run npm audit", done: true },
      { label: "Bump safe transitive deps", done: true },
      { label: "Re-run audit", done: false, active: true },
      { label: "Open PR", done: false },
    ],
    files: [
      { path: "package.json", add: 6, del: 6 },
      { path: "package-lock.json", add: 0, del: 0 },
    ],
    logs: SEED_LOGS.running_sec,
  }),
  mkAgent({
    id: "a-migrate", role: "data", name: "migrate-to-postgres", model: MODELS[1],
    task: "Migrate analytics store from MongoDB to Postgres",
    repo: "acme/analytics", branch: "feat/pg-migration", status: "waiting",
    progress: 0, step: "Queued — position 1",
    tokensIn: 0, tokensOut: 0, cost: 0, startedMin: 0,
    logs: SEED_LOGS.waiting_migrate,
  }),
  mkAgent({
    id: "a-ci", role: "tester", name: "stabilize-flaky-ci", model: MODELS[0],
    task: "Stabilize the 6 flakiest CI tests blocking merges",
    repo: "acme/web", branch: "ci/flake-fix", status: "waiting",
    progress: 0, step: "Queued — position 2",
    tokensIn: 0, tokensOut: 0, cost: 0, startedMin: 0,
    logs: SEED_LOGS.waiting_ci,
  }),
  mkAgent({
    id: "a-images", role: "designer", name: "image-pipeline", model: MODELS[0],
    task: "Build a responsive image optimization pipeline",
    repo: "acme/web", branch: "feat/image-pipeline", status: "done",
    progress: 100, step: "PR #1284 opened · CI green",
    tokensIn: 96400, tokensOut: 24100, cost: 1.84, startedMin: 0, finishedMin: 34,
    filesChanged: 11, additions: 402, deletions: 73, pr: 1284,
    steps: [
      { label: "Audit current images", done: true },
      { label: "Add build-time optimizer", done: true },
      { label: "Generate responsive sets", done: true },
      { label: "Open pull request", done: true },
    ],
    logs: SEED_LOGS.done_images,
  }),
  mkAgent({
    id: "a-docs", role: "analyst", name: "api-docs-gen", model: MODELS[2],
    task: "Generate API reference docs from the OpenAPI spec",
    repo: "acme/api", branch: "docs/api-reference", status: "done",
    progress: 100, step: "PR #1279 opened · CI green",
    tokensIn: 52800, tokensOut: 18900, cost: 0.46, startedMin: 0, finishedMin: 12,
    filesChanged: 28, additions: 1840, deletions: 12, pr: 1279,
    steps: [
      { label: "Parse OpenAPI spec", done: true },
      { label: "Render reference pages", done: true },
      { label: "Open pull request", done: true },
    ],
    logs: SEED_LOGS.done_docs,
  }),
];

// ---- org hierarchy (top-down) + cross-agent workflow edges ----
const TREE = {
  id: "orchestrator", type: "agent", role: "orchestrator", name: "orchestrator",
  model: "claude-opus-4.1", note: "Planifie & répartit la charge",
  children: [
    { id: "lead-be", type: "agent", role: "lead", name: "backend-lead", repo: "acme/api", model: "claude-sonnet-4.5",
      children: [{ aid: "a-auth" }, { aid: "a-checkout" }, { aid: "a-sec" }, { aid: "a-migrate" }] },
    { id: "lead-fe", type: "agent", role: "lead", name: "frontend-lead", repo: "acme/web", model: "claude-sonnet-4.5",
      children: [{ aid: "a-dark" }, { aid: "a-react" }, { aid: "a-i18n" }, { aid: "a-perf" }, { aid: "a-ci" }] },
    { id: "lead-qa", type: "agent", role: "lead", name: "qa-lead", repo: "acme/payments", model: "claude-haiku-4",
      children: [{ aid: "a-tests" }] },
  ],
};
// dependency / handoff flow between worker agents
const EDGES = [
  { from: "a-auth", to: "a-tests", label: "à tester" },
  { from: "a-checkout", to: "a-tests", label: "à tester" },
  { from: "a-react", to: "a-dark", label: "débloque" },
  { from: "a-migrate", to: "a-perf", label: "alimente" },
  { from: "a-sec", to: "a-checkout", label: "préalable" },
];

export { AGENTS, STREAM_POOL, MODELS, L, TREE, EDGES };

// --- helpers partagés (statuts mock + formatters), repris de mc-overview.jsx ---
export const STATUS = {
  running: { label: "running", badge: "st-running", card: "s-running", clr: "var(--run)" },
  waiting: { label: "queued", badge: "st-waiting", card: "s-waiting", clr: "var(--wait)" },
  blocked: { label: "blocked", badge: "st-blocked", card: "s-blocked", clr: "var(--block)" },
  done: { label: "done", badge: "st-done", card: "s-done", clr: "var(--done)" },
};
export const fmtTok = (n) => (n >= 1000 ? (n / 1000).toFixed(n >= 100000 ? 0 : 1) + "k" : String(n));
export const fmtCost = (n) => "$" + n.toFixed(2);
export const fmtDur = (m) => (m <= 0 ? "—" : m < 60 ? m + "m" : Math.floor(m / 60) + "h " + (m % 60) + "m");
