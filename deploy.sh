#!/usr/bin/env bash
# ============================================================
#  ClarityOS Cloud  -  single-command Cloud Run deploy (POSIX)
#
#  Mirror of deploy.bat for Git Bash / WSL / Linux / macOS.
#  See deploy.bat for the rationale on the BUILD_VERSION stamp.
# ============================================================
set -euo pipefail

cd "$(dirname "$0")"

SERVICE="clarity-engine"
REGION="us-east4"

BUILD_TAG="$(date -u +%Y%m%d%H%M%S)"
echo "$BUILD_TAG" > BUILD_VERSION

cat <<EOF

================================================================
  Deploying $SERVICE to Cloud Run ($REGION)
  Build tag: $BUILD_TAG
  Source:    $PWD
================================================================

EOF

gcloud run deploy "$SERVICE" \
    --source . \
    --region "$REGION" \
    --platform managed \
    --allow-unauthenticated \
    --port 8080

cat <<EOF

================================================================
  Deploy complete (build tag $BUILD_TAG).
  Verify:
    gcloud run services describe $SERVICE --region $REGION \\
      --format='value(status.latestReadyRevisionName,status.url)'
================================================================
EOF
