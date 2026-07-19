# ADR-0011 — Pont d'activation par tenant : webhook SGI → `mc_installations.status`

Statut : **accepté** (décision prise en autonomie, autorisation explicite de Hicham le 2026-07-19,
pendant son absence — les 3 questions ouvertes ci-dessous étaient explicitement signalées comme
« à trancher avec Hicham » par l'agent de scoping ; tranchées ici avec la justification la plus
conservatrice à chaque fois, à faire valider a posteriori).
Date : 2026-07-19

## Contexte

ADR-0010 §3 documentait un écart assumé : `JwtHostAdapter.resolve_tenant` (`apps/api/integrations/
jwt_adapter.py`) fait déjà autorité fail-closed sur `mc_installations.status == "active"`, mais rien
ne pilote ce champ automatiquement depuis SGI — activation manuelle jusqu'ici.

Un agent de scoping dédié (lecture seule, aucune implémentation) a vérifié dans le code des deux
repos (pas supposé) :
- SGI n'a **aucun** endpoint admin pour basculer une ligne `subscription` — prérequis commun aux
  deux mécanismes envisagés, pas un coût spécifique à l'un des deux.
- SGI n'a **aucun** pattern de webhook sortant réutilisable (les seuls existants sont entrants —
  `core/comms/inbound_port.py`, WhatsApp/Twilio — hors-sujet).
- SGI n'a **aucun** mécanisme de credential service-à-service (grep `api_key`/`client_credentials`/
  `shared_secret` : uniquement des clés sortantes vers des providers tiers, rien d'entrant).
- Un mécanisme **Pull** (mission_control_plateforme interroge périodiquement `GET /api/v1/tenant/
  subscriptions/by-key/{activity_key}`) casserait la doctrine SGI existante : le tenant n'est jamais
  résolu autrement que via le JWT de l'utilisateur courant (`require_company`, RLS) — un Pull
  nécessiterait un nouveau credential cross-tenant, contraire à cette doctrine.

## Décision

**Push (webhook)**, pas Pull — recommandation directe de l'agent de scoping, retenue telle quelle.

### 1. Mécanisme d'authentification du webhook
**HMAC-SHA256** sur le corps brut de la requête (secret partagé `SGI_WEBHOOK_SECRET`, nouvel env var
des deux côtés — jamais commité en clair), pas un simple jeton statique en en-tête. Justification :
ce webhook peut faire basculer l'accès d'un tenant payant ; un jeton statique volé dans un log HTTP
suffirait à le rejouer indéfiniment, une signature HMAC sur le corps limite le rejeu à la fenêtre de
validité si on ajoute un timestamp + nonce (voir Conséquences). Coût quasi nul par rapport à un
secret partagé simple (déjà le cas du heartbeat V0 `X-MC-Token` — mais ce dernier n'autorise qu'un
report d'état, jamais un changement d'accès ; le webhook subscription mérite le cran de sécurité
au-dessus).

### 2. Bascule d'une ligne existante, PAS d'auto-provisioning
Le webhook **ne crée jamais** de ligne `mc_installations` — il ne fait que basculer le `status`
d'une ligne déjà existante (identifiée par `external_tenant_id == company_id`). Si aucune ligne
n'existe pour ce `company_id`, le webhook répond une erreur explicite (pas un no-op silencieux) et
n'auto-provisionne rien. Justification : provisionner un tenant Agent Control doit rester un acte
d'onboarding délibéré (revue humaine, `installation_key` généré consciemment) — pas un effet de bord
d'un webhook déclenché par un admin SGI qui ne sait même pas que "activer agent_control" a cet effet
de bord côté d'un système tiers. Plus conservateur que ce que l'agent de scoping envisageait comme
option, choisi délibérément dans le doute.

### 3. Mapping du statut
`enabled=true` → `mc_installations.status="active"` ; `enabled=false` → `status="suspended"` — tel
qu'inféré du commentaire du modèle (`apps/api/models/agent_control.py`, enum `active|suspended|
archived`). `archived` n'est jamais atteint par ce webhook (réservé à un futur off-boarding manuel).

## Conséquences

- Nouveau endpoint entrant côté `mission_control_plateforme` : `POST /integrations/sgi/subscription-
  events`, vérifie la signature HMAC (rejette 401 si absente/invalide — fail-closed, jamais un
  fallback vers un accès non vérifié), payload `{company_id, activity_key, enabled}`, ignore tout
  `activity_key != "agent_control"` (ce canal n'est pas générique aux autres activités SGI).
- Nouveau endpoint sortant + admin côté SGI : l'endpoint de bascule de subscription (prérequis,
  n'existait pas) déclenche l'appel HTTP sortant signé après le commit DB de la subscription — jamais
  avant (le webhook ne doit jamais annoncer un état pas encore committé).
- Écart assumé, volontairement non traité ici : pas de retry/outbox pour ce webhook (si l'appel
  échoue réseau, l'admin SGI doit relancer manuellement — un vrai outbox comme celui d'Agent Control
  V1 serait plus robuste mais hors scope de cette itération, à durcir plus tard si ce chemin s'avère
  fragile en usage réel).
- Décision prise sans confirmation de Hicham (absent) — **à revalider explicitement à son retour**,
  en particulier le choix HMAC (vs secret simple) et le refus d'auto-provisioning, qui sont les deux
  points où cette ADR a été plus conservatrice que nécessaire pour rester réversible.

## Alternatives rejetées

- **Pull/polling** : rejeté, cf. Contexte — casse la doctrine tenant-jamais-hors-JWT de SGI.
- **Secret statique simple (comme `X-MC-Token`)** : rejeté pour CE webhook spécifiquement (change un
  accès, pas juste un report d'état) — HMAC préféré malgré le coût d'implémentation légèrement plus
  élevé.
- **Auto-provisioning `mc_installations` depuis le webhook** : rejeté — onboarding doit rester un
  acte humain délibéré, pas un effet de bord.
