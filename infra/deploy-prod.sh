#!/usr/bin/env sh
# Lance la stack prod co-hébergée avec la combinaison exacte de fichiers Compose requise
# (base + prod + fronted) et refuse de démarrer sur une version Docker Compose trop ancienne
# pour supporter le tag de fusion `!override` (>= 2.24) — sans ce garde, un `!override` non
# reconnu est silencieusement ignoré et les ports/volumes/profiles dev réapparaissent en prod.
# Voir docs/DEPLOY_FRONTED.md.
set -e

cd "$(dirname "$0")/.."

REQUIRED="2.24.0"
ACTUAL="$(docker compose version --short)"
LOWEST="$(printf '%s\n%s\n' "$REQUIRED" "$ACTUAL" | sort -V | head -n1)"
if [ "$LOWEST" != "$REQUIRED" ]; then
	echo "refuse : Docker Compose >= $REQUIRED requis (tag !override), trouvé $ACTUAL" >&2
	exit 1
fi

if [ ! -f infra/.env.prod ]; then
	echo "refuse : infra/.env.prod introuvable (cp infra/.env.prod.example infra/.env.prod, puis remplir)" >&2
	exit 1
fi

docker network inspect caddy_net >/dev/null 2>&1 || docker network create caddy_net

exec docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml \
	-f infra/docker-compose.prod-fronted.yml --env-file infra/.env.prod \
	up -d --build postgres redis ag-api ag-web
