#!/usr/bin/env sh
# Entrypoint API : migre la base, seed (idempotent, dev/test only), puis lance uvicorn.
set -e

# Comparaison insensible à la casse + préfixe (aligné sur apps/api/routers/auth.py qui fait
# `.lower().startswith("prod")` côté Python) : évite qu'une future valeur "production"/"PROD"
# passe le check applicatif mais rate ce check shell (et réintroduise le seed démo + --reload).
is_prod() {
	case "$(printf '%s' "${ENVIRONMENT:-}" | tr '[:upper:]' '[:lower:]')" in
		prod*) return 0 ;;
		*) return 1 ;;
	esac
}

echo "[entrypoint] alembic upgrade head"
alembic upgrade head

if is_prod; then
	echo "[entrypoint] ENVIRONMENT=prod → seed démo sauté (aucun compte demo@infinity.ae en prod)"
else
	echo "[entrypoint] seed (idempotent)"
	python -m apps.api.seed || echo "[entrypoint] seed ignoré"
fi

if is_prod; then
	echo "[entrypoint] uvicorn (prod, sans --reload)"
	exec uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
else
	echo "[entrypoint] uvicorn --reload (dev)"
	exec uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload
fi
