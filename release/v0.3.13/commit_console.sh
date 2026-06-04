#!/usr/bin/env bash
# Deterministic console landing: apply the 3 surface patches on top of the
# backend-committed tree, gate each on its vitest suite, and commit per surface
# (no cross-surface mixing, no backend files). Run AFTER commit_backend.sh.
#   PHONE_MODE=C2 (default): land phone code + scaffolds; verify externally
#                            (web's vitest binary rooted at phone, node env).
#   PHONE_MODE=C1          : add vitest to phone, wire a node-env config, run
#                            48 scaffolds in-package.
set -euo pipefail
D="$(cd "$(dirname "$0")" && pwd)"; R="$(cd "$D/.." && pwd)"; cd "$R"
PHONE_MODE="${PHONE_MODE:-C2}"
TR="Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git diff --quiet HEAD || { echo "ABORT: tracked changes present"; exit 1; }

# ---- WEB ----
git apply "$D/console_web_landing.patch"
npm --prefix web run test                       # vitest gate (web)
git add -A -- web/
git commit -q -m "feat: operator console web" -m "$TR"

# ---- DESKTOP ----
git apply "$D/console_desktop_landing.patch"
npm --prefix desktop run test                   # vitest gate (desktop)
git add -A -- desktop/
git commit -q -m "feat: operator console desktop" -m "$TR"

# ---- PHONE (mode-specific) ----
git apply "$D/console_phone_landing.patch"
if [ "$PHONE_MODE" = "C1" ]; then
  npm --prefix phone install -D vitest          # add the runner (needs network)
  cat > phone/vitest.config.ts <<'CFG'
import { defineConfig } from "vitest/config";
// Node-env runner for the pure operator-lib scaffolds (no React Native runtime).
export default defineConfig({ test: { environment: "node", include: ["lib/__tests__/**/*.test.ts"] } });
CFG
  ( cd phone && node_modules/.bin/vitest run )   # in-package gate (48 scaffolds)
  git add -A -- phone/
  git commit -q -m "feat: operator console phone (C1: in-package vitest runner)" -m "$TR"
else
  ( cd phone && "$R/web/node_modules/.bin/vitest" run lib/__tests__ --environment node )  # external gate
  git add -A -- phone/
  git commit -q -m "chore: operator console phone scaffolds (C2: verified externally)" -m "$TR"
fi

# ---- Guards ----
N=$([ "$PHONE_MODE" = "C1" ] && echo 3 || echo 3)
for f in $(git diff --name-only HEAD~3 HEAD); do
  case "$f" in web/*|desktop/*|phone/*) : ;; *) echo "ERROR: non-console file in console commits: $f"; exit 1;; esac
done
echo "OK: 3 console commits (PHONE_MODE=$PHONE_MODE); surface-scoped; no backend files."
git log --oneline -3
