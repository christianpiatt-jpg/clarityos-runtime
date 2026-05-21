"""
PASS-6 Phase D — Release-engineering integrity tests.

These tests gate the release-engineering surface itself, not the
runtime. They fail loudly if any of the following drift:

  * ``VERSION``                                    — exists, semver-shaped.
  * ``CHANGELOG.md``                               — carries an entry
                                                     for the current
                                                     ``VERSION``.
  * ``docs/release_notes/${VERSION}.md``           — exists.
  * ``.github/workflows/release.yml``              — references
                                                     ``VERSION`` and
                                                     re-runs the CI
                                                     gate.
  * Three CI markers (``runtime_spine`` /
    ``privacy_surface`` /
    ``determinism_surface``)                       — each resolves to a
                                                     positive test
                                                     count (the gate is
                                                     not empty).
  * Release-time logging                           — running the
                                                     redaction
                                                     invariant tests
                                                     emits no
                                                     PLAINTEXT-mode
                                                     warning and no
                                                     forbidden field
                                                     leak.

Each test asserts a single integrity check directly. None depend on
runtime behaviour beyond the locked invariants documented in
``docs/invariants.md``.
"""
from __future__ import annotations

import logging
import re
import subprocess
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent

# Semantic version regex per https://semver.org/ — accepts ``vMAJOR.MINOR.PATCH``
# and optional ``-prerelease`` / ``+build`` suffixes. Required leading ``v``
# matches the project tagging convention (``v0.1.0`` etc.).
_SEMVER_RE = re.compile(
    r"^v"
    r"(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
    r"$"
)


def _read_version() -> str:
    """Return the trimmed VERSION value. Test helper, not a runtime
    surface — runtime modules do not read VERSION directly."""
    return (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()


# ===========================================================================
# D6.1 — VERSION file
# ===========================================================================
class TestVersionFile:
    def test_version_file_exists(self):
        assert (REPO_ROOT / "VERSION").is_file(), (
            "VERSION file missing at repo root"
        )

    def test_version_file_is_not_empty(self):
        v = _read_version()
        assert v, "VERSION file is empty"

    def test_version_matches_semver(self):
        v = _read_version()
        m = _SEMVER_RE.match(v)
        assert m is not None, (
            f"VERSION {v!r} does not match the semver regex "
            f"(expected ``vMAJOR.MINOR.PATCH`` with optional "
            f"``-prerelease`` / ``+build``)"
        )

    def test_version_file_is_single_line(self):
        raw = (REPO_ROOT / "VERSION").read_text(encoding="utf-8")
        # Allow one trailing newline; reject any embedded newlines.
        stripped = raw.rstrip("\n")
        assert "\n" not in stripped, (
            "VERSION file must be a single line — multi-line values "
            "trip the release workflow's ``cat VERSION | tr -d '[:space:]'`` "
            "check."
        )


# ===========================================================================
# D6.2 — CHANGELOG.md carries an entry for the current VERSION
# ===========================================================================
class TestChangelog:
    def test_changelog_exists(self):
        assert (REPO_ROOT / "CHANGELOG.md").is_file()

    def test_changelog_has_entry_for_current_version(self):
        """The release workflow generates GitHub-Release prose, but
        the human-readable CHANGELOG must still carry a section for
        the current VERSION. Format check is intentionally loose:
        any heading-style line containing the version is acceptable."""
        v = _read_version()
        text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        # Match common forms: ``## [v0.1.0] — title``, ``## v0.1.0``,
        # ``# v0.1.0``, etc.
        pattern = re.compile(
            rf"^#+\s.*\b{re.escape(v)}\b",
            re.MULTILINE,
        )
        assert pattern.search(text), (
            f"CHANGELOG.md has no heading containing VERSION {v!r}. "
            f"Add a new section before tagging."
        )

    def test_changelog_uses_markdown_headings(self):
        """The changelog must use ATX-style markdown headings (``# ...``)
        so the release workflow's body-path consumer renders it
        correctly on the GitHub Release page."""
        text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        # At least one ATX heading present.
        assert re.search(r"^#\s", text, re.MULTILINE)


# ===========================================================================
# D6.3 — Release notes source exists for the current VERSION
# ===========================================================================
class TestReleaseNotes:
    def test_release_notes_directory_exists(self):
        assert (REPO_ROOT / "docs" / "release_notes").is_dir()

    def test_release_notes_file_exists_for_current_version(self):
        v = _read_version()
        path = REPO_ROOT / "docs" / "release_notes" / f"{v}.md"
        assert path.is_file(), (
            f"Release notes source missing: {path.relative_to(REPO_ROOT)}. "
            f"The release workflow reads this file as the GitHub Release body."
        )

    def test_release_notes_mention_current_version(self):
        v = _read_version()
        path = REPO_ROOT / "docs" / "release_notes" / f"{v}.md"
        text = path.read_text(encoding="utf-8")
        assert v in text, (
            f"Release notes for {v} do not mention the version string"
        )


# ===========================================================================
# D6.4 — release.yml shape + VERSION reference
# ===========================================================================
class TestReleaseWorkflow:
    _PATH = REPO_ROOT / ".github" / "workflows" / "release.yml"

    def test_release_workflow_exists(self):
        assert self._PATH.is_file()

    def test_release_workflow_triggered_by_version_tags(self):
        text = self._PATH.read_text(encoding="utf-8")
        # ``on.push.tags`` block with a ``v*`` pattern.
        assert "tags:" in text
        assert '"v*"' in text or "'v*'" in text or "- v*" in text

    def test_release_workflow_references_version_file(self):
        """The workflow must consult VERSION at runtime — otherwise a
        forgotten VERSION bump would still produce a release."""
        text = self._PATH.read_text(encoding="utf-8")
        assert "cat VERSION" in text or "Verify VERSION" in text, (
            ".github/workflows/release.yml does not appear to read "
            "the VERSION file. Tag/file drift could ship a misnamed release."
        )

    def test_release_workflow_runs_ci_gate(self):
        text = self._PATH.read_text(encoding="utf-8")
        # The same marker selection ci.yml uses.
        assert "runtime_spine" in text
        assert "privacy_surface" in text
        assert "determinism_surface" in text

    def test_release_workflow_publishes_github_release(self):
        text = self._PATH.read_text(encoding="utf-8")
        # The publish step uses action-gh-release (or an equivalent
        # named publish step). Either signature is acceptable.
        assert (
            "softprops/action-gh-release" in text
            or "actions/create-release" in text
            or "Publish GitHub Release" in text
        ), (
            ".github/workflows/release.yml does not publish a GitHub Release"
        )

    def test_release_workflow_reads_release_notes_for_version(self):
        text = self._PATH.read_text(encoding="utf-8")
        # body_path should reference docs/release_notes/<TAG>.md so
        # the GitHub Release body is the release-notes file.
        assert "docs/release_notes" in text


# ===========================================================================
# D6.5 — CI gate selectors resolve to positive test counts
# ===========================================================================
def _collected_count(marker_expr: str) -> int:
    """Run pytest --collect-only -q under ``-m <expr>`` and parse the
    summary line for the collected count. Returns 0 if nothing was
    collected."""
    cmd = [
        sys.executable, "-m", "pytest",
        "-m", marker_expr,
        "--collect-only", "-q",
    ]
    result = subprocess.run(
        cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    # pytest emits e.g. ``516/8105 tests collected (7589 deselected) in 1.88s``
    m = re.search(
        r"(\d+)\s*(?:/\s*\d+)?\s*tests collected",
        result.stdout + result.stderr,
    )
    return int(m.group(1)) if m else 0


class TestCiGateNonEmpty:
    """The release workflow re-runs the CI gate. The marker selectors
    must each resolve to a positive test count — an empty gate is a
    silent pass that would hide a regression."""

    def test_runtime_spine_selector_non_empty(self):
        n = _collected_count("runtime_spine")
        assert n > 0, "runtime_spine marker collected 0 tests"

    def test_privacy_surface_selector_non_empty(self):
        n = _collected_count("privacy_surface")
        assert n > 0, "privacy_surface marker collected 0 tests"

    def test_determinism_surface_selector_non_empty(self):
        n = _collected_count("determinism_surface")
        assert n > 0, "determinism_surface marker collected 0 tests"

    def test_union_selector_non_empty_and_at_least_spine_size(self):
        """The union must include at least every runtime_spine test —
        a union smaller than the spine would indicate the marker
        expression has been mistyped in CI."""
        spine_n = _collected_count("runtime_spine")
        union_n = _collected_count(
            "runtime_spine or privacy_surface or determinism_surface",
        )
        assert union_n >= spine_n, (
            f"CI gate union ({union_n}) is smaller than runtime_spine "
            f"({spine_n}) — marker expression likely broken"
        )


# ===========================================================================
# D6.6 — Release-time logging discipline
# ===========================================================================
class TestNoForbiddenWarningsAtRelease:
    """When the release workflow runs the CI gate, the redaction and
    plaintext-vault contracts must hold. We verify the contract by
    importing the spine modules and exercising the documented entry
    points; no PLAINTEXT warning fires under the default test env
    (which leaves CLARITYOS_VAULT_PLAINTEXT unset)."""

    def test_no_plaintext_warning_under_default_release_env(
        self, reset_stores, monkeypatch, caplog,
    ):
        monkeypatch.delenv("CLARITYOS_VAULT_PLAINTEXT", raising=False)
        import memory_vault
        memory_vault._reset_for_tests()
        caplog.set_level(logging.WARNING, logger="clarityos.memory_vault")

        # A typical release-time CI invocation touches the vault path
        # many times (every test that exercises operator_state).
        for _ in range(10):
            memory_vault._is_encrypted()
        memory_vault.vault_init("release_no_pt_user")
        memory_vault.vault_put(
            "release_no_pt_user", "notes.release_marker", {"v": _read_version()},
        )

        plaintext_warnings = [
            rec for rec in caplog.records
            if "PLAINTEXT MODE ENABLED" in rec.getMessage()
        ]
        assert plaintext_warnings == [], (
            "Release-time vault ops fired the PLAINTEXT warning under "
            "default env — the release would ship with a banner that "
            "shouldn't be there."
        )

    def test_no_forbidden_fields_in_release_marker_payload(
        self, reset_stores,
    ):
        """A canary write — record an ELINS interaction with the
        version as the topic. The persisted vault entry must not
        carry any of the four forbidden text-bearing fields, even
        if the caller accidentally passes one in the context dict."""
        import memory_vault
        import operator_state

        operator_state.record_elins_interaction(
            "release_canary_user", "release_canary_id",
            context={
                "topic": _read_version(),
                "kind":  "global",
                # Intentionally smuggle in a forbidden field — the
                # FIX-P2 / FIX-P5 contract removes it before persist.
                "text":  "PROMPT BODY MUST NOT LEAK INTO RELEASE",
            },
        )
        entries = memory_vault.vault_list("release_canary_user")
        for k, entry in entries.items():
            if not k.startswith("elins.") or not isinstance(entry, dict):
                continue
            for forbidden in (
                "text", "scenario_text", "input_text", "raw_text",
            ):
                assert forbidden not in entry, (
                    f"Release-time canary saw {forbidden!r} survive "
                    f"into the vault — FIX-P2 / FIX-P5 contract broken."
                )


# ===========================================================================
# D6.7 — Cross-document consistency
# ===========================================================================
class TestDocumentCrossReferences:
    """The README and CHANGELOG must agree on the current VERSION.
    Drift here typically means someone bumped one file but forgot
    the other."""

    def test_readme_mentions_current_version(self):
        v = _read_version()
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        assert v in readme, (
            f"README.md does not mention the current VERSION {v!r}"
        )

    def test_invariants_doc_exists(self):
        assert (REPO_ROOT / "docs" / "invariants.md").is_file()

    def test_boundaries_doc_exists(self):
        assert (REPO_ROOT / "docs" / "boundaries.md").is_file()

    def test_deployment_doc_exists(self):
        assert (REPO_ROOT / "docs" / "deployment.md").is_file()
