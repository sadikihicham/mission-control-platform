# SP3 — API métier, orchestration et contrôle humain

## Rôle

Tu es propriétaire des schémas Pydantic, services métier et routeurs V1 de registre, projets, tâches, runs, commandes, approbations et politiques.

## Dépendances

Consomme exclusivement le contrat V1 figé et les modèles livrés par SP2. Si un modèle manque, produis une demande de handoff précise au lieu de contourner la DB avec du JSON non contractuel.

## Zone de propriété

- `apps/api/agent_control/schemas/**` ;
- `apps/api/agent_control/services/**` hors services réservés à SP6 ;
- `apps/api/agent_control/routers/**` hors ingest/realtime ;
- tests services/routes associés.

`main.py` reste intégré par l'orchestrateur.

## Travaux

1. Implémente dépendances de contexte hôte, tenant et capacité.
2. Implémente registre : CRUD borné, suspendre, reprendre, archiver.
3. Implémente création/rotation/révocation de credentials en affichant le secret une seule fois.
4. Remplace le service projets hybride par une source DB V1, sans casser les réponses V0.
5. Implémente tâches/sous-tâches, ordre, priorité, dépendances, affectations et critères d'acceptation.
6. Implémente création/lecture de runs, transitions autorisées et retry par nouveau run.
7. Construis timeline depuis étapes/événements, paginée et redacted.
8. Implémente commandes idempotentes, expiration et annulation opérateur.
9. Implémente moteur de politiques déterministe `allow|deny|require_approval`.
10. Implémente demandes d'approbation et décision avec version optimiste.
11. Libère une commande risquée seulement après approbation valide et non expirée.
12. Écris l'audit/outbox dans la même transaction que l'action métier.
13. Utilise chargements SQL explicites et élimine N+1.
14. Retourne erreurs machine stables définies par SP1.

## Invariants

- chaque service reçoit `HostContext` ;
- aucune recherche par ID seul sans tenant ;
- états terminaux immuables ;
- routeurs sans logique métier ;
- événements outbox après mutation, jamais publication Redis directe avant commit ;
- secrets et correction de politique internes absents des DTO publics ;
- permission UI non considérée comme contrôle.

## Tests attendus

- CRUD et pagination ;
- 401/403/404 sans fuite d'existence cross-tenant ;
- matrices de rôles/capacités ;
- transitions run/commande/approbation ;
- double décision concurrente ;
- idempotency keys ;
- credential créé/roté/révoqué ;
- policy allow/deny/approval ;
- N+1 contrôlé sur listes principales ;
- non-régression routes projets/agents V0.

## Handoff

Fournis routes livrées, DTO effectifs, codes d'erreur, événements outbox, dépendances de configuration et points d'inclusion dans `main.py`.

## Terminé quand

Un opérateur peut gérer agents/projets/tâches/runs et une action à risque est bloquée jusqu'à une décision humaine auditée.

