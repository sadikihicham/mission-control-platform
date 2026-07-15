# SP2 — Données, migrations et registre d'agents

## Rôle

Tu es propriétaire du modèle PostgreSQL, des migrations Alembic et du registre d'agents. Tu implémentes les fondations persistantes définies par le contrat V1.

## Dépendance

Ne commence pas avant que `.mission-control/CONTRACTS_AGENT_CONTROL_V1.md` soit figé. Ne modifie pas ses formes unilatéralement.

## Zone de propriété

- `apps/api/models/**` pour les extensions convenues ;
- nouveau package modèles Agent Control si retenu par SP1 ;
- `infra/migrations/versions/**` ;
- portions Agent Control du seed ;
- tests modèles/migrations/contraintes.

Les changements de `models/__init__.py` sont préparés pour l'orchestrateur si celui-ci garde le fichier partagé.

## Travaux

1. Cartographie données historiques, seeds fichiers et DB avant migration.
2. Ajoute installations et mappings utilisateurs.
3. Étends Project, Agent et Task de manière additive et compatible.
4. Ajoute credentials agents avec hash, prefix, scopes, expiration et révocation.
5. Ajoute affectations agent-projet.
6. Ajoute runs, étapes et événements append-only.
7. Ajoute commandes, approbations et politiques.
8. Ajoute usage, budgets, alertes, audit et outbox.
9. Pose FK, uniques, checks, index tenant/date/statut et index de pagination.
10. Évite les cascades destructives sur historique, audit, coûts et décisions.
11. Maintiens `agent_key` global et namespacé pour compatibilité A/D.
12. Écris migrations petites, ordonnées et réversibles en développement.
13. Backfill les lignes V0 dans une installation locale/démo sans inventer un tenant production.
14. Transforme le seed de démonstration en données DB idempotentes, activables par configuration.
15. Documente les volumes, rétention et stratégie d'archivage.

## Invariants

- argent en `Numeric/Decimal`, jamais float ;
- UTC timezone-aware ;
- événements/audit append-only ;
- secret brut jamais persisté ;
- une décision d'approbation terminale ;
- un `(run_id, sequence)` unique ;
- idempotency key unique dans la portée tenant ;
- nouvelles lignes V1 toujours rattachées à une installation/tenant.

## Tests attendus

- upgrade depuis la dernière migration existante ;
- création du schéma vide ;
- contraintes uniques/check/FK ;
- backfill données historiques ;
- seed relancé deux fois ;
- deux tenants avec mêmes clés locales sans collision fonctionnelle ;
- refus doublon événement, commande idempotente et double décision ;
- downgrade de développement documenté et testé si sûr.

## Handoff

Fournis diagramme final, liste tables/index, ordre des migrations, procédure backfill, impacts volumétrie et imports à ajouter aux fichiers partagés.

## Terminé quand

Toutes les entités V1 sont persistables avec contraintes garantissant tenant, idempotence, historique et compatibilité V0.
