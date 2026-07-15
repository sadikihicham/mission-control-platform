# Guide d'utilisation avec Claude Code

Cette édition transforme le plan Agent Control en configuration native Claude Code : un agent orchestrateur, sept sous-agents spécialisés et une skill manuelle.

## Contenu Claude Code

```text
.claude/
  agents/
    agent-control-orchestrator.md
    agent-control-contracts.md
    agent-control-data.md
    agent-control-api.md
    agent-control-runtime.md
    agent-control-frontend.md
    agent-control-operations.md
    agent-control-qa.md
  skills/
    build-agent-control/
      SKILL.md
  settings.agent-control.example.json
```

## Prérequis

- utiliser une version récente de Claude Code ;
- exécuter `claude --version`, puis `claude update` si nécessaire ;
- démarrer Claude Code depuis la racine du dépôt ;
- conserver `CLAUDE.md`, `.mission-control/CONTRACTS.md` et les documents `docs/agent-control/` accessibles ;
- valider ou committer la configuration et les documents avant d'utiliser les sous-agents en worktree, afin que leurs copies isolées possèdent les mêmes sources de vérité ;
- ne jamais activer `--dangerously-skip-permissions` pour ce build.

Les définitions utilisent `isolation: worktree`, disponible sur les versions récentes de Claude Code. Si l'environnement ne supporte pas cette option, retirer uniquement cette ligne et exécuter les spécialistes séquentiellement pour éviter les conflits.

## Démarrage recommandé

### Option 1 — Skill depuis une session normale

```text
/build-agent-control plan
/build-agent-control execute
/build-agent-control status
/build-agent-control resume
```

La skill demande à Claude de déléguer à `agent-control-orchestrator` et de respecter les gates du plan.

### Option 2 — Orchestrateur comme session principale

```bash
claude --agent agent-control-orchestrator
```

Puis :

```text
Exécute le build Agent Control à partir de la baseline et commence par le Gate P0.
```

Cette option donne directement à la session principale le rôle d'orchestrateur et limite ses délégations aux sept spécialistes déclarés.

### Option 3 — Un spécialiste ciblé

```bash
claude --agent agent-control-contracts
claude --agent agent-control-data
claude --agent agent-control-qa
```

Ou, dans une session Claude Code, mentionner explicitement le sous-agent :

```text
@agent-agent-control-contracts exécute SP1 et rends le Gate P0 vérifiable.
```

## Ordre imposé

1. `agent-control-contracts` termine SP1 et le contrat V1 est intégré.
2. `agent-control-data` réalise les fondations persistantes.
3. `agent-control-api` et `agent-control-runtime` travaillent contre le contrat et les modèles stabilisés.
4. `agent-control-frontend` consomme les DTO stabilisés.
5. `agent-control-operations` ajoute sécurité, coûts et observabilité.
6. `agent-control-qa` exécute le gate final et recommande go/no-go.

L'orchestrateur peut paralléliser uniquement les tâches dont les fichiers et contrats sont indépendants. Les migrations, contrats et fichiers transverses restent séquentiels.

## Agent teams facultatives

Claude Code propose aussi les agent teams, mais cette fonctionnalité reste expérimentale. Le dispositif livré fonctionne avec les sous-agents standards et ne l'exige pas. Pour une expérimentation contrôlée, fusionner la variable de `.claude/settings.agent-control.example.json` dans les settings du projet, puis demander à l'orchestrateur de créer une équipe à partir des types de sous-agents existants.

Ne jamais faire travailler deux coéquipiers sur le même fichier. Le lead doit attendre leurs résultats, inspecter les diffs et intégrer les changements avant de fermer l'équipe.

## Hooks Mission Control facultatifs

Le fichier `.claude/settings.agent-control.example.json` montre comment connecter :

- `SessionStart` à `apps/agent-cli/hooks/session_start.sh` ;
- `PreToolUse` à `apps/agent-cli/hooks/pre_tool_use.sh` ;
- `Stop` à `apps/agent-cli/hooks/stop.sh`.

Ne pas remplacer `.claude/settings.local.json`. Fusionner seulement le bloc `hooks` souhaité. Les scripts sont non bloquants : une API Mission Control indisponible ne doit pas interrompre Claude Code.

## Permissions

Les agents utilisent `permissionMode: default`. Ils demandent donc l'autorisation pour les actions qui l'exigent. Les définitions n'autorisent ni push, ni PR, ni déploiement. Le fichier d'exemple ne contient aucun secret et ne modifie pas les permissions existantes.

## Validation de l'installation

1. Démarrer `claude` à la racine.
2. Exécuter `/agents` et vérifier les huit agents `agent-control-*`.
3. Exécuter `/build-agent-control status`.
4. Vérifier que Claude lit l'analyse, le schéma et les contrats avant de proposer des modifications.
5. Exécuter `/doctor` si un agent n'apparaît pas ou si un nom est dupliqué.

## Sources officielles Claude Code

- Sous-agents : <https://code.claude.com/docs/en/sub-agents>
- Skills : <https://code.claude.com/docs/en/slash-commands>
- Agent teams : <https://code.claude.com/docs/en/agent-teams>
- Hooks : <https://code.claude.com/docs/en/hooks-guide>

