# Documentation technique

- **Contrats inter-modules** : `../.mission-control/CONTRACTS.md` (DB, Auth, REST, Heartbeat, WebSocket + décisions verrouillées).
- **Prompts d'agents** : `../.mission-control/prompts/`.
- **Lancer le projet** : voir `../README.md`.

## Roadmap MVP → V1

| Vague | Agents | Livraison |
|------|--------|-----------|
| 1 | `socle` | scaffold monorepo + docker-compose + contrats ✅ |
| 2 | `db-core`, `agent-cli`, `dashboard` | modèles DB, CLI heartbeat, scaffold front |
| 3 | `auth`, `api`, `realtime` | JWT, REST + ingest, WS + Redis + stale |
| 4 | intégration | dashboard live branché bout-en-bout |

Détail dans la conversation d'orchestration et `CONTRACTS.md`.
