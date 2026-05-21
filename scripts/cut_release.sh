#!/usr/bin/env bash
# PASS-6 Phase D — Release-cutting helper.
#
# Wraps the four-step release process documented in
# README.md::"Cutting a release". Use this to reduce the chance of
# tag/file drift during a release cut.
#
# Usage:
#     bash scripts/cut_release.sh v0.1.1
#
# What this script does:
#   1. Validates the supplied version against semver.
#   2. Asserts the working tree is clean (no uncommitted changes).
#   3. Updates VERSION to the new value (in a working-tree change you
#      review + commit yourself).
#   4. Reminds you to update CHANGELOG.md and create the release-notes
#      source.
#   5. Runs the release-integrity test suite locally.
#   6. Optionally creates + pushes the tag.
#
# This script never pushes without confirmation.
set -euo pipefail

usage() {
    echo "usage: $0 <version>"
    echo ""
    echo "  <version>   Release version in semver form with leading v"
    echo "              (e.g. v0.1.0, v0.2.0-rc1, v1.0.0)"
    exit 2
}

if [ "$#" -ne 1 ]; then
    usage
fi

NEW_VERSION="$1"

# --- 1. Validate semver shape ------------------------------------------------
if ! [[ "$NEW_VERSION" =~ ^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$ ]]; then
    echo "::error::version '$NEW_VERSION' does not match semver"
    usage
fi

# --- 2. Working tree is clean ------------------------------------------------
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    echo "::error::working tree is dirty — commit or stash before cutting a release"
    git status --short
    exit 1
fi

# --- 3. Update VERSION -------------------------------------------------------
CURRENT_VERSION="$(cat VERSION | tr -d '[:space:]')"
if [ "$CURRENT_VERSION" = "$NEW_VERSION" ]; then
    echo "VERSION is already $NEW_VERSION — nothing to update."
else
    echo "$NEW_VERSION" > VERSION
    echo "Updated VERSION: $CURRENT_VERSION -> $NEW_VERSION"
fi

# --- 4. Sanity check the documentation surface -------------------------------
if ! grep -qE "^#+\s.*$NEW_VERSION\b" CHANGELOG.md; then
    echo ""
    echo "============================================================"
    echo "  ACTION REQUIRED — CHANGELOG.md needs a section for"
    echo "  $NEW_VERSION. Open CHANGELOG.md and add a new entry"
    echo "  before continuing. The release-integrity test"
    echo "  (tests/test_release_integrity.py) will fail otherwise."
    echo "============================================================"
fi

NOTES_PATH="docs/release_notes/${NEW_VERSION}.md"
if [ ! -f "$NOTES_PATH" ]; then
    echo ""
    echo "============================================================"
    echo "  ACTION REQUIRED — Create release notes at:"
    echo "    $NOTES_PATH"
    echo "  The release workflow reads this file as the GitHub"
    echo "  Release body. Use docs/release_notes/v0.1.0.md as a"
    echo "  template."
    echo "============================================================"
fi

# --- 5. Run the release-integrity tests --------------------------------------
echo ""
echo "============================================================"
echo "  Running release-integrity tests..."
echo "============================================================"
python -m pytest tests/test_release_integrity.py -q

# --- 6. Run the full CI gate -------------------------------------------------
echo ""
echo "============================================================"
echo "  Running CI gate (runtime_spine + privacy_surface + determinism_surface)..."
echo "============================================================"
python -m pytest \
    -m "runtime_spine or privacy_surface or determinism_surface" \
    -q --maxfail=1

# --- 7. Final reminder -------------------------------------------------------
echo ""
echo "============================================================"
echo "  Local checks green. To finish the release:"
echo ""
echo "    git add VERSION CHANGELOG.md docs/release_notes/${NEW_VERSION}.md"
echo "    git commit -m \"release: ${NEW_VERSION}\""
echo "    git tag ${NEW_VERSION}"
echo "    git push origin main ${NEW_VERSION}"
echo ""
echo "  The release.yml workflow runs on the tag push."
echo "============================================================"
