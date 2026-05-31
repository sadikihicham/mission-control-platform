#!/usr/bin/env bash
# Hook Claude Code · Stop → heartbeat final (l'agent reste assigné ; le passage
# en "done" est volontairement manuel via `mc-platform done`).
CLI_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHONPATH="$CLI_DIR" python3 -m mc_platform beat >/dev/null 2>&1 || true
