# ADR-0003 — Le tenant est propriété de l'hôte, résolu serveur

Statut : accepté (SP1, Gate P0)
Date : 2026-07-15

## Contexte

Le MVP a abandonné le multi-tenant (`company_id` retirée en migration 0007). V1
doit isoler données et événements par tenant sans réintroduire un faux signal
d'isolation. L'analyse (`01_ANALYSE_EXISTANT.md` §4.3) alerte : ne pas activer le
multi-tenant avant un contexte hôte et des tests négatifs systématiques.

## Décision

Le tenant est **résolu côté serveur** par `HostTenantPort` à partir du
credential/JWT hôte et de `installation_id` — **jamais** accepté depuis un query
ou un body. Il est porté par `HostContext.installation.external_tenant_id` et
propagé à chaque service, qui filtre **toutes** ses requêtes (HTTP, WS, cache,
export) par `installation_id`.

Fail-closed : contexte tenant absent → `tenant_required` (403) ; ressource d'un
autre tenant → `not_found` (404, pas 403, pour ne pas divulguer l'existence).

## Conséquences

- L'isolation V1 passe par `installation_id`, pas par l'ancienne `company_id`.
  Les nouvelles données portent `installation_id` (obligatoire applicativement,
  colonne nullable en base pour compat V0 — voir ADR-0007).
- Le WS n'accepte une souscription qu'après validation identité + tenant +
  capacité, et vérifie chaque topic.
- Les tests cross-tenant négatifs (deux tenants, aucune fuite) sont un gate P1.

## Alternatives rejetées

- Tenant depuis un header/body « pratique » : trivialement usurpable. Rejeté.
- Réactiver `company_id` sans filtre actif : faux signal d'isolation (finding
  cartographer). Rejeté — colonne + filtre reviennent ensemble.
