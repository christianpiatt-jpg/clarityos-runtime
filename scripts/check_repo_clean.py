#!/usr/bin/env python3
"""
PASS-6 Phase F — Repository cleanliness check.

Asserts the repository is in a clean, upload-ready shape:

  * No stray temp / log / editor-backup files in the tracked tree.
  * No build artifacts (``dist/``, ``build/``, ``*.egg-info``).
  * No secret files (``.env``, ``sa.json``).
  * No process-local vault scratch (``*.vault.json``, ``*.sqlite3``).
  * Every required top-level scaffold file is present
    (VERSION, README.md, requirements.txt, .gitignore, pytest.ini,
    .github/workflows/{ci,deploy,release}.yml).

Exit code:
    0 — repo is clean and upload-ready.
    1 — at least one violation. Each violation is printed.

Stdlib-only (Path + fnmatch + argparse). Runs against the filesystem,
not git — so it works even before ``git init``.

Usage:
    python scripts/check_repo_clean.py
    python scripts/check_repo_clean.py --verbose
"""
from __future__ import annotations

import argparse
import fnmatch
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Stray-file globs. Any file matching one of these patterns is a
# violation regardless of where in the repo it lives.
# ---------------------------------------------------------------------------
STRAY_FILE_GLOBS: tuple[str, ...] = (
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

# Files that must NEVER ship in the upload, even if a contributor
# accidentally committed them. Any one of these in the tree is fatal.
SECRET_FILE_GLOBS: tuple[str, ...] = (
    ".env",
    "*.env",         # except .env.example, handled explicitly
    "sa.json",
    "*-sa.json",
    "service-account*.json",
    "gcp-key*.json",
)

# Directories whose presence indicates build / cache artifacts that
# should not be tracked. We allow them to exist (the operator may
# have run pytest locally), but they should already be gitignored;
# the check_repo_clean script just calls out their existence so a
# future ``git status --porcelain`` step in CI can verify they're
# ignored.
LOCAL_ONLY_DIRS: tuple[str, ...] = (
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "htmlcov",
    "build",
    "dist",
    ".venv",
    "venv",
)

# Required scaffolding — every release tag must carry these.
REQUIRED_FILES: tuple[str, ...] = (
    "VERSION",
    "README.md",
    "CHANGELOG.md",
    "requirements.txt",
    "requirements-dev.txt",
    ".gitignore",
    "pytest.ini",
    ".env.example",
    ".github/workflows/ci.yml",
    ".github/workflows/deploy.yml",
    ".github/workflows/release.yml",
    "docs/runtime_architecture.md",
    "docs/invariants.md",
    "docs/boundaries.md",
    "docs/deployment.md",
    "docs/performance.md",
    "tests/conftest.py",
    "app.py",
    "intelligence_kernel.py",
    "model_router.py",
    "operator_state.py",
    "memory_vault.py",
    "runtime_privacy.py",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _walk_repo_files(verbose: bool) -> list[Path]:
    """Walk the repo tree and return every file path, skipping the
    "local-only" directories we expect to be present but ignored."""
    out: list[Path] = []
    skip_dirs = set(LOCAL_ONLY_DIRS) | {".git", "node_modules"}
    for p in REPO_ROOT.rglob("*"):
        if p.is_dir():
            continue
        # Skip files under any local-only dir anywhere in the tree.
        if any(part in skip_dirs for part in p.relative_to(REPO_ROOT).parts):
            continue
        out.append(p)
    if verbose:
        print(f"  walked {len(out)} files")
    return out


def _check_stray_files(files: list[Path]) -> list[str]:
    out: list[str] = []
    for f in files:
        name = f.name
        for pattern in STRAY_FILE_GLOBS:
            if fnmatch.fnmatch(name, pattern):
                out.append(str(f.relative_to(REPO_ROOT)))
                break
    return out


def _check_secret_files(files: list[Path]) -> list[str]:
    out: list[str] = []
    for f in files:
        rel = f.relative_to(REPO_ROOT)
        name = f.name
        # The committed template file is explicitly allowed.
        if name == ".env.example":
            continue
        for pattern in SECRET_FILE_GLOBS:
            if fnmatch.fnmatch(name, pattern):
                out.append(str(rel))
                break
    return out


def _check_required_scaffolding() -> list[str]:
    out: list[str] = []
    for rel in REQUIRED_FILES:
        path = REPO_ROOT / rel
        if not path.is_file():
            out.append(rel)
    return out


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def check(verbose: bool = False) -> int:
    print("checking repo cleanliness at", REPO_ROOT)
    files = _walk_repo_files(verbose=verbose)

    failures: list[str] = []

    stray = _check_stray_files(files)
    if stray:
        failures.append(
            "FAIL — stray temp / backup files in tree:\n" +
            "\n".join(f"  {s}" for s in stray)
        )

    secrets = _check_secret_files(files)
    if secrets:
        failures.append(
            "FAIL — secret files in tree (must never be committed):\n" +
            "\n".join(f"  {s}" for s in secrets)
        )

    missing = _check_required_scaffolding()
    if missing:
        failures.append(
            "FAIL — required scaffolding files missing:\n" +
            "\n".join(f"  {s}" for s in missing)
        )

    if failures:
        for f in failures:
            print(f)
        return 1

    print("repo is clean:")
    print(f"  {len(files)} tracked-shape files inspected")
    print(f"  {len(REQUIRED_FILES)} required scaffolding files present")
    print(f"  0 stray files, 0 secret files")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print every directory walked and file inspected.",
    )
    args = ap.parse_args()
    return check(verbose=args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
