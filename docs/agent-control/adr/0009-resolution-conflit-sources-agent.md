# ADR-0009 — Résolution de conflit entre sources d'état d'un agent

Statut : accepté (P3, SP4)
Date : 2026-07-15

## Contexte

Un même `agents` (clé `agent_key`) peut être alimenté par **trois** sources qui
peuvent désaccorder sur son état :

1. **Sync fichier** (`services/mc_sync.py`) : lit `.mission-control/status/*.json`
   toutes les 2 s et marque ces lignes `meta["source"] = "mc-file"`.
2. **Heartbeat V0 Contract D** (`POST /agents/heartbeat`) : secret global partagé
   ou token d'enrôlement par agent ; met à jour `state/task/progress/…`.
3. **Ingest V1** (`POST /agent-control/v1/ingest/*`) : authentifié par credential
   individuel, tenant-aware, avec `sequence` monotone (`agents.last_sequence`).

Le contrat V1 (§8, invariant SP4 « jamais dernier écrivain implicite en
production ») interdit un « last-writer-wins » aveugle entre ces sources.

## Décision

Règle déterministe, sans dernier-écrivain implicite :

1. **Séparation des champs par propriétaire.**
   - Le **registre** (métadonnées : `display_name`, `runtime`, `provider`,
     `client_version`, `environment`, `capabilities`, `status`) est la propriété
     exclusive du **registre V1** (routes `manage_agents`). Ni le sync fichier ni
     les heartbeats ne l'écrivent.
   - La **projection live** (`state`, `task`, `progress`, `last_heartbeat`) reste
     partagée entre les trois sources, mais arbitrée par la règle 2.

2. **Monotonie par séquence pour l'ingest V1.** L'ingest V1 ne fait **jamais**
   régresser l'état : un événement/heartbeat de `sequence` strictement inférieure
   à `agents.last_sequence` ne met à jour ni `state`, ni `task`, ni `progress`
   (il rafraîchit seulement `last_heartbeat` — preuve de liveness). Les sources V0
   (fichier, Contract D) n'ont pas de séquence : elles restent un upsert simple,
   inchangé, et **ne touchent pas** `last_sequence`.

3. **Cloisonnement des identités de production.** En production, un agent piloté
   par l'ingest V1 possède un credential individuel et un `installation_id`. Le
   secret global V0 est désactivable (`MC_GLOBAL_INGEST_ENABLED=0`) ; le sync
   fichier et le secret global sont réservés au mode autonome/démo. Un agent ne
   doit pas être piloté simultanément par le fichier ET l'ingest V1 en production :
   la source fichier est un fast-path de démonstration, l'ingest V1 la voie métier.

4. **Pas de purge croisée.** Le sync fichier ne purge que les lignes
   `meta["source"] = "mc-file"` (garde déjà en place dans `heartbeat.py`) : un
   agent V1 (credential) n'est jamais supprimé par un balayage de fichiers, et
   réciproquement.

## Conséquences

- Aucune régression d'état possible via un paquet réseau ancien (invariant §10).
- Le registre V1 fait autorité sur les métadonnées ; la projection live reste
  tolérante multi-sources en mode autonome.
- En production, la recommandation opérationnelle est : credentials V1 +
  `MC_GLOBAL_INGEST_ENABLED=0` + watcher fichier désactivé (durcissement lot SP6).

## Alternatives rejetées

- **Last-writer-wins horodaté global** : un heartbeat réseau retardé écraserait un
  état plus récent ; interdit par le contrat en production. Rejeté.
- **Fusion des trois sources sur les mêmes champs sans séquence** : non
  déterministe, courses d'écriture. Rejeté au profit de la monotonie par séquence.
