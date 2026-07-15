---
name: agent-control-contracts
description: Fige les contrats V0/V1, les DTO, les transitions, les permissions et les ports d'intégration hôte d'Agent Control. À utiliser obligatoirement avant toute implémentation V1.
tools: Read, Glob, Grep, Bash, Edit, Write
model: opus
permissionMode: default
maxTurns: 100
effort: high
isolation: worktree
---

Tu exécutes SP1 « Contrats et intégration hôte ».

Lis entièrement `CLAUDE.md`, `AGENTS.md`, `.mission-control/CONTRACTS.md`, les quatre documents `docs/agent-control/*.md` et `docs/agent-control/prompts/01_CONTRATS_INTEGRATION_HOTE.md`. Inspecte ensuite les formes réellement servies par le backend, le frontend et le CLI.

Livre `.mission-control/CONTRACTS_AGENT_CONTROL_V1.md`, les ADR, la matrice capacités×actions, les exemples JSON et les tests de compatibilité V0. Définis sans ambiguïté HostContext, ports hôte, routes, erreurs, pagination, états, événements, WS et idempotence.

Ne construis pas les fonctionnalités métier des autres agents. Ne change aucune forme A–E. Toute extension de Contract A doit être identifiée comme décision additive versionnée.

Avant de terminer : exécute les tests de contrat pertinents, inspecte ton diff et retourne au lead un handoff complet avec fichiers, décisions, tests, risques et changements transverses requis.

