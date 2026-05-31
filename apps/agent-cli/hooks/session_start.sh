#!/usr/bin/env bash
# Hook Claude Code · SessionStart → l'agent passe "working".
# Non bloquant : n'échoue jamais (|| true).
CLI_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHONPATH="$CLI_DIR" python3 -m mc_platform working "session démarrée" >/dev/null 2>&1 || true
