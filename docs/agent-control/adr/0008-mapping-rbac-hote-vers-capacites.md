# ADR-0008 — Mapping RBAC hôte → capacités du module (adaptateur local)

Statut : accepté (SP1, Gate P0)
Date : 2026-07-15

## Contexte

Le domaine V1 autorise par **capacités** (`view, operate, manage_agents,
manage_projects, approve, view_costs, admin`), pas par rôle hôte. L'adaptateur
local doit traduire le RBAC existant (`viewer < developer < pm < cto < admin`,
`apps/api/core/roles.py`) en capacités, une seule fois, de façon déterministe.

## Décision

Mapping unique dans `apps/api/integrations/capabilities.py::ROLE_CAPABILITIES` :

| Rôle | Capacités |
|---|---|
| viewer | view |
| developer | view, operate |
| pm | view, operate, manage_projects, approve, view_costs |
| cto | view, operate, manage_projects, manage_agents, approve, view_costs |
| admin | toutes |

Principes :

- **monotone** avec la hiérarchie existante : `caps(role_n) ⊆ caps(role_{n+1})` ;
- préserve la sémantique actuelle `WRITE_ROLES = {pm, cto, admin}` (frontend
  `lib/api.ts`) pour `manage_projects` ;
- `manage_agents` (registre, credentials, révocation) réservé à **cto+** — plus
  sensible que le CRUD projet ;
- `admin` (politiques, installations, intégrations) réservé à `admin` ;
- rôle inconnu/absent → **aucune** capacité (fail-closed).

Ce mapping est le **défaut de l'adaptateur `local`**. Un adaptateur `jwt` d'un
hôte réel fournit son propre mapping via `HostPermissionPort.capabilities_for`
sans toucher au domaine.

## Conséquences

- La matrice `ROUTE_CAPABILITIES` + ce mapping déterminent l'autorisation
  effective, vérifiée par `test_agent_control_permissions.py`.
- Changer une frontière de capacité = éditer une seule table + son test.

## Alternatives rejetées

- Comparer les rôles hôte directement dans les services (`require_role`) : couple
  le domaine au RBAC hôte, empêche un adaptateur `jwt` de mapper différemment.
  Rejeté au profit des capacités.
- Donner `manage_agents` à `pm` : le registre/credentials est plus sensible que
  le CRUD projet ; réservé à cto+. Décision révisable (mapping isolé).
