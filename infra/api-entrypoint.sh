#!/usr/bin/env sh
# Entrypoint API : migre la base, seed (idempotent, dev/test only), puis lance uvicorn.
set -e

echo "[entrypoint] alembic upgrade head"
alembic upgrade head

if [ "$ENVIRONMENT" = "prod" ]; then
	echo "[entrypoint] ENVIRONMENT=prod → seed démo sauté (aucun compte demo@infinity.ae en prod)"
else
	echo "[entrypoint] seed (idempotent)"
	python -m apps.api.seed || echo "[entrypoint] seed ignoré"
fi

if [ "$ENVIRONMENT" = "prod" ]; then
	echo "[entrypoint] uvicorn (prod, sans --reload)"
	exec uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
else
	echo "[entrypoint] uvicorn --reload (dev)"
	exec uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload
fi
