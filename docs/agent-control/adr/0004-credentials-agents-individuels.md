# ADR-0004 — Credentials agents individuels, hashés, scopés, rotatifs, révocables

Statut : accepté (SP1, Gate P0)
Date : 2026-07-15

## Contexte

Contract D authentifie l'ingest par un **secret global** `MC_INGEST_TOKEN`
(header `X-MC-Token`). Depuis migration 0005, un enrôlement opt-in émet un token
propre par agent (`agents.token_hash`). Mais il n'y a ni scopes, ni expiration,
ni rotation de première classe, ni portée. Une flotte métier distribuée exige des
identités d'agents révocables individuellement.

## Décision

V1 introduit une table dédiée `agent_credentials` (schéma §7) :
`id, agent_id, key_prefix, secret_hash, scopes, expires_at, last_used_at,
revoked_at, created_by`. Propriétés :

- le **secret brut n'est renvoyé qu'à la création/rotation** (`credential_created`),
  jamais stocké en clair — seul `secret_hash` persiste ;
- **scopes** explicites (ex. `ingest`, `commands`) ;
- **expiration** et **rotation** (rotation = nouveau credential + révocation de
  l'ancien, machine d'état `credential`) ;
- **révocation** immédiate : un credential révoqué est refusé au prochain appel et
  ne peut jamais agir pour un autre agent/tenant.

L'ingest V1 (`/ingest/*`, `/agent/commands*`) s'authentifie par ce credential, pas
par le JWT utilisateur (`AGENT_CREDENTIAL` dans la matrice).

## Conséquences

- Contract D (secret global + enrôlement) reste **mode de compatibilité**
  désactivable en production via `MC_GLOBAL_INGEST_ENABLED=0` (ADR-0002, §13 schéma).
- Le serveur dérive tenant + agent du credential et refuse tout `agent_key`
  divergent (`permission_denied`).

## Alternatives rejetées

- Conserver un secret global unique en production : pas de révocation
  individuelle, pas de scoping, replay trivial entre agents. Rejeté.
- Stocker le secret brut « pour debug » : fuite garantie. Rejeté (hash uniquement).
