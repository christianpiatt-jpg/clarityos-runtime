#!/usr/bin/env bash
# spa_route_objects_v1.sh — SPA deep-link objects for a classic EXTERNAL LB.
#
# COW-1 · 2026-08-24 · READ-ONLY PROPOSAL. K3 applies under CT-1 authorship.
# Substitute for the custom-error-response fix, which is unavailable:
# custom error responses require loadBalancingScheme=EXTERNAL_MANAGED and
# this map is classic EXTERNAL. Measured by K3, HTTP 400 twice, map verified
# byte-identical afterward.
#
# WHY THIS SCRIPT AND NOT A cp LOOP
# ---------------------------------
# Two mechanisms make the obvious loop fail SILENTLY. Both are handled here.
#
#   1. gsutil cp INFERS A DIRECTORY.
#      Once gs://B/operator/console exists, `gsutil cp index.html gs://B/operator`
#      writes gs://B/operator/index.html — the object named `operator` is never
#      created and /operator still 404s, with a zero exit code.
#      6 of the 52 route objects are prefixes of other route objects:
#          founder(14)  operator(9)  operator/el_ins(5)
#          founder/acceptance(3)  founder/identity(2)  session(1)
#      With `-m` the creation order is nondeterministic, so this is a RACE.
#      -> This script creates SHALLOWEST-FIRST, SEQUENTIALLY, no -m,
#         and then VERIFIES every object's actual name (step 4).
#
#   2. THE DEPLOY IS `gsutil rsync -r` WITH NO `-d`.
#      (DEPLOY_SESSION_HANDOFF_staged_2026-08-21_v1.md:91,103)
#      So the route objects are NOT deleted on deploy — they SURVIVE, stale,
#      pointing at old hashed assets which also survive (no -d prunes them).
#      The deep link therefore does not break after a deploy. It returns 200
#      and silently serves the PREVIOUS BUILD, indefinitely, with no error
#      anywhere. That is worse than a 404 and it is invisible.
#      -> `refresh` MUST run after every rsync. Use `deploy` (step 5), which
#         does both, rather than calling rsync directly.
#
# The parameterized route /founder/operator/:user_id cannot be covered by an
# object. It keeps today's behavior: shell body, 404 status, SPA renders.
# Stated, accepted, unchanged by this script.

set -euo pipefail

BUCKET="${BUCKET:-clarityos-web-founding-os}"
APP_TSX="${APP_TSX:-web/src/App.tsx}"
DIST="${DIST:-web/dist}"

# v1.1 — K3, 2026-08-24. SOURCE OF TRUTH IS THE LIVE BUCKET, not web/dist.
# v1.0 copied from the local build, which can be stale — a script whose whole
# purpose is preventing silent staleness had the stale thing as its input.
# The live object is what users are served; that is what the route objects
# must mirror. Set SRC=local to override for an offline dry run.
SRC="${SRC:-bucket}"
_stage_index() {
  if [ "$SRC" = "local" ]; then
    [ -f "${DIST}/index.html" ] || { echo "FATAL: ${DIST}/index.html not found" >&2; exit 1; }
    INDEX="${DIST}/index.html"
  else
    INDEX="$(mktemp)"
    gsutil cp "gs://${BUCKET}/index.html" "$INDEX" >/dev/null 2>&1 \
      || { echo "FATAL: cannot read gs://${BUCKET}/index.html" >&2; exit 1; }
  fi
}

# ---------------------------------------------------------------------------
# 1 · ROUTES — generated from App.tsx, never hand-maintained.
#     Drops: "/" (already served by mainPageSuffix=index.html)
#            "*" (wildcard, cannot be an object)
#            any path containing ":" (parameterized)
# ---------------------------------------------------------------------------
routes() {
  [ -f "$APP_TSX" ] || { echo "FATAL: $APP_TSX not found" >&2; exit 1; }
  grep -o 'path="[^"]*"' "$APP_TSX" \
    | sed 's/path="//; s/"$//' \
    | grep -v '^\*$' \
    | grep -v ':' \
    | grep -v '^/$' \
    | sed 's|^/||' \
    | sort -u
}

# shallowest first — this ordering is the whole defense against mechanism 1
routes_ordered() { routes | awk '{print gsub(/\//,"/"), $0}' | sort -k1,1n -k2,2 | cut -d' ' -f2-; }

# ---------------------------------------------------------------------------
# 2 · CREATE
# ---------------------------------------------------------------------------
create() {
  _stage_index
  local n=0
  while read -r r; do
    [ -z "$r" ] && continue
    gsutil -h "Content-Type:text/html" -h "Cache-Control:no-cache, max-age=0" \
           cp "$INDEX" "gs://${BUCKET}/${r}"
    n=$((n+1))
  done < <(routes_ordered)
  echo "created/updated ${n} route objects"
  invalidate
}

# ---------------------------------------------------------------------------
# 2b · INVALIDATE — MECHANISM 3, measured by K3 2026-08-24.
#
# The backend bucket runs negativeCaching=true with serveWhileStale=86400.
# EVERY route object this script creates had a pre-existing negative cache
# entry, because every one of them legitimately 404'd before it existed.
# K3 measured /cockpit still serving a 41-minute-old negative AFTER create,
# carrying index.html's generation rather than its own — while /operator
# (Age: 0) served correctly. The negatives are per-path; a partial clear
# looks like success on whichever path you happen to curl.
#
# So this is NOT a one-time cleanup. Any route added later reopens the same
# hole. create/refresh must always end here.
#
# ★ Verify by GENERATION, not status. A 200 cannot distinguish "invalidated"
#   from "never cached". A 404 carrying index.html's generation is decisive.
# ---------------------------------------------------------------------------
invalidate() {
  gcloud compute url-maps invalidate-cdn-cache "${URL_MAP:-clarityos-web-map}" \
    --path "/*" --global --async \
    || echo "WARN: CDN invalidate failed — deep links may serve stale negatives for up to 24h" >&2
}

# ---------------------------------------------------------------------------
# 3 · REFRESH — re-copy index.html over every route object. Run AFTER rsync.
# ---------------------------------------------------------------------------
refresh() { create; }

# ---------------------------------------------------------------------------
# 4 · VERIFY — does an object with EXACTLY this name exist?
#     `gsutil stat` on the exact name is the only check that catches
#     mechanism 1. A curl on three routes does not: none of the three
#     classes K3 proposed (flat / nested / unknown) is "a route that is
#     also a prefix of another route", which is the only class at risk.
# ---------------------------------------------------------------------------
# v1.1 — K3, 2026-08-24. BATCHED. v1.0 spawned gsutil once per object; at
# ~6s/spawn on a Windows host that is ~104 spawns / ~15 min and it ALWAYS
# dies in a 300s foreground window. Verify is the step that catches
# mechanism 1, so verify being the step that cannot finish was exactly
# backwards. One `gsutil stat` call takes all URLs at once.
#
# Also v1.1: verify no longer shares a failure domain with create. v1.0 ran
# `create; verify` — a verify killed by timeout is indistinguishable from a
# failed create, and a runner could roll back a fix that worked. verify now
# reports its own exit distinctly and create does not imply it.
verify() {
  local urls=() r
  while read -r r; do [ -z "$r" ] && continue; urls+=("gs://${BUCKET}/${r}"); done < <(routes_ordered)
  local n="${#urls[@]}" bad=0 present

  present="$(gsutil stat "${urls[@]}" 2>/dev/null | grep -c '^gs://' || true)"
  if [ "$present" -ne "$n" ]; then
    echo "MISSING: ${present}/${n} route objects present — listing gaps:"
    gsutil ls "gs://${BUCKET}/**" 2>/dev/null | sed "s|gs://${BUCKET}/||" | sort > /tmp/_have.$$
    routes_ordered | sort | comm -23 - /tmp/_have.$$ | sed 's/^/  MISSING: /'
    rm -f /tmp/_have.$$
    bad=$((bad + n - present))
  fi

  # directory-inference tell — one batched call, prefix routes only
  local kids=() o
  while read -r o; do
    [ -z "$o" ] && continue
    routes_ordered | grep -q "^${o}/" && kids+=("gs://${BUCKET}/${o}/index.html")
  done < <(routes_ordered)
  if [ "${#kids[@]}" -gt 0 ]; then
    local arts
    arts="$(gsutil stat "${kids[@]}" 2>/dev/null | grep '^gs://' || true)"
    if [ -n "$arts" ]; then
      echo "DIRECTORY-INFERENCE ARTIFACTS — these routes were written as folders:"
      echo "$arts" | sed 's/^/  /'
      bad=$((bad + $(echo "$arts" | wc -l)))
    fi
  fi

  echo "verified ${n} routes, ${bad} problem(s)"
  [ "$bad" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 5 · DEPLOY — the only supported way to ship the SPA once this fix is live.
# ---------------------------------------------------------------------------
deploy() {
  gsutil rsync -r "$DIST" "gs://${BUCKET}"
  refresh
  verify
  echo "NOTE: CDN defaultTtl 3600 — invalidate if serving stale."
}

# ---------------------------------------------------------------------------
# 6 · ROLLBACK
# ---------------------------------------------------------------------------
rollback() {
  routes_ordered | sed "s|^|gs://${BUCKET}/|" | gsutil -m rm -I
  echo "removed route objects; deep links return to shell+404 behavior"
}

case "${1:-}" in
  list)     routes_ordered ;;
  create)   create; verify ;;
  refresh)  refresh; verify ;;
  verify)   verify ;;
  deploy)   deploy ;;
  rollback) rollback ;;
  *) echo "usage: $0 {list|create|refresh|verify|deploy|rollback}"; exit 2 ;;
esac
