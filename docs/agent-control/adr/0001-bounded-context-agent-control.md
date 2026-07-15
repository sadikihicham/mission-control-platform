# ADR-0001 — Agent Control est un bounded context, pas une seconde plateforme

Statut : accepté (SP1, Gate P0)
Date : 2026-07-15

## Contexte

Le cockpit actuel est une application autonome (auth locale, RBAC, shell,
dashboard). L'objectif V1 est de l'intégrer dans une plateforme métier hôte qui
possède déjà identité, tenant, rôles globaux, navigation et design system.

## Décision

Agent Control devient un **bounded context** intégrable. Il n'implémente ni
authentification, ni gestion des organisations, ni shell propres en mode
embarqué. Il consomme la plateforme hôte via **cinq ports** (`HostIdentityPort`,
`HostTenantPort`, `HostPermissionPort`, `HostNavigationPort`,
`HostNotificationPort`, `apps/api/integrations/ports.py`). Le domaine ne dépend
jamais des tables de l'hôte. La sélection d'adaptateur (`local` en dev, `jwt` en
prod) se fait par **configuration** (`MC_HOST_ADAPTER`), pas par des `if embedded`
dispersés dans les services.

L'API V1 est montée sous `/agent-control/v1`, le frontend sous `/agent-control`.

## Conséquences

- Un adaptateur local (`LocalHostAdapter`) réutilise `User`/JWT/RBAC existants et
  expose un tenant unique `local` — le mode autonome reste fonctionnel.
- Les services reçoivent un `HostContext` explicite ; ils ne lisent jamais le JWT
  ni le RBAC hôte directement.
- Le module garde uniquement des **références externes** (`external_user_id`,
  `external_tenant_id`) et ses **capacités** propres, pas la hiérarchie hôte.

## Alternatives rejetées

- Fork « seconde plateforme » avec sa propre auth : duplication d'identité,
  divergence des rôles, double login. Rejeté.
- Branches `if embedded` dans chaque service : couplage fort, non testable,
  fuite de la préoccupation d'intégration dans le domaine. Rejeté.
