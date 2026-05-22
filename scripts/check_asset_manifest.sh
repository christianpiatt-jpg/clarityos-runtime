#!/usr/bin/env bash
# Card A10 — asset manifest drift gate.
#
# Regenerates web/assets/v0.2/manifest.json and asserts the
# committed snapshot is byte-identical to a fresh generation.
# Fails non-zero if:
#   * an asset under web/assets/v0.2/ changed but the manifest
#     wasn't regenerated, or
#   * the manifest was hand-edited away from a regenerable shape.
#
# Suggested CI wiring (later):
#
#   - name: Asset manifest drift gate
#     run: bash scripts/check_asset_manifest.sh
#
# The generator (web/scripts/gen-asset-manifest.mjs) is pure Node
# (crypto + fs) and has zero npm dependencies, so this gate runs
# without first installing node_modules.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="${REPO_ROOT}/web"
MANIFEST_REL="assets/v0.2/manifest.json"
MANIFEST_PATH="${WEB_DIR}/${MANIFEST_REL}"

cd "${WEB_DIR}"

node scripts/gen-asset-manifest.mjs

# git diff --exit-code is the load-bearing line: exits 0 iff the
# regenerated file matches the committed one byte-for-byte.
if ! git diff --exit-code -- "${MANIFEST_REL}"; then
  echo ""
  echo "[fail] asset manifest is stale."
  echo "       run \`npm run assets:gen\` in web/, then commit ${MANIFEST_PATH}."
  exit 1
fi

echo "[ok] asset manifest drift gate passed"
