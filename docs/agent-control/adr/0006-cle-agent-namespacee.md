# ADR-0006 — Clé d'agent globalement namespacée `<installation_key>:<local_key>`

Statut : accepté (SP1, Gate P0)
Date : 2026-07-15

## Contexte

Contract A impose `agents.agent_key` **globalement unique** (contrainte `unique`),
et Contract D l'utilise comme identité de heartbeat. V1 devient multi-installation
(multi-tenant) : deux tenants peuvent légitimement nommer un agent `builder-01`.
Réutiliser une clé locale nue casserait l'unicité globale.

## Décision

Pour V1, `agent_key` **reste global et unique** et est généré sous la forme
`<installation_key>:<local_key>` (ex. `local:builder-01`). Le producteur envoie
un `local_key` ; le serveur préfixe avec l'`installation_key` du contexte résolu.
`installation_key` vient de `HostContext.installation.installation_key`.

## Conséquences

- L'unicité de Contract A est **préservée** sans migration cassante.
- Les agents V0 existants (clé nue, sans `:`) restent valides : le mode compat les
  traite comme appartenant à l'installation `local`.
- Le parsing `installation_key, local_key = agent_key.split(":", 1)` est
  déterministe ; une clé sans `:` = installation `local` implicite.
- Le catalogue d'événements et les topics `agent:{id}` utilisent l'`id` UUID de
  l'agent, pas `agent_key`, pour éviter d'exposer la structure de clé en WS.

## Alternatives rejetées

- Rendre `agent_key` unique **par tenant** (drop de la contrainte globale) :
  mutation cassante de Contract A, casse les producteurs V0. Rejeté.
- Générer un UUID opaque comme clé de heartbeat : casse l'alignement volontaire
  avec le JSON `mc` (Contract D). Rejeté.
