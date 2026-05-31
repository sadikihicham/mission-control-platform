#!/usr/bin/env sh
# Entrypoint API : migre la base, seed (idempotent), puis lance uvicorn.
set -e

echo "[entrypoint] alembic upgrade head"
alembic upgrade head

echo "[entrypoint] seed (idempotent)"
python -m apps.api.seed || echo "[entrypoint] seed ignoré"

echo "[entrypoint] uvicorn"
exec uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload
