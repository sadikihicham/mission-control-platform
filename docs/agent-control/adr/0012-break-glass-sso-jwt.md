# ADR-0012 — Break-glass local sous `MC_HOST_ADAPTER=jwt` (anti-verrouillage)

Statut : **proposé** (design seul, aucun code). Bloqué par le déploiement du code du lien
(§ Contexte) — rien n'est actionnable tant qu'`ag.infinityauh.com` sert une image antérieure à
ADR-0010/0011.
Date : 2026-07-23

## Contexte

ADR-0010 a fixé `JwtHostAdapter` comme second adaptateur hôte (SGI). `_build_adapter`
(`apps/api/core/agent_control_deps.py:37-47`) sélectionne l'adaptateur par la configuration
**globale** `MC_HOST_ADAPTER` : `jwt` **ou** `local`, jamais les deux à la fois. En mode `jwt`,
`_resolve_credential` (`agent_control_deps.py:50-64`) prend le Bearer hôte brut et **ne passe
jamais** par `get_current_user` (le chemin des comptes V0 de ce service) — confirmé au code, pas
supposé.

Ce commutateur exclusif croise un piège déjà vécu côté SGI : la règle anti-lockout de
`core/tenant/CLAUDE.md` (SGI, migration `0197`) documente l'incident #237 — gater une surface sur
un critère (`role=='admin'`) sans laisser de **chemin de provisioning** vers ce critère a verrouillé
l'admin réel de prod hors de son propre produit.

Le même risque existe ici, structurellement plus grave qu'un rôle manquant :
1. `MC_HOST_ADAPTER=jwt` **coupe le login local** — confirmé au code (§ ci-dessus).
2. Le mode `jwt` **exige** une ligne `mc_installations` active pour le `company_id` du JWT
   (`jwt_adapter.py:97-99`, `TenantUnresolved` sinon). Cette ligne **n'est jamais auto-créée**
   (constaté par le bulletin de la session « Agent Control », 2026-07-22 — grep zéro sur toute
   création automatique).
3. Une divergence du secret webhook (`SGI_WEBHOOK_SECRET`) échoue **silencieusement en 401**
   (même source).

⇒ Si la voie de provisioning de `mc_installations` était elle-même **derrière** le SSO SGI, un
SSO cassé (secret désynchronisé, panne SGI, `mc_installations` jamais posée) enfermerait
**tout le monde** dehors — y compris pour réparer. C'est le chicken-and-egg exact de #237, appliqué
à un chemin d'authentification entier plutôt qu'à un rôle.

**Ceci n'est PAS un audit de sécurité du code de `mission-control-platform`** — je n'ai pas lu ce
dépôt au-delà des fichiers cités, et je ne travaille sur aucun de ses fichiers de code. C'est une
proposition de design, à charge de la session/équipe propriétaire de l'implémenter ou de la
rejeter.

## Décision proposée

**Ne pas activer `MC_HOST_ADAPTER=jwt` en exclusivité totale.** Garder un recours local, **étroit**,
qui survit au mode `jwt` — un break-glass, pas un second mode de production permanent.

### Options considérées

| # | Approche | Coût | Verrou résiduel |
|---|---|---|---|
| 1 | Exclusivité assumée (statu quo du code) | ~0 j | 🔴 lockout total si SSO/ligne cassé |
| 2 | `CompositeAdapter` dual complet (JWT SGI **et** login V0 coexistent pour tous, en permanence) | ~2-4 j | 🟠 surface d'auth doublée en continu |
| **3** | **Break-glass minimal** (JWT SGI par défaut + une échappatoire admin locale, étroite) | ~1-2 j | 🟢 recours borné, audité distinctement |

**Option 3 retenue.** L'option 1 rejoue #237. L'option 2 maintient une surface d'authentification
double en permanence pour un besoin qui n'est qu'un recours d'urgence — coût disproportionné.

### Forme du break-glass (Option 3)

Faisabilité de conception : `JwtHostAdapter` et `DbHostAdapter` implémentent déjà les mêmes trois
ports (`HostIdentityPort`/`HostTenantPort`/`HostPermissionPort`, ADR-0010 §1-3) — un composite n'est
pas une réécriture. Forme proposée dans `_resolve_credential` :
- **Chemin normal** (route/en-tête standard) : mode `jwt`, inchangé.
- **Chemin réservé** (ex. un en-tête ou une route distincte, jamais la même surface que le SSO) :
  retombe sur `get_current_user` (V0), pour un **compte break-glass** seul — pas tout le barème V0.

Le compte break-glass doit pouvoir, au minimum, **créer/réparer** la ligne `mc_installations`
manquante — c'est le seul geste qui compte réellement en incident.

## Conséquences

- **Audit distinct obligatoire** : le journal append-only doit porter la **source d'identité**
  (`actor_source="break-glass"` ou équivalent), jamais confondue avec une identité SGI — sinon
  l'audit devient ambigu sur qui a agi pendant l'incident, ce qui défait tout l'intérêt du break-glass.
- **Le break-glass est une clé maîtresse** : secret long, rotation, **alerte à chaque usage**. Une
  porte de secours non surveillée est une porte dérobée, pas un contrôle.
- **Revue sécurité adverse obligatoire avant tout code** — ceci touche un chemin d'authentification.
  Points à faire trancher par la revue, pas par ce document : confusion possible entre les deux
  secrets JWT (SGI vs V0) si un jeton de l'un était accepté par erreur côté de l'autre ; parité de
  capacités entre le barème `_SGI_ROLE_TO_MC_ROLE` (ADR-0010 §3) et le barème V0 — le break-glass ne
  doit pas hériter d'un accès plus large que nécessaire.
- **Séquencement** : inerte tant que le code du lien n'est pas déployé sur `ag.` (mesuré 404 sur
  `/agent-control/v1/context` au 2026-07-22 22h58 — cf. bulletin SGI, hors de ce repo). Une fois
  déployé, l'ordre naturel est : déploiement → (fermeture de l'audit borgne, ADR-0010 §1, en
  parallèle) → ce break-glass → activation de `MC_HOST_ADAPTER=jwt` → création de la première
  ligne `mc_installations` **via le break-glass lui-même** (dogfooding du recours dès le premier jour).

## Alternatives rejetées

- **God-mode / bypass de l'isolation tenant côté break-glass** : rejeté par principe — même
  doctrine que SGI sur son propre opérateur cross-tenant (« Option D agrégats 0-PII ; god mode
  BYPASSRLS REJETÉ »). Le recours répare une installation, il ne contourne pas l'isolation.
- **Break-glass hors-application pur** (SSH + script SQL direct sur `mc_installations`) : c'est
  l'option 1 déguisée — non auditée par le journal applicatif, et suppose un accès infra qui n'est
  pas garanti disponible au moment précis d'un incident d'authentification.
- **Dual complet permanent (option 2)** : rejeté pour cette V1 — coût de surface d'auth doublée en
  continu pour un besoin qui est un recours d'urgence, pas un mode d'usage courant.

---
*Rédigé par une session travaillant sur `Infinity_Sass_AI` (SGI), à la demande explicite de
l'USER (propriétaire des deux dépôts) qui souhaitait une proposition de design pour cette
décision. Aucun fichier de code de ce dépôt n'a été modifié. Périmètre : lecture des fichiers
cités ci-dessus + `apps/api/integrations/jwt_adapter.py`, `apps/api/integrations/db_adapter.py`.*
