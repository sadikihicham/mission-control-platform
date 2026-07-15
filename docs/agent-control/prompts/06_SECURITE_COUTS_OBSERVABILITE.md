# SP6 — Sécurité, coûts, audit et observabilité

## Rôle

Tu renforces le module pour la production et implémentes usage, budgets, alertes, audit, outbox opérationnelle, logs et métriques.

## Dépendances

Travaille sur les contrats et modèles stabilisés. Ne remplace pas les services SP3/SP4 : ajoute des ports/services transverses et propose les points d'appel transactionnels.

## Zone de propriété

- services Agent Control `usage`, `budgets`, `alerts`, `audit`, `outbox`, `redaction` ;
- middleware/guards dédiés du module ;
- métriques et runbooks Agent Control ;
- tests sécurité/usage/observabilité.

Les changements core/config/compose sont remis à l'orchestrateur.

## Travaux

1. Réalise un threat model : host JWT, credential agent, ingest, WS, commandes, approbations, exports et logs.
2. Ajoute validation issuer/audience/JWKS via port hôte et fail-closed.
3. Ajoute rate limits tenant/agent/IP adaptés aux endpoints.
4. Centralise redaction des secrets, prompts, outputs, PII et réponses outils.
5. Implémente usage idempotent : tokens, appels, durée, modèle, provider, prix versionné.
6. Calcule coûts en Decimal et conserve source/pricing_version.
7. Implémente budgets tenant/projet/agent et seuils configurables.
8. Évalue dépassements transactionnellement et déclenche alert/approval/block selon politique.
9. Implémente alertes persistées, déduplication, ACK et résolution.
10. Implémente audit append-only sur credentials, commandes, décisions, policies, exports et budgets.
11. Finalise outbox : retries, backoff, dead letter, métriques et replay opérateur.
12. Ajoute request_id/trace_id propagés HTTP→DB→Redis→WS.
13. Ajoute logs structurés tenant-aware sans PII inutile.
14. Ajoute métriques techniques et métier avec cardinalité bornée.
15. Rédige rétention, purge, incident credential, panne Redis, backlog outbox et surcoût.
16. Vérifie CORS/CSP/headers et interdiction des valeurs de dev en production.

## Invariants

- jamais de secret ou prompt brut dans logs/audit/métriques ;
- aucun label métrique avec user_id/agent_id libre ;
- coût reproductible depuis usage + pricing_version ;
- alertes dédupliquées ;
- audit non modifiable par API métier ;
- rate limiting ne mélange pas les tenants ;
- outbox rejouable sans double notification.

## Tests attendus

- JWT mauvais issuer/audience/clé ;
- credential brute force/révocation ;
- rate limits et isolation ;
- redaction avec payloads piégés ;
- calcul Decimal et tarif versionné ;
- doublon usage ;
- budgets 50/80/100 et concurrence ;
- alerte dédupliquée/ACK/résolution ;
- outbox retry/dead letter/replay ;
- logs sans secrets via assertions de capture.

## Handoff

Fournis threat model, métriques/alertes, variables de prod, dashboards opératoires, runbooks et points d'intégration dans les transactions SP3/SP4.

## Terminé quand

Le module est exploitable et auditable en production, avec coûts fiables et absence démontrée de fuite de secret ou de tenant.

