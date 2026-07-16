# Dérives doc/code Agent Control — pense-bête inter-sessions

Convention informelle : aucun mécanisme de bulletin partagé n'existait encore dans ce repo
(contrairement au skill `chef-sessions` de SGI) — ce fichier sert de pense-bête durable pour
les prochaines sessions qui codent contre `CONTRACTS_AGENT_CONTROL_V1.md`. Non tracké par
défaut ; à committer si une session juge que ça vaut la peine de le garder.

## Vérifié le 2026-07-16 (après merge de P6, avant P7/P8)

**1. Routes `/agent-control/v1/projects*` et `/tasks*` documentées mais absentes du code**
— **RÉSOLU par P8** (`e16f810` "expose projets & tâches V1 tenant-scoped", `f9e5394` migration
`installation_id`, `d9c67b8` écran frontend). Plus d'action requise sur ce point.

**2. Clé de pagination `page` (doc) vs `page_info` (code livré) — TOUJOURS EN SUSPENS**
`.mission-control/CONTRACTS_AGENT_CONTROL_V1.md:186` et `docs/agent-control/examples/v1/
examples.json:21` documentent encore `"page": {...}`. Tout le code P0-P6 (control/schemas.py,
operations/schemas.py, registry/schemas.py, runs/schemas.py + routes correspondantes) utilise
`page_info`. Reconfirmé encore présent après merge de P7/P8 (grep direct, 2026-07-16). Un client
codé sur la forme documentée cherchera une clé `page` inexistante. Fix trivial : corriger le §7
du contrat + l'exemple JSON pour dire `page_info`, ou l'inverse si `page` est jugé préférable
(mais alors casser un contrat déjà consommé par des tests réels serait le mauvais sens).

**3. Canal temps réel V1 (`/agent-control/ws`, `ac:events`) documenté comme figé, jamais câblé —
TOUJOURS EN SUSPENS** `CONTRACTS_AGENT_CONTROL_V1.md` §10 décrit l'endpoint et le canal Redis.
Le code d'écriture existe (`apps/api/agent_control/operations/outbox.py`, table
`mc_outbox_events`) mais rien ne consomme ces lignes : reconfirmé après P7/P8 (aucune route
`/agent-control/ws`, aucun abonnement `ac:events` dans `apps/api/realtime/ws.py` ou `main.py` —
seul le `/ws` V0 existe). Les événements V1 restent `pending` en base indéfiniment. Si une phase
future (frontend Agent Control, dashboard live) suppose que ces événements arrivent en temps
réel, elle codera contre du vide tant que ce relais n'est pas implémenté.

**Comment appliquer** : avant de construire quoi que ce soit qui dépend de la pagination ou du
temps réel V1 documentés, vérifier le code réel plutôt que de faire confiance au contrat sur ces
deux points précis. Le reste du contrat (ports, HostContext, capacités/rôles, machines d'état,
codes d'erreur) a été vérifié fidèle au code.
