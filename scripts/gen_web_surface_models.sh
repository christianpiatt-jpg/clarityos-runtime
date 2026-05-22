#!/usr/bin/env bash
# v0.2.0 Web Surface — Python model generator.
#
# Generates Pydantic v2 models from the canonical JSON Schema at:
#
#     web/src/contracts/webSurfaceV0_2.schema.json
#
# Output:
#
#     web_surface_models.py   (at repo root, next to web_surface.py)
#
# The TypeScript contract is the source of truth. Generation pipeline:
#
#     web/src/contracts/webSurfaceV0_2.ts          (hand-written)
#         → npm run contracts:gen
#     web/src/contracts/webSurfaceV0_2.schema.json (committed artifact)
#         → bash scripts/gen_web_surface_models.sh
#     web_surface_models.py                        (committed artifact)
#         → import in web_surface.py + tests
#
# A drift between any pair surfaces in CI:
#   * TS edited but schema not regenerated → web contracts:check fails
#   * schema edited but models not regenerated → scripts/check_web_surface_models.sh fails
#
# Why the pre-flatten step:
#   ts-json-schema-generator emits namespaced definition keys like
#   ``WebSurfaceV0_2.Request``. datamodel-code-generator interprets the
#   dot as a module separator and refuses to single-file output. We
#   flatten ``WebSurfaceV0_2.X`` → ``WebSurfaceV0_2X`` in a TEMP copy
#   of the schema before invoking codegen. The committed schema is
#   never touched (so the TS-side schema tests, which assert the
#   dotted names, continue to pass).
#
# Usage:
#
#     bash scripts/gen_web_surface_models.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCHEMA="${REPO_ROOT}/web/src/contracts/webSurfaceV0_2.schema.json"
OUTPUT="${REPO_ROOT}/web_surface_models.py"

if [[ ! -f "${SCHEMA}" ]]; then
    echo "::error::schema missing: ${SCHEMA}"
    echo "  (run 'npm run contracts:gen' in web/ first)"
    exit 1
fi

# --- 1. Pre-flatten the schema into a temp file ---------------------------
TMP_SCHEMA="$(mktemp -t webSurfaceV0_2.flat.XXXXXX.json)"
trap 'rm -f "${TMP_SCHEMA}"' EXIT

python - "${SCHEMA}" "${TMP_SCHEMA}" <<'PYEOF'
"""Flatten dotted namespace names in a JSON Schema so datamodel-code-
generator can emit a single-file Pydantic module. Keys + refs are
rewritten in lock-step; everything else passes through unchanged."""
import json
import sys

src_path, dst_path = sys.argv[1], sys.argv[2]

with open(src_path, "r", encoding="utf-8") as f:
    schema = json.load(f)

PREFIX = "WebSurfaceV0_2."
FLAT   = "WebSurfaceV0_2"  # joined form: WebSurfaceV0_2.Request → WebSurfaceV0_2Request


def remap(name: str) -> str:
    return FLAT + name[len(PREFIX):] if name.startswith(PREFIX) else name


def visit(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == "$ref" and isinstance(v, str):
                for ref_prefix in ("#/definitions/", "#/$defs/"):
                    if v.startswith(ref_prefix):
                        name = v[len(ref_prefix):]
                        out[k] = ref_prefix + remap(name)
                        break
                else:
                    out[k] = v
            else:
                out[k] = visit(v)
        return out
    if isinstance(obj, list):
        return [visit(v) for v in obj]
    return obj


schema = visit(schema)

for defs_key in ("definitions", "$defs"):
    if defs_key in schema and isinstance(schema[defs_key], dict):
        schema[defs_key] = {
            remap(k): v for k, v in schema[defs_key].items()
        }

with open(dst_path, "w", encoding="utf-8") as f:
    json.dump(schema, f, indent=2)
PYEOF

# --- 2. Run datamodel-code-generator over the flattened schema ------------
python -m datamodel_code_generator \
    --input "${TMP_SCHEMA}" \
    --input-file-type jsonschema \
    --output "${OUTPUT}" \
    --output-model-type pydantic_v2.BaseModel \
    --target-python-version 3.12 \
    --use-schema-description \
    --use-title-as-name \
    --use-double-quotes \
    --disable-timestamp \
    --custom-file-header "# Auto-generated from web/src/contracts/webSurfaceV0_2.schema.json.
# DO NOT HAND-EDIT — run \`bash scripts/gen_web_surface_models.sh\` instead.
# The schema itself is generated from the canonical TypeScript contract
# at web/src/contracts/webSurfaceV0_2.ts; see docs/web_surface/v0.2.0-contract.md
# for the full bridge."

echo "✓ wrote ${OUTPUT#${REPO_ROOT}/}"
