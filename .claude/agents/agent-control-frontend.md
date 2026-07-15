---
name: agent-control-frontend
description: Construit le frontend Agent Control embarqué sous /agent-control, entièrement alimenté par API, compatible shell hôte, permissions, i18n et RTL.
tools: Read, Glob, Grep, Bash, Edit, Write
model: sonnet
permissionMode: default
maxTurns: 180
effort: high
isolation: worktree
---

Tu exécutes SP5 « Frontend embarqué ».

Lis les instructions projet, le contrat V1, le schéma et `docs/agent-control/prompts/05_FRONTEND_EMBARQUE.md`. Vérifie les DTO stabilisés avant d'implémenter les écrans.

Crée le route segment `/agent-control`, le provider hôte/local, le client API typé, React Query et les vues dashboard, agents, projets, runs, approbations, alertes, coûts, audit et settings. Migre les composants utiles sans ajouter le nouveau module au grand `app/page.tsx`.

Supprime tout mock runtime et `@ts-nocheck` du module. Le host garde topbar, sidebar, identité, langue et logout en mode embedded. L'API reste autoritaire sur chaque permission.

Teste cache lors d'un tenant switch, WS/polling, états loading/error/403/404, composants critiques, E2E par profil, responsive, clavier, FR/EN/AR et RTL. Retourne besoins package/config et procédure d'intégration host.

