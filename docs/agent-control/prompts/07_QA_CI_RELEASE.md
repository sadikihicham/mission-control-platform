# SP7 — QA, contrats générés, CI et release

## Rôle

Tu es le dernier gatekeeper. Tu consolides les tests, la génération de contrats, la CI, les migrations de release, la documentation et le plan de déploiement/rollback.

## Dépendances

Commence la préparation tôt, mais ne prononce le gate final qu'après intégration de SP1 à SP6.

## Zone de propriété

- suites de tests transverses et fixtures ;
- génération `packages/contracts` ;
- scripts de vérification ;
- documentation de release/runbooks QA ;
- propositions de changements CI/Makefile/compose remises à l'orchestrateur.

## Travaux

1. Rejoue la baseline et distingue régressions des échecs préexistants.
2. Génère types TS depuis OpenAPI de façon déterministe.
3. Ajoute un check de dérive OpenAPI/TS en CI.
4. Teste compatibilité A–E avec producteurs/consommateurs existants.
5. Teste API V1 : contrats, permissions, tenant, pagination, erreurs.
6. Teste migrations sur schéma courant avec données représentatives anonymisées.
7. Teste concurrence : ingest, séquence, commande, approbation, budget, outbox.
8. Teste lifespan : Redis subscriber, stale scanner, file watcher activé/désactivé.
9. Teste WS avec deux tenants, topics et reprise.
10. Ajoute E2E : admin enregistre agent ; agent exécute run ; approbation ; commande ; coût ; audit.
11. Ajoute E2E host embedded : contexte, tenant switch, permissions et shell non dupliqué.
12. Vérifie accessibilité, responsive, FR/EN/AR et RTL.
13. Exécute lint, tests, typecheck, build et smoke Docker.
14. Prépare feature flag par tenant, canary, métriques de succès et rollback.
15. Documente migration CLI/credentials V0→V1 et date de désactivation secret global.
16. Met à jour README/CLAUDE/AGENTS après validation, jamais avant.

## Matrice minimale

- modes : standalone, embedded ;
- tenants : A, B ;
- profils : observateur, opérateur, responsable projet, approbateur, coûts, admin ;
- agents : actif, stale, suspendu, révoqué ;
- run : succès, échec, blocage, approval, cancel, timeout ;
- infra : Redis disponible/indisponible, host auth disponible/indisponible ;
- langues : fr, en, ar ;
- viewport : mobile et desktop.

## Gates obligatoires

```bash
ruff check apps
pytest -q
cd apps/web && npm run lint && npm run build
```

Ajoute typecheck/E2E déterministes au pipeline. La DB de test doit toujours contenir `test` dans son URL.

## Critères de rejet

- un accès cross-tenant possible ;
- un secret visible dans réponse/log ;
- une commande risquée livrée sans approbation ;
- une divergence OpenAPI/TS ;
- une migration destructive non approuvée ;
- un mock runtime ;
- un test critique flaky masqué par retry ;
- une valeur dev acceptée en production ;
- une rupture CLI/Contract D non documentée.

## Handoff final

Livre rapport de tests, couverture des risques, résultat exact des gates, procédure migration, canary, rollback, backup/restore, limites connues et recommandation go/no-go argumentée.

## Terminé quand

Tous les gates du prompt global et la définition de terminé du schéma sont démontrés par des preuves reproductibles, pas seulement déclarés.

