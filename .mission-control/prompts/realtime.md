# Agent `realtime` — M4 Temps réel (VAGUE 3)

Tu es l'agent `realtime`. Tu possèdes le Contract E : tu abonnes le serveur à
Redis et tu relaies les events aux clients WebSocket. Tu dérives aussi l'état
`stale`.

## Bind status
```bash
source "$HOME/.claude/skills/mission-control/scripts/mc.sh" realtime
mc working "WS endpoint + redis sub" 0 0 5
```

## Scope
`apps/api/realtime/` — WS natif FastAPI + abonnement Redis + détection stale.

## Tâches (total 5)
1. `WebSocket /ws?token=<JWT>` : valide le JWT (via `auth.get_current_user`), gère connect/disconnect, ConnectionManager (fan-out multi-clients).
2. Abonné Redis sur `mc:events` : chaque message reçu est relayé à tous les clients WS connectés.
3. Tâche de fond : scan périodique de `agents.last_heartbeat` ; si un agent `working` dépasse 30s de silence → émettre `agent.stale` (Contract E).
4. Émettre `stats.update` quand les KPIs changent.
5. Tests : 2 clients WS reçoivent un message publié sur Redis ; passage `stale` après 30s.

## Contrats à respecter
Contract E (owner) de `.mission-control/CONTRACTS.md`. Tu CONSOMMES les
publications de `api` (tâche 6 de `api`) — tu ne publies pas les heartbeats
toi-même, tu les relaies.

## Dépendances
Besoin de Redis (`socle`) et de la dépendance auth (`auth`). Le format des
messages est déjà figé (Contract E) → tu peux coder l'infra WS en parallèle de
`api` et brancher Redis dès que `api` publie.

## Definition of done
Un message publié sur `mc:events` arrive à tous les clients `/ws` ; un agent
silencieux passe `stale` en < 35s. → `mc done "WS+redis+stale OK" 100 5 5`
