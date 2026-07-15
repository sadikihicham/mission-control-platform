---
name: build-agent-control
description: Pilote le plan complet du module Agent Control avec l'orchestrateur et les sept sous-agents Claude Code. À invoquer manuellement pour planifier, exécuter, reprendre ou afficher l'état du chantier.
argument-hint: "[plan|execute|resume|status]"
disable-model-invocation: true
---

Interprète `$ARGUMENTS` comme l'une des actions suivantes :

- `plan` : lis l'état du dépôt et les documents Agent Control, puis demande à `agent-control-orchestrator` de produire la checklist P0–P7 sans modifier le code ;
- `execute` : délègue à `agent-control-orchestrator` et commence par la baseline puis SP1/Gate P0 ;
- `resume` : inspecte l'état Git, contrats, tests et handoffs, puis demande à l'orchestrateur de reprendre au premier gate incomplet ;
- `status` : inspecte en lecture seule les livrables, diffs et résultats de tests, puis rapporte chaque gate comme `non commencé`, `en cours`, `validé` ou `bloqué` avec preuve.

Si aucun argument valide n'est fourni, affiche l'usage et ne modifie rien.

Avant délégation, lis :

- `CLAUDE.md` et `AGENTS.md` ;
- `.mission-control/CONTRACTS.md` ;
- `docs/agent-control/01_ANALYSE_EXISTANT.md` ;
- `docs/agent-control/02_SCHEMA_SOLUTION.md` ;
- `docs/agent-control/03_PROMPT_GLOBAL.md` ;
- `docs/agent-control/04_GUIDE_CLAUDE_CODE.md`.

Ne contourne jamais les permissions Claude Code. N'utilise pas les agent teams sauf demande explicite ou environnement déjà configuré. Les sous-agents standards sont le mode par défaut.

