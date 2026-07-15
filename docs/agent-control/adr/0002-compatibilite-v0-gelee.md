# ADR-0002 — Compatibilité V0 gelée par tests, dérives documentées non corrigées

Statut : accepté (SP1, Gate P0)
Date : 2026-07-15

## Contexte

Les contrats A–E (`.mission-control/CONTRACTS.md`) ont des producteurs et écrans
vivants : CLI `mc-platform`, fichiers `.mission-control/status/`, heartbeat
`POST /agents/heartbeat`, WS `/ws`, DTO REST du frontend. Des dérives de nommage
et de documentation existent (voir table §2 du contrat V1).

## Décision

1. **Geler par snapshot** les formes V0 réellement servies via
   `apps/api/tests/test_agent_control_v0_freeze.py` : aucun champ existant ne
   disparaît, les dérives de nommage `agent`/`agent_key` et
   `updated_at`/`last_heartbeat` restent séparées, les erreurs V0 gardent
   `{"detail": ...}`, le canal reste `mc:events`, les KPI restent au nombre de 7.
2. **Documenter, pas corriger en urgence** les dérives de documentation
   (`AGENTS.md` : `company_id`, 5 KPI, CI Actions) — la correction de doc est un
   changement du lead (fichier transverse), pas un travail SP1.
3. Toute correction future d'une dérive **préserve les anciens champs** ou passe
   par un **adaptateur de réponse** ; jamais un renommage cassant.

## Conséquences

- Les six autres spécialistes construisent V1 sans risquer de casser V0.
- V1 vit dans un espace **disjoint** : `/agent-control/v1`, `/agent-control/ws`,
  canal `ac:events`, enveloppe d'erreur `{"error": {...}}`, types d'événements du
  catalogue — aucun chevauchement avec V0.

## Alternatives rejetées

- Corriger les dérives de nommage tout de suite : casse le CLI, les fichiers de
  statut et le frontend. Rejeté au profit de la stabilité.
