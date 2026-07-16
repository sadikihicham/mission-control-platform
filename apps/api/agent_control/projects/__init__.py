"""Projets & tâches V1 (P8) — routes HTTP tenant-scoped au-dessus du Contract A+.

Ce lot ferme le gap assumé au Gate P7 : les tables V0 `projects`/`tasks`
n'avaient pas de colonne tenant, ce qui interdisait de les exposer sous
`/agent-control/v1` sans risque de fuite cross-tenant. La migration 0016 ajoute
`installation_id` (nullable, backfill local) ; ces modules exposent, tenant-scoped
et fail-closed, les routes projets/tâches déjà déclarées dans la matrice figée
`ROUTE_CAPABILITIES` (lecture `view`, mutation `manage_projects`).

Aucune nouvelle capacité n'est inventée. Cross-tenant = 404 (jamais 403, ADR-0003).
"""
