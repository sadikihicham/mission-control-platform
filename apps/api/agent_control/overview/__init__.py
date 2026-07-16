"""Vue d'ensemble V1 (P7) — `/health`, `/dashboard`, activation d'installation.

Ferme le gap Gate P7 : ces routes étaient déclarées dans `ROUTE_CAPABILITIES`
mais non exposées. Toutes tenant-scoped (ADR-0003), fail-closed, agrégats dérivés
serveur — jamais de compteur fourni par le client (aucun mock runtime).
"""
