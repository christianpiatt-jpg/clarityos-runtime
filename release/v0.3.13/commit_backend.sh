#!/usr/bin/env bash
# Deterministic backend landing: 3 isolated commits, then gate on the full suite
# (revert all 3 if not green). Commit-then-gate avoids the untracked-file residue
# that "apply-all → reset → re-apply" leaves behind. Run from a CLEAN checkout of
# HEAD (2651c78) on a landing branch, with this landing_v0.3.13/ directory +
# auth_magiclink_landing.patch present at repo root. Commits stage ONLY each
# patch's target files — never the landing/ inputs, never any console file.
set -euo pipefail
D="$(cd "$(dirname "$0")" && pwd)"   # landing_v0.3.13/
R="$(cd "$D/.." && pwd)"             # repo root
cd "$R"
AUTH="$R/auth_magiclink_landing.patch"
git diff --quiet HEAD || { echo "ABORT: tracked changes present (need a clean HEAD)"; exit 1; }

C1="app.py tests/conftest.py"
C2="tests/test_runtime_inv_http.py tests/test_fix_p1_billing_surface_hardening.py"
C3="app.py tests/conftest.py auth_magiclink.py tests/test_auth_magiclink.py \
    harmonizer.py orientation_contracts.py tests/test_harmonizer.py \
    compass_elins_bridge.py tests/test_compass_elins_bridge.py tests/test_phase6.py \
    phase7_endpoint.py tests/test_phase10_11_endpoint.py"
TR="Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
abort_revert(){ echo "$1"; git reset --hard HEAD~3 >/dev/null 2>&1 || true; exit 1; }

# ---- 3 isolated commits (incremental apply + explicit staging) ----
git apply "$D/phase7_mount.patch"
git add -- $C1
git commit -q -m "feat: mount operator engine surface (phase7–9)" -m "$TR"

git apply "$D/billing_fix.patch"
git add -- $C2
git commit -q -m "fix: billing grace_period mapping (C1)" -m "$TR"

git apply "$AUTH" "$D/peripheral_harmonizer.patch" "$D/peripheral_compass_bridge.patch" \
          "$D/peripheral_phase6_test.patch" "$D/phase10_11_surface.patch"
git add -- $C3
git commit -q -m "feat: auth magic-link + peripheral modules + phase10/11 surface" -m "$TR"

# ---- Gate AFTER committing; revert all 3 if not green ----
echo "[gate] full backend suite on the 3-commit tree…"
CLARITYOS_BACKEND=memory python -m pytest tests/ -q -p no:cacheprovider \
  || abort_revert "GATE FAILED — reverted the 3 commits."

# ---- Guards ----
git diff --name-only HEAD~3 HEAD | grep -qE '^(web|desktop|phone)/' \
  && abort_revert "ERROR: console files in backend commits — reverted." || true
git diff --name-only HEAD~3 HEAD | grep -qE '^landing_v0\.3\.13/|auth_magiclink_landing\.patch' \
  && abort_revert "ERROR: landing inputs in commits — reverted." || true
[ -z "$(git status --porcelain --untracked-files=no)" ] \
  || abort_revert "ERROR: tracked changes left uncommitted — reverted."
echo "OK: 3 backend commits; gate green; no console/landing leakage; tree clean."
git log --oneline -3
