#!/usr/bin/env bash
# PASS-6 Phase C — Local CI-gate driver.
#
# Mirrors what .github/workflows/ci.yml runs on every PR. Use this
# before pushing to surface failures locally instead of in CI.
#
# Usage:
#     bash scripts/run_ci_gates.sh              # all three suites
#     bash scripts/run_ci_gates.sh spine        # runtime_spine only
#     bash scripts/run_ci_gates.sh privacy      # privacy_surface only
#     bash scripts/run_ci_gates.sh determinism  # determinism_surface only
#     bash scripts/run_ci_gates.sh union        # the CI gate union
set -euo pipefail

# Test-only env defaults — mirrors tests/conftest.py and ci.yml. None
# of these are real secrets.
: "${CLARITYOS_VAULT_SECRET:=local-throwaway-vault-secret-DO-NOT-USE-IN-PROD}"
: "${CLARITYOS_BACKEND:=memory}"
: "${CLARITYOS_BILLING_MODE:=mock}"
: "${CLARITYOS_MOCK_AUTO_CONFIRM:=1}"
: "${CLARITYOS_DISABLE_MACRO_SCHEDULER:=1}"
: "${CLARITYOS_LOG_LEVEL:=WARNING}"
export CLARITYOS_VAULT_SECRET CLARITYOS_BACKEND CLARITYOS_BILLING_MODE
export CLARITYOS_MOCK_AUTO_CONFIRM CLARITYOS_DISABLE_MACRO_SCHEDULER
export CLARITYOS_LOG_LEVEL

# Pick the gate to run. Default to all three (matches CI default).
GATE="${1:-all}"

run_marker() {
    local marker="$1"
    echo ""
    echo "============================================================"
    echo "  Running gate: $marker"
    echo "============================================================"
    python -m pytest -m "$marker" -q --maxfail=1
}

case "$GATE" in
    spine)
        run_marker "runtime_spine"
        ;;
    privacy)
        run_marker "privacy_surface"
        ;;
    determinism)
        run_marker "determinism_surface"
        ;;
    union)
        run_marker "runtime_spine or privacy_surface or determinism_surface"
        ;;
    all)
        run_marker "runtime_spine"
        run_marker "privacy_surface"
        run_marker "determinism_surface"
        ;;
    *)
        echo "unknown gate: $GATE"
        echo "usage: $0 [spine|privacy|determinism|union|all]"
        exit 2
        ;;
esac

echo ""
echo "============================================================"
echo "  All requested gates green."
echo "============================================================"
