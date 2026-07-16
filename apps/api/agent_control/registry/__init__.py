"""Registre d'agents V1 (SP2/P7) — routes HTTP au-dessus des modèles Contract A+.

Ce lot ferme le gap identifié au Gate P7 : les colonnes de registre
(`Agent.installation_id`, `display_name`, `status`, `last_sequence`, …,
migration 0011) et les credentials (`agent_credentials`) existaient déjà, mais
aucune route HTTP `/agent-control/v1/agents*` ne les exposait. Ces modules
n'ajoutent aucune colonne : ils exposent, tenant-scoped et fail-closed, ce que
le contrat V1 figé déclarait déjà dans `ROUTE_CAPABILITIES`.
"""
