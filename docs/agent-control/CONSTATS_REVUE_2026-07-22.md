# Constats de revue — 2026-07-22

Revue de **lecture** du module Agent Control, menée depuis le dépôt hôte `Infinity_Sass_AI` (SGI)
dans le cadre de l'intégration ADR-0010/0011. Objectif initial : établir ce que la rubrique
« Agent Control » sait faire avant de décider de l'activer côté SGI. Elle n'a **pas** été activée.

Trois constats en sont sortis. Le premier est un **défaut bloquant sur du code déjà en production**
(`ag.infinityauh.com`) ; il est corrigé ici. Les deux autres sont documentés, **non corrigés** :
ils demandent un arbitrage, pas un correctif mécanique.

---

## 🔴 Constat 1 — Approuver / rejeter depuis l'UI était impossible (corrigé)

### Symptôme
Toute décision d'approbation prise depuis l'écran `/agent-control/approvals` repartait en
**`422 Unprocessable Entity`**. L'écran de gouvernance humaine du module — sa fonction la plus
sensible — était inopérant.

### Cause racine, vérifiée maillon par maillon

| Maillon | Preuve |
|---|---|
| Le serveur exige `version` | `apps/api/agent_control/control/schemas.py:175` — `version: int`, **sans valeur par défaut** |
| Les deux routes lisent ce schéma en corps | `apps/api/agent_control/control/routes.py:91` et `:102` — `body: ApprovalDecisionIn` |
| Le front ne l'envoyait jamais | `apps/web/lib/agent-control/hooks.ts` — `body: { comment: input.comment ?? null }` |
| Le composant non plus | `apps/web/components/agent-control/Approvals.tsx:47` — `mutate({ decision, comment })` |
| La valeur était pourtant disponible | `ApprovalOut.version` — `schemas.py:162`, exposée dans `apps/web/lib/contracts.ts` |

`version` est le **verrou optimiste** qui garantit l'invariant « jamais deux décisions sur la même
demande » (`UPDATE ... WHERE status='pending' AND version=:v`, `control/approvals.py:114`).

### Pourquoi c'est passé au travers — trois filets absents, pas un
1. **`RequestOptions.body` est typé `unknown`** (`apps/web/lib/agent-control/client.ts:75`) :
   TypeScript ne pouvait structurellement pas voir le champ manquant.
2. **Aucun test front n'existe** dans tout `apps/web` (recherche `*.test.*` : zéro résultat) —
   aucun test n'exerçait ce chemin.
3. **Pas de handler `RequestValidationError`** dans `apps/api/main.py` : le 422 de FastAPI ressort
   en erreur générique côté écran, sans nommer le champ fautif.

> Le back était pourtant correct **et testé** (`test_no_double_decision_http`,
> `test_no_double_decision_concurrent_db`). C'est l'illustration nette qu'un invariant serveur vert
> ne dit **rien** sur l'atteignabilité de la fonction par un utilisateur réel.

### Correctif appliqué
- `apps/web/lib/agent-control/hooks.ts` — `useApprovalDecision` exige désormais
  `version: number` dans son `input` et le place dans le corps.
- `apps/web/components/agent-control/Approvals.tsx` — passe `approval.version`.

Le champ étant **typé** dans la signature du hook (et non simplement ajouté à l'appel), l'oubli
redevient une **erreur de compilation** au lieu d'un échec silencieux à l'exécution. Seul appelant
du hook : `Approvals.tsx` (vérifié par recherche exhaustive).

### Vérification — par mutation, pas par vert silencieux
`npx tsc --noEmit` sort à **0** après correctif. Un vert ne prouvant rien tant qu'on n'a pas montré
que l'outil couvre réellement le fichier, deux mutations ont été jouées :

| Mutation | Résultat | Ce que ça prouve |
|---|---|---|
| `approval.version` → `approval.versionMUTANT` | `TS2339` — code 2 | `tsc` couvre bien ce fichier |
| **Retrait pur de `version`** (= le bug d'origine, mot pour mot) | `TS2345: Property 'version' is missing` — code 2 | **La forme exacte du bug est désormais une erreur de compilation.** Avant ce correctif, ce même code compilait sans broncher |

`npm run lint` : **code 0**, zéro occurrence dans `agent-control/` (les seuls avertissements restants
visent le cockpit V0 `components/mc/*`, préexistants et hors périmètre).

### ⚠️ Ce qui n'est PAS couvert
Le garde-fou est **statique** (typage), pas un test : il empêche la régression à la compilation,
mais **aucun test n'exerce le chemin approve/reject de bout en bout** — il n'existe pas de harnais
de test front dans ce dépôt. Un changement de contrat côté serveur (nouveau champ requis) ne serait
donc toujours pas détecté ici. Voir §4.

---

## 🟠 Constat 2 — Les credentials d'agent ne peuvent ni être listés, ni donc tournés/révoqués

`apps/api/agent_control/registry/routes.py` expose bien :
- `POST /agents/{id}/credentials` (émission, secret affiché une seule fois) — l.113
- `POST /agents/{id}/credentials/{cid}/rotate` — l.129
- `DELETE /agents/{id}/credentials/{cid}` — l.145

Mais **aucune route ne liste les credentials d'un agent**. Sans elle, un opérateur n'a aucun moyen
d'obtenir un `credential_id` : **rotate et revoke sont inatteignables en pratique**, en API comme en
UI. C'est un trou dans le cycle de vie d'un secret — précisément la partie qui compte en cas de
compromission.

Deux écarts adjacents dans le même fichier :
- Le statut `revoked` est valide (`registry/service.py:36`) mais **aucune route ne le pose** — seuls
  `suspend`/`resume`/`archive` existent.
- L'UI force `scopes: ["ingest"]` en dur (`AgentDetail.tsx:150`) : impossible d'émettre un
  credential `commands` depuis l'écran.

**Non corrigé** : ajouter une route est un choix de contrat d'API (forme de la réponse, faut-il
exposer les credentials révoqués, pagination) — pas un geste mécanique.

---

## 🟠 Constat 3 — Créer un budget bloquant est gardé par une capacité de *lecture*

`POST /budgets` et `PATCH /budgets/{id}` sont gardés par `Capability.view_costs`
(`apps/api/agent_control/operations/routes.py:156` et `:169`).

Or un budget porte le comportement `block_new_runs` (`operations/budgets.py`), qui **bloque les
commandes de toute la flotte** au dépassement. Une capacité nommée « voir les coûts » autorise donc
un acte de gouvernance à effet de coupure.

Conséquence concrète pour l'hôte SGI, via `_SGI_ROLE_TO_MC_ROLE`
(`apps/api/integrations/jwt_adapter.py:36`) : `manager` SGI → rôle `pm` → porte `view_costs` →
**peut poser un budget qui bloque la flotte**, sans être admin.

**Non corrigé** : c'est un arbitrage (faut-il un `manage_budgets` distinct ? ou gater l'écriture sur
`admin` ?), pas un bug d'implémentation.

---

## 4. Angles morts structurels (à arbitrer, non traités)

| Sujet | Constat | Pourquoi ça n'a pas été fait ici |
|---|---|---|
| **Zéro test front** | Aucun `*.test.*` dans `apps/web`. C'est la cause directe du constat 1 | Amorcer un harnais (vitest + testing-library) est un chantier, pas un correctif |
| **`body: unknown`** | `client.ts:75` neutralise TypeScript sur **tous** les appels du module, pas seulement les approbations | Le typer proprement = revoir la signature de `acRequest` et ses ~30 appelants |
| **Pas de handler 422** | `apps/api/main.py` ne traduit pas `RequestValidationError` vers l'enveloppe d'erreur maison | Change le contrat d'erreur : à décider, pas à improviser |
| **Front ≈ ⅔ du back** | Sans écran : politiques, budgets, commandes opérateur, rotation de credential, édition projet/tâche | Périmètre produit |

---

## 5. Portée de cette intervention

**Fait** : les deux éditions du constat 1, et ce document.

**Délibérément pas fait** : aucun commit, aucun push, aucune PR, aucun déploiement ; aucune
modification du dépôt SGI ; aucune activation d'Agent Control ; aucune variable d'environnement
posée.

**Vérification effectuée** :
1. Lecture ligne à ligne des 5 maillons du constat 1 ; contrôle que `ApprovalOut.version: number`
   existe bien dans `apps/web/lib/contracts.ts` (l'interface a été extraite en entier — un
   `version: number` voisin appartient en fait à `AlertOut`, la confusion était facile) et que
   `Approvals.tsx` est l'**unique** appelant du hook.
2. `npm install` dans `apps/web` (l'installation était partielle : `typescript` absent,
   `node_modules/.bin` manquant) — 399 paquets installés.
3. `npx tsc --noEmit` → **0**, puis **deux mutations** confirmant que le garde-fou mord réellement
   (voir §1). `npm run lint` → **0**.

> `npm audit` signale 7 vulnérabilités préexistantes (1 critique, 5 hautes), dont `next@14.2.18`
> explicitement marqué vulnérable par npm. **Hors périmètre de cette intervention**, non traité,
> mais à ne pas laisser dormir : ce dépôt est exposé publiquement sur `ag.infinityauh.com`.
