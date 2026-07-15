# ADR — Agent Control

Décisions d'architecture du module Agent Control (V1). Chaque ADR est
autoportant. Source de vérité du contrat : `.mission-control/CONTRACTS_AGENT_CONTROL_V1.md`.

| ADR | Titre |
|---|---|
| [0001](0001-bounded-context-agent-control.md) | Agent Control est un bounded context, pas une seconde plateforme |
| [0002](0002-compatibilite-v0-gelee.md) | Compatibilité V0 gelée par tests, dérives documentées |
| [0003](0003-tenant-host-owned.md) | Le tenant est propriété de l'hôte, résolu serveur |
| [0004](0004-credentials-agents-individuels.md) | Credentials agents individuels, hashés, scopés, rotatifs, révocables |
| [0005](0005-outbox-avant-publication.md) | Outbox transactionnel avant publication d'événements |
| [0006](0006-cle-agent-namespacee.md) | Clé d'agent namespacée `<installation_key>:<local_key>` |
| [0007](0007-extensions-additives-contract-a.md) | Extensions du Contract A additives et versionnées (migrations 0008+) |
| [0008](0008-mapping-rbac-hote-vers-capacites.md) | Mapping RBAC hôte → capacités (adaptateur local) |
