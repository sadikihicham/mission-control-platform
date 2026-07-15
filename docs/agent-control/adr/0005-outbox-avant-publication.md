# ADR-0005 — Outbox transactionnel avant publication d'événements

Statut : accepté (SP1, Gate P0)
Date : 2026-07-15

## Contexte

Le flux V0 (Contract E) publie sur Redis directement après le commit DB
(`publish_event`, non bloquant). C'est acceptable pour un état courant volatile,
mais V1 introduit des **faits historiques** (`agent_events`), des commandes et des
notifications/webhooks qui ne doivent **ni se perdre, ni se dupliquer** si Redis
est indisponible ou si le process meurt entre le commit et la publication.

## Décision

Les événements V1 sont écrits dans `mc_outbox_events` **dans la même
transaction** que le fait métier (run, step, commande, décision, usage). Un
relais lit l'outbox et publie ensuite vers Redis (`ac:events`), notifications et
webhooks, avec statut, tentatives, `next_attempt_at` et erreur. La publication est
**au moins une fois** ; les consommateurs déduplifient par `event_id`
(idempotence, §10 du contrat).

PostgreSQL reste la source de vérité ; Redis n'est qu'un transport. Un Redis mort
ne perd jamais le fait métier ni ne fait échouer l'écriture.

## Conséquences

- La reprise WS (`last_event_id`) rejoue depuis `agent_events`, pas depuis Redis.
- Le fan-out WS est estampillé tenant + topic à la publication (§10).
- Coût : une table outbox + un relais (lot SP4/SP6). SP1 fige seulement le contrat.

## Alternatives rejetées

- Publier directement dans la transaction applicative (double-écriture DB+Redis
  non atomique) : perte ou duplication sur crash/panne Redis. Rejeté.
- S'appuyer sur Redis comme source de vérité : contredit l'hypothèse verrouillée
  « PostgreSQL fait foi ». Rejeté.
