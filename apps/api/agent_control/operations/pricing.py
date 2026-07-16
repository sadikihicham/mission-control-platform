"""Grille tarifaire versionnée et calcul de coût **décimal** — P6, SP6.

Le coût d'une consommation est **reproductible** : à `(provider, model,
input_tokens, output_tokens, calls)` et `pricing_version` donnés, le calcul
redonne toujours exactement le même `Decimal`. La version de tarif est stockée
sur chaque `agent_usage_record` : si la grille évolue, les enregistrements
anciens restent recalculables avec **leur** version (traçabilité, schéma
solution §`agent_usage_records`).

Jamais de `float` pour l'argent : tout est `Decimal`. Les tarifs sont exprimés
en unité monétaire **par 1000 tokens** (convention provider) et convertis en coût
par token en `Decimal`. Un modèle inconnu retombe sur un tarif par défaut borné
(jamais un coût nul silencieux qui fausserait budgets et réconciliation).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

# Version courante de la grille. Changer la grille = nouvelle version (les
# anciens enregistrements gardent la leur). Exposé via l'env pour un hôte réel.
CURRENT_PRICING_VERSION = "2026-07-01"

_THOUSAND = Decimal(1000)
# Précision de stockage du coût (aligné sur Numeric(20, 8) en base).
_COST_QUANT = Decimal("0.00000001")


@dataclass(frozen=True)
class ModelRate:
    """Tarif d'un modèle : prix par **1000** tokens (entrée/sortie), en devise."""

    input_per_1k: Decimal
    output_per_1k: Decimal
    currency: str = "USD"


# Grille par version → (provider, model) → tarif. `("*", "*")` = défaut borné.
# Valeurs indicatives (ordres de grandeur publics) — la source de vérité en prod
# viendra d'un port de tarification hôte ; ici, défaut déterministe et versionné.
_PRICING: dict[str, dict[tuple[str, str], ModelRate]] = {
    "2026-07-01": {
        ("anthropic", "claude-opus"): ModelRate(Decimal("15.00"), Decimal("75.00")),
        ("anthropic", "claude-sonnet"): ModelRate(Decimal("3.00"), Decimal("15.00")),
        ("anthropic", "claude-haiku"): ModelRate(Decimal("0.80"), Decimal("4.00")),
        ("openai", "gpt-4o"): ModelRate(Decimal("2.50"), Decimal("10.00")),
        ("openai", "gpt-4o-mini"): ModelRate(Decimal("0.15"), Decimal("0.60")),
        # Défaut borné (modèle/provider inconnu) — jamais 0 silencieux.
        ("*", "*"): ModelRate(Decimal("3.00"), Decimal("15.00")),
    }
}


def _rate(pricing_version: str, provider: str | None, model: str | None) -> ModelRate:
    table = _PRICING.get(pricing_version) or _PRICING[CURRENT_PRICING_VERSION]
    key = ((provider or "*").lower(), (model or "*").lower())
    return table.get(key) or table[("*", "*")]


@dataclass(frozen=True)
class CostBreakdown:
    """Résultat d'un calcul de coût — tout en `Decimal`, jamais `float`."""

    cost: Decimal
    unit_cost_input: Decimal
    unit_cost_output: Decimal
    currency: str
    pricing_version: str


def compute_cost(
    *,
    input_tokens: int,
    output_tokens: int,
    provider: str | None = None,
    model: str | None = None,
    pricing_version: str | None = None,
) -> CostBreakdown:
    """Calcule le coût `Decimal` d'une consommation, reproductible par version.

    `cost = input_tokens/1000 * input_per_1k + output_tokens/1000 * output_per_1k`,
    quantifié à 8 décimales (arrondi bancaire au plus proche). Les prix unitaires
    par token sont conservés pour audit du calcul.
    """
    version = pricing_version or CURRENT_PRICING_VERSION
    rate = _rate(version, provider, model)
    unit_in = (rate.input_per_1k / _THOUSAND)
    unit_out = (rate.output_per_1k / _THOUSAND)
    raw = Decimal(int(input_tokens)) * unit_in + Decimal(int(output_tokens)) * unit_out
    cost = raw.quantize(_COST_QUANT, rounding=ROUND_HALF_UP)
    return CostBreakdown(
        cost=cost,
        unit_cost_input=unit_in,
        unit_cost_output=unit_out,
        currency=rate.currency,
        pricing_version=version,
    )
