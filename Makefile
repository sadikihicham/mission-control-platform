COMPOSE := docker compose -f infra/docker-compose.yml

.PHONY: help up down restart logs ps psql redis-cli seed web dev full clean

help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Démarre le backend (postgres + redis + api, migre + seed auto) → API sur :8008
	$(COMPOSE) up -d --build
	@echo "API → http://localhost:8008/health  ·  docs → http://localhost:8008/docs"

down: ## Arrête le backend
	$(COMPOSE) down

restart: down up ## Redémarre le backend

logs: ## Suit les logs de l'API
	$(COMPOSE) logs -f ag-api

ps: ## État des conteneurs
	$(COMPOSE) ps

psql: ## Ouvre psql sur la base
	$(COMPOSE) exec postgres psql -U mc -d mission_control

redis-cli: ## Ouvre redis-cli
	$(COMPOSE) exec redis redis-cli

seed: ## (Re)joue le seed
	$(COMPOSE) exec ag-api python -m apps.api.seed

contracts: ## Régénère les types TS depuis l'OpenAPI (packages/contracts + lib/contracts.ts)
	$(COMPOSE) exec -T ag-api python -m packages.contracts.generate

web: ## Lance le frontend en dev (Next.js sur :3100)
	cd apps/web && npm install && NEXT_PUBLIC_API_URL=http://localhost:8008 npm run dev -- -p 3100

dev: up ## Backend (compose) + rappel pour le front
	@echo ""
	@echo "Backend prêt. Lance le front dans un autre terminal :  make web"
	@echo "Puis ouvre http://localhost:3100  (login: demo@infinity.ae / password)"

full: ## Tout en conteneurs (web inclus, build long)
	$(COMPOSE) --profile full up -d --build

clean: ## Arrête tout + supprime le volume de données
	$(COMPOSE) down -v

test: ## Lance les tests d'intégration (conteneur api, DB éphémère mc_test)
	$(COMPOSE) exec -T postgres sh -c "psql -U mc -d mission_control -tc \"SELECT 1 FROM pg_database WHERE datname='mc_test'\" | grep -q 1 || createdb -U mc mc_test"
	$(COMPOSE) exec -T -e DATABASE_URL=postgresql+psycopg://mc:mc@postgres:5432/mc_test -e JWT_SECRET=test-secret -e MC_INGEST_TOKEN=test-ingest ag-api pytest -q
