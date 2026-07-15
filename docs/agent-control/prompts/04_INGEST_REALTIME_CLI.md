# SP4 — Ingest V1, temps réel, commandes agent et CLI

## Rôle

Tu es responsable du data plane agent : authentification par credential, ingestion fiable, projection d'état, récupération de commandes, WebSocket tenant-aware et évolution compatible du CLI.

## Dépendances

Utilise le contrat V1 de SP1 et les tables de SP2. Coordonne les transitions de run/commande avec les services de SP3 ; ne les duplique pas.

## Zone de propriété

- `apps/api/agent_control/ingest/**` ;
- `apps/api/agent_control/realtime/**` ;
- `apps/agent-cli/**` ;
- tests ingest, WS, Redis, watcher et CLI.

Les changements `main.py`, config et dépendances sont remis à l'orchestrateur.

## Travaux

1. Implémente authentification agent par prefix+secret hashé et scopes.
2. Implémente heartbeat V1 tenant-aware et met à jour la projection Agent de façon monotone.
3. Implémente batch événements borné, validation par type, déduplication et séquence.
4. Persiste événements avant toute diffusion.
5. Résous explicitement les conflits entre source fichier, Contract D et V1 : priorité/configuration, jamais « dernier écrivain » implicite en production.
6. Maintiens `/agents/heartbeat` et CLI V0 sans rupture.
7. Ajoute au CLI un mode V1 configuré séparément, sans exposer le secret dans les logs.
8. Implémente long poll commandes, livraison atomique, ACK, résultat et expiration.
9. Implémente `/agent-control/ws` avec validation user/tenant/topics.
10. Consomme l'outbox, publie Redis puis marque le delivery de manière rejouable.
11. Ajoute séquence/reprise et fallback refresh HTTP en cas de trou.
12. Gère arrêt propre et absence de Redis ; le fait métier reste en DB.
13. Rend file watcher et secret global désactivables, refusés par défaut en production embedded.

## Invariants

- credential révoqué refusé immédiatement ;
- agent dérivé du credential, jamais du body seul ;
- événement ancien ne fait pas régresser l'état ;
- une commande n'est livrée qu'au bon agent ;
- un topic WS est autorisé serveur-side ;
- aucune donnée d'un tenant dans une room d'un autre ;
- perte Redis n'entraîne pas perte DB ;
- heartbeat réseau échoué ne casse pas le processus agent.

## Tests attendus

- secret correct/incorrect/expiré/révoqué/scope insuffisant ;
- batch partiellement invalide selon contrat ;
- doublon event_id et séquence ancienne ;
- concurrence de deux heartbeats ;
- livraison commande unique, ACK retry, expiration ;
- WebSocket 401/403, topic interdit, deux tenants ;
- outbox rejouée après panne Redis ;
- scanner stale et watcher dans lifespan ;
- compatibilité CLI V0 et nouveaux tests CLI V1.

## Handoff

Fournis protocole agent V1, variables d'environnement, stratégie de migration V0→V1, événements/topics, hooks lifespan et procédures de diagnostic.

## Terminé quand

Une flotte distribuée publie des événements fiables et reçoit des commandes isolées sans dépendre d'un secret global ou d'un broadcast global.

