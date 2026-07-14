# mc-platform — CLI agent (M5)

CLI **zéro dépendance** (stdlib `argparse` + `urllib`) qui publie les heartbeats
d'un agent Claude Code vers Project Mission Control (`POST /agents/heartbeat`,
Contract D). Conçu pour tourner dans n'importe quel environnement d'agent.

## Configuration (variables d'environnement)

| Variable | Défaut | Rôle |
|---|---|---|
| `MC_API_URL` | `http://localhost:8000` | base de l'API |
| `MC_INGEST_TOKEN` | `dev-ingest-token` | header `X-MC-Token` — secret d'**enrôlement** (1er contact seulement, voir ci-dessous) |
| `MC_AGENT_KEY` | `agent` | identifiant de l'agent |
| `MC_PROJECT` | _(vide)_ | slug du projet (optionnel) |
| `MC_TOKEN_FILE` | `~/.mc-platform/credentials.json` | où persister le token émis à l'enrôlement |

### Identité par agent (enrôlement)

Ce client envoie `X-MC-Enroll: 1` à chaque heartbeat. Au premier heartbeat d'un
`agent_key`, le serveur émet un token propre à cet agent (champ `agent_token` dans la
réponse) ; ce client le persiste dans `MC_TOKEN_FILE` (mode `0600`) et l'utilise ensuite
à la place de `MC_INGEST_TOKEN` pour ce même `agent_key`. La persistance n'est jamais
bloquante : si l'écriture échoue, le heartbeat aboutit quand même (le prochain appel
retentera l'enrôlement avec le secret partagé).

## Usage

```bash
# via le module (sans installation)
PYTHONPATH=apps/agent-cli python3 -m mc_platform working "Implémente l'auth" 45 3 7
PYTHONPATH=apps/agent-cli python3 -m mc_platform blocked "Besoin du schéma DB"
PYTHONPATH=apps/agent-cli python3 -m mc_platform done
PYTHONPATH=apps/agent-cli python3 -m mc_platform beat        # heartbeat silencieux

# ou installé (console script `mc-platform`)
pip install -e apps/agent-cli
mc-platform report --state working --task "..." --progress 50 --done 2 --total 5 --module M5
```

Le heartbeat est **non bloquant** : si l'API est injoignable, un avertissement
s'affiche mais le code de sortie reste `0` (ne casse jamais le flux de l'agent).

## Hooks Claude Code

Trois hooks dans `hooks/` instrumentent automatiquement une session :
`session_start.sh` (→ working), `pre_tool_use.sh` et `stop.sh` (→ beat).

Enregistrement dans `~/.claude/settings.json` (adapter les chemins absolus) :

```json
{
  "env": { "MC_API_URL": "http://localhost:8008", "MC_AGENT_KEY": "mon-agent", "MC_INGEST_TOKEN": "dev-ingest-token" },
  "hooks": {
    "SessionStart": [{ "hooks": [{ "type": "command", "command": "<repo>/apps/agent-cli/hooks/session_start.sh" }] }],
    "PreToolUse":  [{ "matcher": "*", "hooks": [{ "type": "command", "command": "<repo>/apps/agent-cli/hooks/pre_tool_use.sh" }] }],
    "Stop":        [{ "hooks": [{ "type": "command", "command": "<repo>/apps/agent-cli/hooks/stop.sh" }] }]
  }
}
```

## Tests

```bash
PYTHONPATH=apps/agent-cli python3 apps/agent-cli/tests/test_client.py   # runner stdlib
# ou, avec pytest installé :
PYTHONPATH=apps/agent-cli pytest apps/agent-cli/tests
```

> Les tests tournent contre un **mock du Contract D** (serveur HTTP stdlib).
> L'endpoint réel `POST /agents/heartbeat` arrive avec l'agent `api` (M3).
