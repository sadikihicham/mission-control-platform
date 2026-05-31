#!/usr/bin/env bash
# Hook Claude Code · PreToolUse → heartbeat (montre l'activité, évite "stale").
CLI_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHONPATH="$CLI_DIR" python3 -m mc_platform beat >/dev/null 2>&1 || true
