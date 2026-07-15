# packages/contracts

Types TypeScript **générés** depuis l'OpenAPI réel de l'API (Contrats C/D/E).

## Contenu

- `openapi.json` — snapshot du schéma OpenAPI servi par FastAPI (source) ;
- `types.ts` — types TS canoniques du monorepo, dérivés de `openapi.json` ;
- `generate.py` — générateur déterministe et hors-ligne.

Le frontend consomme une copie in-tree `apps/web/lib/contracts.ts` (Next ne
transpile de façon fiable que les fichiers sous `apps/web`), produite par le même
générateur. `apps/web/lib/api.ts` ré-exporte ces types : plus aucune définition
de DTO dupliquée à la main côté web.

## Régénération

```bash
make contracts           # via le conteneur api (a accès à l'app FastAPI)
# ou directement :
docker compose -f infra/docker-compose.yml exec -T ag-api \
    python -m packages.contracts.generate
```

Les trois fichiers de sortie sont committés et **ne doivent pas être édités à la
main** : toute évolution passe par les schémas Pydantic puis une régénération.

## Règle d'optionalité

Ces DTO sont des **réponses** : Pydantic sérialise toujours chaque champ (défauts
et `null` inclus), donc toutes les propriétés sont émises comme présentes ; un
champ nullable devient `T | null`. Cela reproduit exactement les formes gelées
côté frontend (aucune propriété optionnelle surprise sous `strict`).
