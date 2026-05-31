"""Seed de la structure projet → tâches → sous-tâches → agents.

Issu de l'orchestration MVP (.mission-control/prompts/*). Les taux et états sont
ajoutés en live par services/projects.py à partir des statuts mission-control.
Sera remplacé par la base de données quand l'agent `api` (M3) livrera l'ingest.
"""

PROJECTS: list[dict] = [
    {
        "id": "mission-control-platform",
        "name": "Project Mission Control Platform",
        "description": "Cockpit de supervision du développement piloté par IA.",
        "status": "in_dev",
        "tasks": [
            {
                "id": "M0", "title": "Socle & Infra", "module": "M0-infra", "agents": ["socle"],
                "subtasks": [
                    "Layout monorepo", "API FastAPI + core", "Web Next.js + dark mode",
                    "docker-compose + healthchecks", "CI + smoke test", "Docs + placeholders",
                ],
            },
            {
                "id": "M1", "title": "Base de données", "module": "M1-database", "agents": ["db-core"],
                "subtasks": [
                    "Modèles SQLAlchemy", "Enums", "Alembic + migration initiale",
                    "Imports apps.api.models", "Seed admin + projet",
                ],
            },
            {
                "id": "M2", "title": "Authentification", "module": "M2-auth", "agents": ["auth"],
                "subtasks": ["security.py (hash + JWT)", "POST /auth/login", "get_current_user", "Tests auth"],
            },
            {
                "id": "M3", "title": "API REST + Ingest", "module": "M3-api", "agents": ["api"],
                "subtasks": [
                    "Schémas Pydantic", "Router projets", "Router agents",
                    "/stats/dashboard", "POST /agents/heartbeat", "Publish Redis",
                ],
            },
            {
                "id": "M4", "title": "Temps réel", "module": "M4-realtime", "agents": ["realtime"],
                "subtasks": ["WS /ws", "Abonné Redis relay", "Détection stale", "stats.update", "Tests WS"],
            },
            {
                "id": "M5", "title": "Agent CLI", "module": "M5-cli", "agents": ["agent-cli"],
                "subtasks": ["CLI Typer", "Config env", "Hooks Claude Code", "Tests vs mock", "README install"],
            },
            {
                "id": "M6", "title": "Dashboard", "module": "M6-frontend", "agents": ["dashboard"],
                "subtasks": ["Layout + nav + dark", "Client API", "Vue live agents", "KPIs", "Client WS", "Login"],
            },
            {
                "id": "M3.5", "title": "Bridge mc → web", "module": "M3.5-bridge", "agents": ["mc-bridge"],
                "subtasks": [
                    "Service lecture statuts", "Endpoints /agents /stats",
                    "Hiérarchie projets/tâches", "Vue web drill-down",
                ],
            },
        ],
    },
]
