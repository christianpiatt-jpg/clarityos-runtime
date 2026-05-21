#!/usr/bin/env bash
# scripts/run_acceptance.sh
#
# Operator-invoked orchestration for a single acceptance harness run.
# Generates a deterministic run-id, invokes the Node runner via ts-node,
# and captures shell stdout/stderr alongside the runner's report.json
# and report.md under tests/acceptance/reports/<run-id>/.
#
# This script is materialized in write-only mode. Claude does NOT
# execute it — operator runs manually:
#
#     bash scripts/run_acceptance.sh fast
#     bash scripts/run_acceptance.sh full
#
# Output layout:
#     tests/acceptance/reports/<run-id>/
#       ├── stdout.log     (captured by this script)
#       ├── stderr.log     (captured by this script)
#       ├── report.json    (written by tests/acceptance/runner.ts)
#       └── report.md      (written by tests/acceptance/runner.ts)
#
# Output is intentionally placed under tests/acceptance/reports/ rather
# than a top-level runs/ directory to honour Global Constraint 3 — no
# new top-level directories are created.
#
# Cross-platform notes:
#   - Linux/macOS: invoke directly (`bash scripts/run_acceptance.sh fast`).
#   - Windows: run inside Git Bash or WSL; cmd.exe / PowerShell are
#     not supported by this script.

set -euo pipefail

# ============================================================
# DRY RUN EXAMPLE — Phase 3A documentation block (NOT EXECUTED)
# ============================================================
# The block below documents what this script would invoke when
# the operator runs it. It is intentionally inside a comment so
# nothing executes during materialization or sourcing.
#
#   # Fast mode (scenarios 01 + 04, ~5–10 minutes wall):
#   bash scripts/run_acceptance.sh fast
#
#   # Full mode (scenarios 01–05, ~20–40 minutes wall):
#   bash scripts/run_acceptance.sh full
#
# What this script would do, step by step:
#   1. Generate run-id   → run-<UTC YYYYmmddTHHMMSSZ>-<4-hex>
#   2. mkdir -p           tests/acceptance/reports/<run-id>/
#   3. Invoke runner      npx ts-node tests/acceptance/runner.ts \
#                            --mode=<mode> --run-id=<run-id>
#   4. tee stdout/stderr  tests/acceptance/reports/<run-id>/{stdout,stderr}.log
#   5. Print exit code:   0 (pass) | 1 (fail) | 2 (fatal) | 64 (usage)
#   6. Print next step:   python tests/acceptance/post_run_ingest.py <run-dir>
#
# A sample report.json + report.md are at:
#   tests/acceptance/expected_outputs/sample_report.json
#   tests/acceptance/expected_outputs/sample_report.md
# ============================================================

# --- argument parsing ---
MODE="${1:-fast}"
case "$MODE" in
  fast|full) ;;
  *)
    echo "usage: $0 [fast|full]" >&2
    exit 64
    ;;
esac

# --- run-id generation ---
# Format: run-<UTC YYYYmmddTHHMMSSZ>-<4-char hex suffix>
TS="$(date -u +%Y%m%dT%H%M%SZ)"
SUFFIX="$(printf '%04x' $((RANDOM % 65536)))"
RUN_ID="run-${TS}-${SUFFIX}"

# --- output directory ---
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_DIR="${REPO_ROOT}/tests/acceptance/reports/${RUN_ID}"
mkdir -p "${OUTPUT_DIR}"

echo "[run_acceptance] mode=${MODE}"
echo "[run_acceptance] run_id=${RUN_ID}"
echo "[run_acceptance] output_dir=${OUTPUT_DIR}"
echo "[run_acceptance] runner=tests/acceptance/runner.ts"

# --- runner invocation ---
# Captures both streams into the run dir while preserving live console output.
EXIT=0
npx ts-node "${REPO_ROOT}/tests/acceptance/runner.ts" \
  --mode="${MODE}" \
  --run-id="${RUN_ID}" \
  > >(tee "${OUTPUT_DIR}/stdout.log") \
  2> >(tee "${OUTPUT_DIR}/stderr.log" >&2) \
  || EXIT=$?

echo
echo "[run_acceptance] runner exit code: ${EXIT}"
echo "[run_acceptance] artifacts:"
echo "  ${OUTPUT_DIR}/report.json"
echo "  ${OUTPUT_DIR}/report.md"
echo "  ${OUTPUT_DIR}/stdout.log"
echo "  ${OUTPUT_DIR}/stderr.log"
echo
echo "[run_acceptance] next step:"
echo "  python tests/acceptance/post_run_ingest.py ${OUTPUT_DIR}"

exit "$EXIT"
