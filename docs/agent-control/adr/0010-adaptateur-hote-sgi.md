# ADR-0010 — Adaptateur hôte SGI (`JwtHostAdapter`)

Statut : **accepté et implémenté** (P1 — `MC_HOST_ADAPTER=jwt`, tests verts, ruff clean ;
2026-07-18). Reste hors de ce repo : le travail côté SGI (§1) et la vraie vérification de
`subscription` (§3, voir écart assumé en Conséquences).
Date : 2026-07-18

## Contexte

Objectif déclaré : intégrer Agent Control comme sous-catégorie de SGI (`Infinity_Sass_AI`), le SaaS
immobilier multi-tenant. L'archi V1 a été conçue précisément pour ce cas (ADR-0001, 0003, 0008) :
le domaine ne connaît que 5 `Protocol` (`apps/api/integrations/ports.py`) et un seul adaptateur
concret existe aujourd'hui, `DbHostAdapter` (mode `local`/standalone). Écrire un second adaptateur,
`JwtHostAdapter`, est le seul travail de code requis côté domaine — confirmé par cartographie
(`.cartographer/report.md`, 2026-07-18).

Cette ADR fige ce qui est **vérifié dans le code de SGI** (pas supposé) pour que l'implémentation
parte d'une interface réelle. Sources : exploration de code de `Infinity_Sass_AI`
(`apps/api/app/core/auth/service.py`, `apps/api/app/core/tenant/middleware.py`,
`apps/api/app/config.py`, `apps/api/migrations/versions/0067_baseline_consolidated.py`,
`0068_action_registry.py`, `apps/web/components/Nav.tsx`).

## Décision

### 1. Identité (`HostIdentityPort`)
SGI émet un JWT HS256 (`PyJWT` côté SGI, TTL 15 min) signé avec `settings.jwt_secret`/`JWT_SECRET`.
Claims utiles : `sub` (user_id), `company_id`, `role`, `permissions` (liste, parfois `["*"]`),
`actor_type`. **Pas de JWKS ni de package partagé à réutiliser** (vérifié : absent côté SGI) — donc
un secret d'environnement partagé (`SGI_JWT_SECRET`), pas de dépendance croisée entre les deux
repos. `JwtHostAdapter.resolve_identity` (`apps/api/integrations/jwt_adapter.py`) décode ce même
JWT — **implémenté avec `jose` (déjà une dépendance de ce repo pour le JWT V0)**, pas `PyJWT` : un
JWT HS256 est un format standard, la bibliothèque qui le décode n'a pas besoin d'être celle qui l'a
signé, donc pas de nouvelle dépendance runtime nécessaire (correction par rapport à l'intention
initiale de cette ADR).

**Décision (2026-07-18)** : le JWT SGI ne porte ni email ni nom affiché (confirmé absent) — SGI
ajoutera un endpoint `/me` léger et self-service (pas de requête DB scoped bricolée côté Agent
Control, pas de `GET /iam/users/{id}` admin-only détourné). `JwtHostAdapter.resolve_identity`
appellera cet endpoint pour compléter `UserRef.email`/`display_name`. Travail côté SGI, hors scope
du code `mission_control_plateforme` — à cadrer séparément avec l'équipe/session SGI.

### 2. Tenant (`HostTenantPort`)
`company_id` (UUID) est **dans le JWT**, jamais résolu autrement côté SGI — cohérent avec l'ADR-0003
existante (tenant jamais accepté du client). `JwtHostAdapter.resolve_tenant` mappera directement
`company_id` (SGI) → `InstallationRef.external_tenant_id` (Agent Control). Pas de résolution DB
supplémentaire nécessaire pour le tenant lui-même — seule `mc_installations` doit gagner une ligne
par `company_id` SGI actif (bootstrap/onboarding, hors scope de cette ADR).

### 3. Permissions (`HostPermissionPort`)
SGI n'a **pas** d'enum de rôles fixe ni de capacités — rôles de base (`manager`/`admin`/`agent` +
personas portal) **plus** un système de permissions granulaires par chaîne (`"module.action"`,
table `role_permission`, T3 RBAC, migration `0215_rbac_fin_grants.py`), unionnées dans le claim JWT
`permissions`. **Décision (2026-07-18)** : `capabilities_for()` (équivalent SGI de
`ROLE_CAPABILITIES`) traduit d'abord le **rôle de base** SGI (`manager`/`admin`/`agent`) vers un
`ROLE_CAPABILITIES`-like fixe, comme le fait déjà l'adaptateur `local` — pas de nouvelle clé de
permission à ajouter côté SGI pour cette première version. Chemin d'évolution : le mapping fin par
clé dédiée (`"agent_control.*"` dans le registre `@action`) reste possible plus tard sans toucher
au domaine, en ne réimplémentant que `capabilities_for()`.

Activation par tenant — **décision (2026-07-18)** : Agent Control n'est **pas** ouvert à tous les
clients SGI par défaut.

**Écart assumé à l'implémentation** : plutôt qu'un appel réseau live vers la table
`activity`/`subscription` de SGI (`0068_action_registry.py`) — dont je n'ai vérifié que la
lecture possible (`GET /api/v1/tenant/subscriptions/{id}`), pas la forme exacte de la réponse ni
un contrat stable à coder dessus sans risque — l'activation par tenant est appliquée via le champ
`status` de `mc_installations`, déjà réel et déjà fail-closed dans `resolve_tenant`
(`jwt_adapter.py`) : un tenant sans ligne `mc_installations` **active** pour son `company_id`
lève `TenantUnresolved`, quel que soit le JWT. Le pont exact "l'admin SGI active la subscription
→ la ligne `mc_installations` passe/est créée à `active`" (onboarding/webhook) reste à câbler
séparément — hors scope de cette ADR, mais c'est le point d'intégration concret à cadrer avec SGI
pour rendre la décision "activable au cas par cas" réellement automatique plutôt que manuelle.

### 4. Navigation (`HostNavigationPort`)
Aucun registre de modules côté SGI — `apps/web/components/Nav.tsx` est un tableau statique
(`HOLDING_ITEMS`). Il existe déjà un précédent pour une entrée « pas encore livrée »
(`comingSoon`, item `firewall`, `Nav.tsx:132`) — c'est le point d'insertion le plus proche : ajouter
une entrée Agent Control à ce tableau (édition manuelle, pas d'API `register_module` à appeler côté
SGI puisqu'il n'en existe pas). `HostNavigationPort.register_module`/`open_route` resteront donc des
no-ops côté SGI pour l'instant, ou seront implémentés a minima (juste `open_route` → `router.push`).

## Conséquences

- **Durcissement post-revue adverse (2026-07-18)** : un `code-reviewer` indépendant a relevé que
  `jwt.decode` n'exigeait pas la présence du claim `exp`, contredisant le TTL 15 min annoncé plus
  haut (un jeton sans `exp` n'expirait jamais) ; corrigé via `options={"require_exp": True}`, plus
  deux tests de régression (`test_token_without_exp_is_rejected`, `test_expired_token_is_rejected`).
  Le même agent a aussi relevé qu'un claim `role` non-string (liste/objet) ferait planter la
  résolution en 500 plutôt que de tomber sur l'ensemble de capacités vide attendu ; corrigé par une
  garde `isinstance(role, str)` avant le mapping. Suite complète re-vérifiée après coup : 286 tests
  verts, ruff clean.
- Zéro nouvelle dépendance runtime — `jose` (déjà utilisé pour le JWT V0) décode aussi le JWT SGI ;
  un secret d'environnement partagé (`SGI_JWT_SECRET`/`SGI_JWT_ALGORITHM`, nouveaux champs
  `apps/api/core/config.py`) entre les deux déploiements — à gérer comme un secret partagé
  inter-projets, jamais dupliqué en clair dans les deux repos.
- `MC_HOST_ADAPTER=jwt` active ce nouvel adaptateur ; `local` reste le défaut — **aucune
  régression sur le mode actuel** (284 tests existants toujours verts + 9 nouveaux, ruff clean).
- Le domaine Agent Control (`agent_control/`) ne change pas : tout le travail neuf est dans
  `integrations/jwt_adapter.py` (nouveau, miroir de `db_adapter.py`) + config. Deux points d'entrée
  existants ont dû être rendus adaptateur-agnostiques (pas juste le nouveau fichier) : la dépendance
  FastAPI `get_host_context` (`core/agent_control_deps.py`) ne dépendait en dur que du JWT/`User` V0
  — elle résout maintenant le credential différemment selon `MC_HOST_ADAPTER` (jeton brut en mode
  `jwt`, `get_current_user` inchangé en mode `local`) ; et la résolution du contexte WS
  (`agent_control/realtime._resolve_ws_context`) avait la même dépendance en dur, corrigée pareil.
- Travail à cadrer côté **SGI**, hors de ce repo : l'endpoint `/me` (§1), et rendre l'activation
  `mc_installations.status` réellement pilotée par la `subscription` SGI plutôt que manuelle (§3).
- Mapping de capacités grossier assumé pour cette V1 (§3) — accepter un couplage plus lâche à la
  granularité fine de SGI en échange d'un premier livrable plus rapide.

## Alternatives rejetées

- **Lien/iframe séparé** (déploiement indépendant, pas de SSO) : rejeté — ne satisfait pas l'objectif
  « sous-catégorie » avec identité unifiée, et SGI n'a de toute façon aucun pattern d'iframe-host
  existant à réutiliser (vérifié absent).
- **Fusion complète en monorepo** (copier `agent_control/` dans SGI) : rejeté pour l'instant — plus
  coûteux que (2) pour le même résultat fonctionnel, et duplique un domaine déjà proprement isolé
  par ports ; à reconsidérer seulement si SGI veut posséder le code, pas juste le consommer.
- **JWKS/rotation de clés asymétrique** : non retenu à ce stade — SGI utilise HS256 symétrique
  partout (pas d'infra JWKS existante à brancher) ; un secret partagé HS256 est le chemin de moindre
  résistance cohérent avec l'existant, au prix d'un couplage plus fort sur la rotation de secret.
