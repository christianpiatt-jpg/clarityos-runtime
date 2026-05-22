#!/usr/bin/env bash
# PASS — Task Card 7: drift detection for the Python-side schema bridge.
#
# Re-runs the Python model generator and fails if the freshly-generated
# ``web_surface_models.py`` differs from the committed one. Catches
# the "edited the TS contract / regenerated the schema / forgot to
# regenerate the Python models" path.
#
# Suggested CI wiring (later):
#
#   - name: Verify v0.2.0 Python models are in sync with schema
#     run: bash scripts/check_web_surface_models.sh
#
# Exit codes:
#   0 — committed models match the generator output
#   1 — drift detected (or generator failed)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

bash "${REPO_ROOT}/scripts/gen_web_surface_models.sh"

if git -C "${REPO_ROOT}" diff --exit-code web_surface_models.py; then
    echo "✓ web_surface_models.py is up to date with the schema"
else
    echo "::error::web_surface_models.py is stale — re-run \`bash scripts/gen_web_surface_models.sh\` and commit the result"
    exit 1
fi
