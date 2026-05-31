# Agent `agent-cli` — M5 Agent CLI (VAGUE 2, peu de dépendances)

Tu es l'agent `agent-cli`. Tu construis le CLI `mc-platform` qui publie les
heartbeats des agents Claude Code vers l'API. Tu codes contre le **Contract D**
(HTTP), pas contre l'implémentation de `api` — tu peux donc démarrer tôt.

## Bind status
```bash
source "$HOME/.claude/skills/mission-control/scripts/mc.sh" agent-cli
mc working "scaffold CLI Typer" 0 0 5
```

## Scope
`apps/agent-cli/` — Python + Typer.

## Tâches (total 5)
1. CLI Typer : commandes `beat`, `working`, `blocked`, `done`, `report` qui POST sur `/agents/heartbeat` (Contract D) avec header `X-MC-Token`.
2. Config via env (`MC_API_URL`, `MC_INGEST_TOKEN`, `MC_AGENT_KEY`).
3. Hooks Claude Code : scripts pour `SessionStart` / `PreToolUse` / `Stop` qui appellent le CLI → état `working`/`done` automatiquement.
4. Tests contre un mock du Contract D (sans dépendre de `api` réel).
5. README : installation des hooks dans `settings.json`.

## Contrats à respecter
Contract D de `.mission-control/CONTRACTS.md` — le payload doit matcher au
champ près (il est aligné sur le JSON `mc` existant).

## Dépendances
Quasi nulles : démarre après `socle` (layout). Validation finale contre `api`
réel en vague 4.

## Definition of done
`mc-platform beat` envoie un POST valide accepté par un serveur respectant le
Contract D ; hooks documentés. → `mc done "CLI + hooks OK vs Contract D" 100 5 5`
