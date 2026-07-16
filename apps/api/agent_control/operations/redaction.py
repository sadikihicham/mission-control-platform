"""Redaction centralisée des données sensibles — P6, SP6.

Point unique de masquage pour **tout** ce qui est persisté ou exposé hors du
strict transit chiffré : audit (`mc_audit_logs`), alertes (`agent_alerts`),
timelines de runs (P4) et contextes d'approbation. Invariant du Gate P6 : jamais
de secret / token / mot de passe / prompt brut / PII évidente dans un log
d'audit, une alerte ou une métrique.

Deux niveaux, non destructifs pour l'original :

1. **par clé** : toute clé dont le nom contient un marqueur sensible
   (`secret`, `token`, `password`, `authorization`, `api_key`, `credential`,
   `prompt`, `raw`, `cookie`, `session`, …) voit sa valeur remplacée par le
   sentinel `[redacted]`, quelle que soit la profondeur ;
2. **par valeur** : une chaîne qui *ressemble* à un secret (préfixe de credential
   agent `ac_…`, en-tête `Bearer …`, JWT à trois segments, longue chaîne
   haute-entropie) est masquée même sous une clé anodine — filet de sécurité
   contre les fuites accidentelles dans un champ libre.

Conservateur par défaut : mieux vaut sur-masquer que fuiter. `[redacted]` est un
sentinel stable (les consommateurs peuvent le détecter).
"""
from __future__ import annotations

import re

REDACTED = "[redacted]"

# Marqueurs de nom de clé sensibles (sous-chaîne, insensible à la casse).
SENSITIVE_KEY_MARKERS: tuple[str, ...] = (
    "secret",
    "token",
    "password",
    "passwd",
    "authorization",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
    "credential",
    "cred",
    "prompt",
    "raw",
    "cookie",
    "session",
    "ssn",
    "pin",
    "otp",
    "signature",
)

# Motifs de VALEUR qui trahissent un secret même sous une clé anodine.
_BEARER = re.compile(r"^Bearer\s+\S+", re.IGNORECASE)
_JWT = re.compile(r"^[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}$")
# Préfixe de credential agent (`generate_agent_credential` → `ac_<hex>.<secret>`).
_AGENT_CRED = re.compile(r"\bac_[0-9a-f]{6,}\b")
# Longue chaîne compacte sans espace (haute entropie probable : clé/hash/token).
_HIGH_ENTROPY = re.compile(r"^[A-Za-z0-9_\-+/=]{40,}$")


def _key_is_sensitive(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in SENSITIVE_KEY_MARKERS)


def _value_looks_secret(value: str) -> bool:
    v = value.strip()
    if not v:
        return False
    return bool(
        _BEARER.match(v)
        or _JWT.match(v)
        or _AGENT_CRED.search(v)
        or _HIGH_ENTROPY.match(v)
    )


def redact_text(value: str) -> str:
    """Masque une chaîne si elle ressemble à un secret ; sinon la renvoie telle quelle."""
    return REDACTED if _value_looks_secret(value) else value


def redact(value):
    """Redaction récursive non destructive d'une valeur arbitraire.

    - dict : masque la valeur des clés sensibles, descend dans le reste ;
    - list/tuple : redaction élément par élément ;
    - str : masquée si elle ressemble à un secret ;
    - autre (int/float/bool/None) : inchangé.
    """
    if isinstance(value, dict):
        out: dict = {}
        for key, val in value.items():
            if isinstance(key, str) and _key_is_sensitive(key):
                out[key] = REDACTED
            else:
                out[key] = redact(val)
        return out
    if isinstance(value, list | tuple):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def redact_dict(payload: dict | None) -> dict:
    """Redaction d'un mapping (retourne toujours un dict, `{}` si `None`)."""
    if not payload:
        return {}
    result = redact(payload)
    return result if isinstance(result, dict) else {}
