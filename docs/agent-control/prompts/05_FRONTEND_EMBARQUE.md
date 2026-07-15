# SP5 — Frontend Agent Control embarqué

## Rôle

Tu es propriétaire du module web `/agent-control`. Tu transformes les vues existantes en interface intégrable, entièrement alimentée par API et compatible avec le shell/design system de la plateforme hôte.

## Dépendances

Code contre les DTO et permissions figés par SP1. Utilise les routes stabilisées de SP3/SP4. Des mocks de test sont permis ; aucun mock runtime n'est permis.

## Zone de propriété

- `apps/web/app/agent-control/**` ;
- `apps/web/components/agent-control/**` ;
- `apps/web/lib/agent-control/**` ;
- tests frontend/E2E du module ;
- migration progressive des composants `components/mc` convenue avec l'orchestrateur.

Ne surcharge pas le grand `app/page.tsx` avec le nouveau module.

## Travaux

1. Crée `AgentControlProvider` recevant contexte, permissions, locale, design tokens et callbacks navigation.
2. Implémente adaptateur local de développement utilisant auth et i18n existantes.
3. Crée un client HTTP unique avec erreurs typées, pagination, abort et contexte installation.
4. Consomme les types générés OpenAPI ; supprime les copies manuelles à mesure.
5. Utilise React Query pour cache/mutations/invalidation et WS pour invalidation ciblée.
6. Remplace tous les compteurs `mc-data.ts` par données API.
7. Supprime `@ts-nocheck` des composants migrés.
8. Implémente routes dashboard, agents, projets, runs, approbations, alertes, coûts, audit et settings.
9. Dashboard : santé, runs, validations et budget réels.
10. Agent : métadonnées, capacités, santé, affectations, credentials et activité.
11. Projet : tâches persistées, agents, runs, Git et risques.
12. Run : timeline virtualisable/paginée, coûts, commandes autorisées.
13. Approbation : contexte, impact, expiration, approve/reject avec confirmation.
14. Chaque écran gère loading, empty, erreur, retry, 401, 403, 404 et offline/polling.
15. En mode embedded, ne duplique ni topbar, sidebar, profil, langue ni logout.
16. Préserve `fr/en/ar`, RTL, clavier, focus, responsive et contrastes.

## Invariants

- aucune permission uniquement côté client ;
- aucun secret credential conservé après l'écran de création ;
- pas de HTML/log brut non assaini ;
- pas de polling multiple concurrent pour la même ressource ;
- aucun import runtime de `mc-data.ts` dans le module ;
- le shell local n'apparaît qu'en mode standalone.

## Tests attendus

- client API, permissions d'affichage et erreurs ;
- composants critiques agents/run/approbation ;
- reconnexion WS et fallback polling ;
- E2E observateur, opérateur, approbateur et admin ;
- tenant switch nettoie cache et subscriptions ;
- aucune donnée ancienne après changement de tenant ;
- mobile, clavier, FR/EN/AR et RTL ;
- lint, typecheck et build sans `@ts-nocheck` module.

## Handoff

Fournis routes, composants réutilisés/remplacés, clés i18n, besoins package/config, couverture E2E et procédure d'intégration dans le shell hôte.

## Terminé quand

Le host peut monter Agent Control sous une route et lui fournir son contexte sans afficher de mock, dupliquer le shell ou exposer une action non autorisée.

