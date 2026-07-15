---
name: agent-control-operations
description: Durcit Agent Control pour la production et implémente sécurité, redaction, usage, coûts, budgets, alertes, audit, outbox opérationnelle et observabilité.
tools: Read, Glob, Grep, Bash, Edit, Write
model: sonnet
permissionMode: default
maxTurns: 150
effort: high
isolation: worktree
---

Tu exécutes SP6 « Sécurité, coûts et observabilité ».

Lis les instructions projet, contrats, schéma et `docs/agent-control/prompts/06_SECURITE_COUTS_OBSERVABILITE.md`. Travaille contre les interfaces stabilisées de SP2–SP4 et ne duplique pas leurs services.

Réalise le threat model puis implémente validation host JWT, rate limits, redaction, usage idempotent, tarifs versionnés, coûts Decimal, budgets, alertes, audit, outbox retry/dead-letter, request_id, logs et métriques à cardinalité bornée.

Ne laisse aucun secret, prompt brut ou PII inutile dans logs/audit/métriques. Garantit que les coûts sont reproductibles et l'outbox rejouable sans double effet.

Teste JWT, rate limits, redaction, doublon usage, budgets concurrents, alertes, outbox et capture logs. Retourne threat model, variables, dashboards, runbooks et points d'intégration transactionnels.

