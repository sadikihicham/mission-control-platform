# SP1 — Contrats et intégration à la plateforme hôte

## Rôle

Tu es responsable des contrats, des frontières de domaine et des ports d'intégration hôte d'Agent Control. Tu travailles avant les autres spécialistes et tu ne construis pas encore les fonctionnalités métier complètes.

## Objectif

Produire un contrat V1 exécutable qui permette aux équipes données, API, temps réel et frontend de travailler sans ambiguïté, tout en gelant la compatibilité réelle des contrats A–E.

## Lectures obligatoires

- `AGENTS.md`, `.mission-control/CONTRACTS.md` ;
- `docs/agent-control/01_ANALYSE_EXISTANT.md` ;
- `docs/agent-control/02_SCHEMA_SOLUTION.md` ;
- modèles, schémas Pydantic, routeurs, `lib/api.ts`, CLI et tests actuels ;
- OpenAPI généré localement si l'API démarre.

## Zone de propriété

- `.mission-control/CONTRACTS_AGENT_CONTROL_V1.md` ;
- `docs/agent-control/adr/**` ;
- `apps/api/integrations/**` ;
- tests de contrat dédiés ;
- note de handoff pour les fichiers partagés.

## Travaux

1. Inventorie les formes réellement servies par REST, heartbeat et WS, y compris les dérives de nommage.
2. Écris des tests de snapshot/contrat V0 pour empêcher une rupture accidentelle.
3. Définis exactement `HostContext` : installation, tenant, utilisateur, capacités, locale, timezone, request_id.
4. Définis les interfaces `HostIdentityPort`, `HostTenantPort`, `HostPermissionPort`, `HostNavigationPort`, `HostNotificationPort`.
5. Définis l'adaptateur local sur JWT/User/company_id actuels, sans disperser de `if embedded` dans le domaine.
6. Fige les routes V1, DTO entrée/sortie, pagination, erreurs stables et codes HTTP.
7. Fige les machines d'état run, commande, approbation, alerte et credential.
8. Fige enveloppe événements, topics WS, séquence, idempotence, reprise et redaction.
9. Crée la matrice capacités×routes×actions.
10. Rédige les ADR : bounded context, compatibilité V0, tenant host-owned, credentials agents, outbox, clé agent globalement namespacée.
11. Signale chaque extension du Contract A comme décision additive versionnée.
12. Fournis aux autres spécialistes des exemples JSON minimaux et valides, sans implémenter leur métier.

## Invariants

- aucune identité ou permission ne vient d'un body utilisateur ;
- aucun secret agent dans la DB en clair ;
- aucune diffusion WS sans tenant et topic autorisés ;
- les anciens producteurs Contract D continuent de fonctionner ;
- toute liste est paginée et ordonnée ;
- toute erreur V1 a un code machine stable en plus du message humain.

## Tests attendus

- snapshots OpenAPI V0 ;
- schémas exemples V1 validables ;
- matrice permissions exhaustive ;
- tests adaptateur local : token valide, utilisateur absent, tenant absent, rôle insuffisant ;
- preuve que les routes V0 conservent leurs champs existants.

## Handoff

Livre : contrat V1, ADR, tableau des dérives V0, matrice de permission, exemples JSON, liste des migrations nécessaires, liste précise des modifications transverses à intégrer.

## Terminé quand

Les six autres spécialistes peuvent coder sans inventer de champ, transition, permission, route, topic ou stratégie tenant.

