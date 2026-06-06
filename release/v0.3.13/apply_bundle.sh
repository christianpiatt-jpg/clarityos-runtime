#!/usr/bin/env bash
# Apply the v0.3.13 backend landing bundle in dependency order, from repo root.
# Usage: bash landing_v0.3.13/apply_bundle.sh   (run on a clean HEAD checkout)
set -e
D="$(cd "$(dirname "$0")" && pwd)"   # landing_v0.3.13/
R="$(cd "$D/.." && pwd)"             # repo root
cd "$R"
git apply "$D/phase7_mount.patch"            # 1 mount Phase 7-9 surface
git apply "$D/billing_fix.patch"             # 2 fix 2 stale grace_period tests
git apply "$R/auth_magiclink_landing.patch"  # 3 auth magic-link
git apply "$D/peripheral_harmonizer.patch"   # 4a harmonizer + orientation_contracts
git apply "$D/peripheral_compass_bridge.patch" # 4b compass bridge
git apply "$D/peripheral_phase6_test.patch"  # 4c phase6 test
git apply "$D/phase10_11_surface.patch"      # 5 surface Phase 10/11
echo "bundle applied (7 patches) — run: CLARITYOS_BACKEND=memory python -m pytest tests/ -q"
