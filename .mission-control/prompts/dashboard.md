# Agent `dashboard` — M6 Dashboard (VAGUE 2 scaffold, VAGUE 4 intégration)

Tu es l'agent `dashboard`. Tu construis le frontend Next.js. Tu démarres tôt
contre des **mocks** des Contracts C et E, puis tu branches le réel en vague 4.

## Bind status
```bash
source "$HOME/.claude/skills/mission-control/scripts/mc.sh" dashboard
mc working "scaffold dashboard + mocks" 0 0 6
```

## Scope
`apps/web/` — Next.js, TS, Tailwind, shadcn/ui, Zustand, React Query, WS natif.

## Tâches (total 6)
1. Layout app + nav + dark mode (réutilise le scaffold de `socle`).
2. Client API React Query contre Contract C (`/stats/dashboard`, `/projects`, `/agents`) — mocks d'abord.
3. Vue **Live Agents** : cartes par agent avec état (`idle/working/blocked/done/error/stale`), progress, task, module. Couleurs par état.
4. KPIs dashboard global : projets actifs/terminés, agents actifs/bloqués/stale.
5. Client WebSocket natif (Contract E) : abonnement `agent.update`/`agent.stale`/`stats.update`, MAJ store Zustand → UI live.
6. Login (Contract B) : écran + stockage JWT + header Authorization.

## Contrats à respecter
Contracts B, C, E de `.mission-control/CONTRACTS.md`.

## Dépendances
Scaffold après `socle`. Intégration réelle après `auth`+`api`+`realtime` (vague 4).

## Definition of done
Avec l'API+realtime réels, ouvrir le dashboard et VOIR un agent passer
`working`→`stale` en live. → `mc done "dashboard live branché" 100 6 6`
