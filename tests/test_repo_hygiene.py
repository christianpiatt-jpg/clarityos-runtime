"""
PASS-6 Phase F — Repo hygiene checks.

These tests gate the repository's upload shape. They complement (do
not duplicate) the standalone scripts:

  * ``scripts/check_repo_clean.py``    — pre-upload gate, also checks
                                         for secret files. Runs against
                                         the filesystem (no git
                                         required).
  * ``scripts/verify_dependencies.py`` — pre-upload gate, walks every
                                         root-level .py file's imports
                                         and asserts requirements.txt
                                         coverage.

The pytest assertions below match the Phase F task spec:

  * No stray files (temp / log / editor backups) anywhere in the tree.
  * Required scaffolding exists at known paths (the runtime spine
    modules, the workflow files, the docs files, the test config).
  * Dependency declarations are exact-pinned.
  * No raw ``__init__.py`` drift in the test tree (tests/ doesn't
    need one; if one ever appears it must be intentional and
    documented).

All checks are read-only filesystem walks. They produce no side
effects and have no network dependencies.
"""
from __future__ import annotations

import fnmatch
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent

# Stray-file globs — none of these patterns may match any file
# anywhere in the tracked tree. Mirrors ``scripts/check_repo_clean.py``
# so the two checks stay in sync.
_STRAY_FILE_GLOBS: tuple[str, ...] = (
    "*~",            # emacs / vim backup
    "*.bak",
    "*.tmp",
    "*.orig",        # merge backup
    "*.rej",         # patch reject
    "*.swp",         # vim swap
    "*.swo",
    ".DS_Store",
    "Thumbs.db",
)

# Directories we deliberately skip during the walk. Build/cache dirs
# are ignored by .gitignore but may exist locally; they are not part
# of the tracked repo shape.
_SKIP_DIRS: frozenset[str] = frozenset({
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "htmlcov", "build", "dist", ".venv", "venv", ".git",
    "node_modules",
})


def _walk_files() -> list[Path]:
    """Return every file in the tree, skipping local-only / build
    directories that .gitignore covers."""
    out: list[Path] = []
    for p in REPO_ROOT.rglob("*"):
        if p.is_dir():
            continue
        if any(part in _SKIP_DIRS for part in p.relative_to(REPO_ROOT).parts):
            continue
        out.append(p)
    return out


# ===========================================================================
# F3a — No stray files anywhere in the tracked tree
# ===========================================================================
class TestNoStrayFiles:
    """No editor backups, temp files, OS scratch, or patch
    leftovers may be present in the upload-ready tree. Catches a
    developer who accidentally ``git add``ed their ``app.py~`` or
    a leftover ``.DS_Store``."""

    @pytest.mark.parametrize("glob", _STRAY_FILE_GLOBS)
    def test_no_files_match_stray_glob(self, glob):
        files = _walk_files()
        offenders = [
            str(f.relative_to(REPO_ROOT))
            for f in files
            if fnmatch.fnmatch(f.name, glob)
        ]
        assert offenders == [], (
            f"hygiene violated — stray files matching {glob!r}:\n" +
            "\n".join(f"  {s}" for s in offenders)
        )

    def test_no_log_files_in_repo_root(self):
        """Log files at the repo root indicate an unintended commit
        from a local run."""
        offenders = [
            f.name for f in REPO_ROOT.iterdir()
            if f.is_file() and f.suffix == ".log"
        ]
        assert offenders == [], (
            f"hygiene violated — log files at root: {offenders!r}"
        )


# ===========================================================================
# F3b — Required scaffolding is present at known paths
# ===========================================================================
class TestRequiredScaffolding:
    """The release pipeline assumes a fixed shape. Missing any of the
    files below would break the CI gate, the release workflow, or a
    fresh contributor's onboarding."""

    @pytest.mark.parametrize("rel", [
        # Manifest + changelog.
        "VERSION",
        "CHANGELOG.md",
        "README.md",
        # Dependency declarations.
        "requirements.txt",
        "requirements-dev.txt",
        # Repo hygiene.
        ".gitignore",
        ".env.example",
        # Test config.
        "pytest.ini",
        "tests/conftest.py",
        # Workflows.
        ".github/workflows/ci.yml",
        ".github/workflows/deploy.yml",
        ".github/workflows/release.yml",
        # Documentation.
        "docs/runtime_architecture.md",
        "docs/invariants.md",
        "docs/boundaries.md",
        "docs/deployment.md",
        "docs/performance.md",
        # Runtime spine.
        "app.py",
        "intelligence_kernel.py",
        "model_router.py",
        "operator_state.py",
        "memory_vault.py",
        "runtime_privacy.py",
        # Helper scripts.
        "scripts/run_ci_gates.sh",
        "scripts/cut_release.sh",
        "scripts/run_load_probe.py",
        "scripts/check_repo_clean.py",
        "scripts/verify_dependencies.py",
    ])
    def test_required_file_exists(self, rel):
        path = REPO_ROOT / rel
        assert path.is_file(), (
            f"required scaffolding file missing: {rel!r}"
        )

    def test_release_notes_for_current_version_exists(self):
        """The release-notes source for the value in VERSION must
        exist (mirrors the release-integrity test). Phase F repeats
        the assertion here so a missing notes file fails both gates."""
        v = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
        assert (REPO_ROOT / "docs" / "release_notes" / f"{v}.md").is_file(), (
            f"release notes missing for VERSION={v!r}"
        )


# ===========================================================================
# F2 — Dependency freeze: exact pins, no ranges, no unpinned entries
# ===========================================================================
class TestDependencyFreeze:
    """Every entry in requirements.txt must use an exact version pin
    (``pkg==X.Y.Z``). Range specifiers (``>=``, ``~=``, ``<``) and
    unpinned entries are forbidden — the production image needs a
    reproducible dependency set."""

    _PINNED_RE = re.compile(
        # name, optional extras, ==, version. Environment markers
        # after ``;`` are allowed.
        r"^[A-Za-z0-9_.\-]+(?:\[[A-Za-z0-9_,\-]+\])?==[A-Za-z0-9._\-+]+(\s*;.*)?$"
    )

    def _entries(self, rel: str) -> list[str]:
        path = REPO_ROOT / rel
        out: list[str] = []
        if not path.is_file():
            return out
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("-r"):
                continue
            out.append(line)
        return out

    def test_requirements_txt_only_exact_pins(self):
        offenders: list[str] = []
        for entry in self._entries("requirements.txt"):
            if not self._PINNED_RE.match(entry):
                offenders.append(entry)
        assert offenders == [], (
            "dependency freeze violated — non-exact pins in "
            "requirements.txt:\n" +
            "\n".join(f"  {o!r}" for o in offenders)
        )

    def test_requirements_dev_txt_only_exact_pins(self):
        offenders: list[str] = []
        for entry in self._entries("requirements-dev.txt"):
            if not self._PINNED_RE.match(entry):
                offenders.append(entry)
        assert offenders == [], (
            "dependency freeze violated — non-exact pins in "
            "requirements-dev.txt:\n" +
            "\n".join(f"  {o!r}" for o in offenders)
        )

    def test_requirements_dev_includes_runtime_requirements(self):
        """The dev file pulls runtime deps transitively via ``-r
        requirements.txt`` so a single ``pip install -r
        requirements-dev.txt`` boots a developer's environment."""
        text = (REPO_ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
        assert "-r requirements.txt" in text, (
            "requirements-dev.txt does not include the production "
            "requirements transitively"
        )

    def test_no_dev_only_packages_in_runtime_requirements(self):
        """Dev-only packages (pytest, pytest-cov, httpx) must not
        appear in requirements.txt. Catches a developer who adds a
        test-only dep to the wrong file."""
        text = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
        for forbidden in ("pytest", "pytest-cov", "httpx", "mypy", "ruff", "black"):
            # Match as a whole word on a line — substring isn't enough.
            pattern = re.compile(
                rf"^\s*{re.escape(forbidden)}(\[[^\]]+\])?(==|>=|<=|~=|>|<|;|$)",
                re.MULTILINE,
            )
            assert not pattern.search(text), (
                f"dev-only package {forbidden!r} leaked into requirements.txt"
            )


# ===========================================================================
# F3c — No __init__.py drift in tests/
# ===========================================================================
class TestNoInitPyDrift:
    """The runtime spine intentionally has no ``__init__.py`` (the
    modules live at the repo root). The ``tests/`` directory follows
    the same convention — pytest auto-discovers tests without needing
    an init file. If an ``__init__.py`` appears under tests/ it must
    be intentional and documented; this test surfaces such a
    change for review."""

    def test_no_init_py_in_tests_dir(self):
        path = REPO_ROOT / "tests" / "__init__.py"
        assert not path.is_file(), (
            "tests/__init__.py present — pytest doesn't need it and "
            "its presence indicates accidental drift. If intentional, "
            "remove this assertion and document why in tests/conftest.py."
        )

    def test_no_init_py_in_scripts_dir(self):
        """``scripts/`` is a helper-script collection, not an
        importable package. Adding ``__init__.py`` here would
        confuse the verify_dependencies importer."""
        path = REPO_ROOT / "scripts" / "__init__.py"
        assert not path.is_file(), (
            "scripts/__init__.py present — scripts/ is not a Python "
            "package."
        )


# ===========================================================================
# F3d — Helper scripts are executable + parseable
# ===========================================================================
class TestHelperScripts:
    """The helper scripts under ``scripts/`` are documented in
    README.md. Each must parse as valid Python (where applicable)
    and start with a shebang."""

    @pytest.mark.parametrize("rel", [
        "scripts/run_load_probe.py",
        "scripts/check_repo_clean.py",
        "scripts/verify_dependencies.py",
    ])
    def test_script_starts_with_python_shebang(self, rel):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        first_line = text.splitlines()[0]
        assert first_line.startswith("#!"), (
            f"{rel} missing shebang"
        )
        assert "python" in first_line, (
            f"{rel} shebang is not a Python interpreter: {first_line!r}"
        )

    @pytest.mark.parametrize("rel", [
        "scripts/run_load_probe.py",
        "scripts/check_repo_clean.py",
        "scripts/verify_dependencies.py",
    ])
    def test_script_parses_as_python(self, rel):
        import ast
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        try:
            ast.parse(text)
        except SyntaxError as e:
            pytest.fail(f"{rel} is not valid Python: {e}")

    @pytest.mark.parametrize("rel", [
        "scripts/run_ci_gates.sh",
        "scripts/cut_release.sh",
    ])
    def test_shell_script_starts_with_bash_shebang(self, rel):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        first_line = text.splitlines()[0]
        assert first_line.startswith("#!"), (
            f"{rel} missing shebang"
        )
        assert "bash" in first_line or "sh" in first_line, (
            f"{rel} shebang is not a shell: {first_line!r}"
        )
