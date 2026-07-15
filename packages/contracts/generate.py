"""Génère les types TypeScript du frontend depuis l'OpenAPI **réel** de l'API.

Source de vérité : les schémas Pydantic exportés par FastAPI (Contrats C/D/E).
Ce script est déterministe et hors-ligne (il importe l'app, sans réseau) :

    docker compose -f infra/docker-compose.yml run --rm ag-api \
        python -m packages.contracts.generate

Sorties (committées, ne pas éditer à la main) :
  - packages/contracts/openapi.json   — snapshot du schéma OpenAPI ;
  - packages/contracts/types.ts       — types TS canoniques du monorepo ;
  - apps/web/lib/contracts.ts         — copie in-tree consommée par le web
    (Next ne transpile de façon fiable que les fichiers sous apps/web).

Règle d'optionalité : ces DTO sont des **réponses** — Pydantic sérialise
toujours chaque champ (défauts et null inclus), donc toutes les propriétés sont
émises comme présentes ; un champ nullable devient `T | null`. Cela reproduit
exactement les formes gelées côté frontend (aucune propriété optionnelle
surprise qui casserait un accès `strict`).
"""
from __future__ import annotations

import json
from pathlib import Path

# Schémas de composants à ne PAS émettre (bruit interne FastAPI/validation).
_SKIP = {"HTTPValidationError", "ValidationError"}

_ROOT = Path(__file__).resolve().parents[2]
_OPENAPI_PATH = _ROOT / "packages" / "contracts" / "openapi.json"
_TYPES_PATH = _ROOT / "packages" / "contracts" / "types.ts"
_WEB_PATH = _ROOT / "apps" / "web" / "lib" / "contracts.ts"

_HEADER = """// -----------------------------------------------------------------------------
// FICHIER GÉNÉRÉ — NE PAS ÉDITER À LA MAIN.
// Source : OpenAPI de l'API (packages/contracts/openapi.json).
// Régénérer : `make contracts` (cf. packages/contracts/generate.py).
// Types alignés sur les schémas Pydantic (Contrats C/D/E gelés).
// -----------------------------------------------------------------------------

"""


def _ts_type(schema: dict) -> str:
    """Traduit un sous-schéma OpenAPI en type TypeScript."""
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]
    if "enum" in schema:
        return " | ".join(json.dumps(v, ensure_ascii=False) for v in schema["enum"])
    if "anyOf" in schema:
        parts = [_ts_type(s) for s in schema["anyOf"] if s.get("type") != "null"]
        has_null = any(s.get("type") == "null" for s in schema["anyOf"])
        union = " | ".join(dict.fromkeys(parts)) or "unknown"
        return f"{union} | null" if has_null else union
    t = schema.get("type")
    if t == "array":
        return f"{_ts_type(schema.get('items', {}))}[]"
    return {
        "string": "string",
        "integer": "number",
        "number": "number",
        "boolean": "boolean",
        "object": "Record<string, unknown>",
        "null": "null",
    }.get(t, "unknown")


def _emit_schema(name: str, schema: dict) -> str:
    if "enum" in schema:
        union = " | ".join(json.dumps(v, ensure_ascii=False) for v in schema["enum"])
        return f"export type {name} = {union};\n"
    props = schema.get("properties")
    if not props:
        return f"export type {name} = Record<string, unknown>;\n"
    lines = [f"export interface {name} {{"]
    for prop, sub in props.items():
        lines.append(f"  {prop}: {_ts_type(sub)};")
    lines.append("}\n")
    return "\n".join(lines)


def render(openapi: dict) -> str:
    schemas = openapi.get("components", {}).get("schemas", {})
    body = [_HEADER]
    for name in sorted(schemas):
        if name in _SKIP:
            continue
        body.append(_emit_schema(name, schemas[name]))
        body.append("")
    return "\n".join(body).rstrip() + "\n"


def main() -> None:
    from apps.api.main import app

    openapi = app.openapi()
    _OPENAPI_PATH.write_text(json.dumps(openapi, ensure_ascii=False, indent=2) + "\n")
    ts = render(openapi)
    _TYPES_PATH.write_text(ts)
    _WEB_PATH.write_text(ts)
    print(f"OpenAPI → {_OPENAPI_PATH}")
    print(f"types TS → {_TYPES_PATH}")
    print(f"types TS (web) → {_WEB_PATH}")


if __name__ == "__main__":
    main()
