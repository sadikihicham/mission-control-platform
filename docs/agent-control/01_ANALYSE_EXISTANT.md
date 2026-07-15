# Analyse de l'existant — module de gestion d'agents

Statut : analyse documentaire et statique du dépôt  
Date : 13 juillet 2026  
Périmètre : backend, frontend, agent CLI, temps réel, données, sécurité, tests et intégration dans une plateforme métier existante

## 1. Résumé exécutif

Le dépôt contient déjà un MVP cohérent de supervision d'agents : authentification, persistance PostgreSQL, heartbeat, détection des agents silencieux, diffusion WebSocket, tableau de bord, projets, rôles, CLI et environnement Docker. Il ne faut donc pas reconstruire un produit depuis zéro.

En revanche, le résultat actuel est encore un cockpit autonome de démonstration, pas un module métier intégrable et multi-tenant prêt pour la production. Les principales limites sont :

- coexistence de données réelles, de seeds statiques et de mocks frontend ;
- absence de frontière d'intégration avec l'identité, les tenants, les permissions et la navigation d'une plateforme hôte ;
- secret d'ingest global au lieu d'identités d'agents révocables ;
- absence de notions complètes de run, étape, commande, approbation et coût ;
- temps réel diffusé à tous les clients authentifiés, sans cloisonnement de tenant ;
- types TypeScript non générés et plusieurs vues encore sous `@ts-nocheck` ;
- couverture limitée des tâches de fond, du WebSocket, de la concurrence et de l'isolation.

La bonne stratégie est une consolidation incrémentale : conserver les contrats A–E comme compatibilité V0, introduire un contrat de module V1 versionné, remplacer progressivement les sources de démonstration par la base, puis exposer le produit au travers d'adaptateurs de plateforme hôte.

## 2. Ce qui est effectivement livré

### Socle et exploitation locale

- monorepo FastAPI + Next.js + PostgreSQL + Redis ;
- Docker Compose avec healthchecks et migrations automatiques ;
- Makefile pour démarrage, logs, seed, tests et accès DB/Redis ;
- CI séparée backend/frontend ;
- configuration centralisée dans `apps/api/core/config.py` ;
- moteur et sessions SQLAlchemy chargés paresseusement.

### Identité et sécurité de base

- login JWT HS256, expiration et vérification utilisateur ;
- récupération du compte courant ;
- rôles hiérarchiques `viewer < developer < pm < cto < admin` ;
- garde `require_role(minimum)` ;
- mot de passe oublié anti-énumération ;
- reset token hashé, expirant et à usage unique ;
- comptes de démonstration par rôle.

### Registre et télémétrie d'agents

- table `agents` avec état, tâche, progression, module, branche et blocage ;
- ingest `POST /agents/heartbeat` protégé par `X-MC-Token` ;
- rejet de `stale` à l'ingest, car cet état est dérivé côté serveur ;
- journal d'activité par heartbeat ;
- deux producteurs unifiés vers la même table : fichiers `.mission-control/status` et CLI `mc-platform` ;
- CLI sans dépendance, non bloquant si l'API est indisponible ;
- commandes ergonomiques `working`, `blocked`, `done`, `idle` et `beat`.

### Temps réel

- Redis pub/sub sur `mc:events` ;
- WebSocket natif `/ws?token=...` ;
- scanner d'agents silencieux toutes les 15 secondes ;
- watcher des fichiers de statut toutes les 2 secondes ;
- événements `agent.update`, `agent.stale`, `stats.update` et `refresh` ;
- reconnexion et polling de secours côté dashboard.

### Projets et interface

- CRUD projets en base avec RBAC `pm+` ;
- association facultative à un dépôt GitHub ;
- liste et détail d'agents avec historique ;
- dashboard trilingue français/anglais/arabe et RTL ;
- vues flotte, projets, agent, hiérarchie, audit, coût, commandes et réglages ;
- palette de commandes, thèmes et alertes visuelles.

## 3. Écarts entre le résultat et une solution intégrable

| Domaine | État actuel | Écart pour le module cible | Priorité |
|---|---|---|---|
| Données projets | mélange seed statique + projets DB | une source DB unique et des tâches réelles | critique |
| Données frontend | vues live + `mc-data.ts` mock | supprimer tout compteur et workflow mock | critique |
| Multi-tenant | `company_id` réservé sur users/projects | agents, événements, WS et requêtes non cloisonnés | critique |
| Auth hôte | auth locale uniquement | adaptateur JWT/SSO et contexte tenant de la plateforme | critique |
| Ingest | un secret global | credential par agent, hash, scopes, rotation, révocation | critique |
| Contrôle | heartbeat uniquement | runs, étapes, commandes pause/retry/cancel et ACK | haute |
| Human-in-loop | blocage textuel | demandes d'approbation, décision, SLA et audit | haute |
| Coûts | écran non relié | usage tokens/coût/durée/budget par tenant/projet/agent | haute |
| Contrats TS | placeholder | génération OpenAPI et détection de dérive | haute |
| Temps réel | broadcast global | rooms/filtre tenant + reprise et séquence | critique |
| Sécurité | JWT + RBAC de base | rate limits, rotation, audit, CSP, secrets prod | haute |
| Tests | HTTP principaux | WS, lifespan, concurrence, cross-tenant, E2E | haute |
| Exploitation | healthcheck simple | métriques, logs structurés, alertes et runbooks | moyenne |
| Intégration UI | page racine monolithique | route `/agent-control`, shell hôte et feature flag | critique |

## 4. Risques précis observés

### 4.1 Contrats et schémas en dérive

- `.mission-control/CONTRACTS.md` décrit cinq KPI projet/agent, tandis que `DashboardStats` expose aujourd'hui sept KPI orientés agents.
- Le message temps réel produit par l'ingest utilise `agent_key` et `last_heartbeat`, tandis que le DTO REST frontend utilise `agent` et `updated_at`.
- `packages/contracts` est encore un placeholder ; les types frontend sont maintenus manuellement.
- Le README annonce encore certains modules « à venir » alors qu'ils sont implémentés.

Conséquence : une intégration externe peut compiler tout en interprétant des formes différentes selon HTTP ou WebSocket.

### 4.2 Sources de vérité multiples

- `services/projects.py` concatène une vitrine statique et les projets DB.
- Les projets DB renvoient `tasks=[]`, alors que les projets seedés ont une hiérarchie détaillée.
- `Shell.tsx` calcule encore ses compteurs depuis `mc-data.ts`.
- `page.tsx` utilise des données live pour certaines vues et mock pour d'autres.
- plusieurs composants ont `@ts-nocheck`.

Conséquence : les écrans peuvent se contredire et une action utilisateur peut viser une entité non éditable de démonstration.

### 4.3 Isolation et intégration hôte incomplètes

- `company_id` existe sur `users` et `projects`, mais pas sur `agents`, `tasks` ou `activity_logs`.
- `agent_key` est globalement unique.
- le WebSocket valide le JWT, mais ne vérifie ni l'existence actuelle de l'utilisateur ni son tenant avant de diffuser tous les événements.
- les listes ne filtrent pas par entreprise.
- le JWT ne porte pas de contexte d'installation ou de tenant sélectionné.

Conséquence : le mode multi-tenant ne doit pas être activé avant la mise en place d'un contexte hôte et de tests négatifs systématiques.

### 4.4 Identité des agents trop faible

- tous les agents partagent `MC_INGEST_TOKEN` ;
- aucune rotation/révocation par agent ;
- aucune portée par projet ou environnement ;
- aucune protection native contre répétition ou ordre ancien ;
- les fichiers locaux peuvent écraser le même agent que l'API selon la dernière synchronisation.

Conséquence : le contrat D convient au développement local, mais pas à une flotte métier distribuée.

### 4.5 Modèle métier incomplet

Les tables actuelles couvrent l'état courant mais pas le cycle complet :

- pas de session/run d'agent ;
- pas d'étape ni tool call ;
- pas de commande serveur avec accusé de réception ;
- pas de demande/validation humaine structurée ;
- pas de politique ou budget ;
- pas de mesure d'usage ou de coût ;
- pas d'alerte persistée et acquittable ;
- `Task` ne porte que titre, statut libre et affectation.

Conséquence : le système supervise, mais ne gouverne pas encore l'exécution.

### 4.6 Tests et exploitation

- les tests HTTP n'activent volontairement pas le lifespan ; les scanners et watchers ne sont donc pas couverts ;
- pas de tests WebSocket/Redis ni de reconnexion ;
- pas de test de concurrence sur les upserts/heartbeats ;
- pas de test E2E frontend ;
- pas de pagination des activités ou agents ;
- reset password n'a pas encore d'envoi email production ;
- secrets de développement utilisables par défaut.

## 5. Décision d'architecture recommandée

Transformer le cockpit actuel en bounded context « Agent Control » intégrable, avec trois couches :

1. **Adaptateurs hôte** : identité, tenant, permissions, navigation, notifications et design system de la plateforme métier.
2. **Noyau Agent Control** : registre, projets/tâches, runs, commandes, approbations, politiques, usage et audit.
3. **Compatibilité Mission Control V0** : routes A–E, CLI et fichiers locaux conservés durant la migration.

La plateforme hôte reste propriétaire des utilisateurs, organisations et rôles métier globaux. Le module garde seulement les références externes et ses permissions propres. En mode autonome de développement, un adaptateur local réutilise les tables et JWT actuels.

## 6. Séquence de consolidation

1. Figer un inventaire des contrats réellement servis et ajouter des tests de compatibilité V0.
2. Créer un nouveau contrat versionné `/agent-control/v1` sans casser A–E.
3. Introduire l'adaptateur d'identité/tenant hôte et le cloisonnement systématique.
4. Remplacer seeds et mocks par PostgreSQL, puis générer les types TS.
5. Ajouter credentials par agent, événements séquencés, runs et tâches réelles.
6. Ajouter commandes, approbations et politiques.
7. Relier coût, audit, alertes et reporting.
8. Extraire le frontend dans `/agent-control` et l'intégrer au shell hôte.
9. Couvrir WebSocket, cross-tenant, concurrence, E2E et exploitation.
10. Désactiver les chemins de démonstration en production via configuration explicite.

## 7. Critère de réussite

La transformation est réussie lorsque la plateforme hôte peut activer le module pour un tenant, transmettre son utilisateur courant, enregistrer des agents avec des credentials isolés, suivre leurs runs et tâches, demander une validation humaine, envoyer des commandes sûres, mesurer les coûts et consulter l'audit, sans exposer aucune donnée d'un autre tenant et sans casser les producteurs Contract D existants.

