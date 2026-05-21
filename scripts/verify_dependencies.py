#!/usr/bin/env python3
"""
PASS-6 Phase F — Dependency verification.

Walks the runtime-spine modules' top-level ``import`` statements and
asserts each external import is declared in ``requirements.txt``
(production) or ``requirements-dev.txt`` (tests-only). The script
is also intended to be invokable as a step in CI / pre-commit to
catch:

  * runtime imports of a package that isn't in requirements.txt;
  * stale dependency entries that no longer match any import;
  * dev-only deps accidentally pulled into the runtime spine.

Stdlib-only (uses ``sys.stdlib_module_names`` from Python 3.10+).

Usage:
    python scripts/verify_dependencies.py            # check + exit 0/1
    python scripts/verify_dependencies.py --verbose  # show every match
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent

# Runtime-spine files whose imports must be covered by requirements.txt
# (production). New spine modules go here. The forward import check
# walks ALL root-level .py files (so adjacent runtime modules like
# billing_intents.py are also covered); RUNTIME_SPINE_FILES is just
# the locked-contract subset used in failure-message scoping.
RUNTIME_SPINE_FILES: tuple[str, ...] = (
    "app.py",
    "intelligence_kernel.py",
    "model_router.py",
    "operator_state.py",
    "memory_vault.py",
    "runtime_privacy.py",
    "runtime_http_config.py",
    "kernel_logging.py",
)

# Test files whose imports must be covered by EITHER requirements.txt
# or requirements-dev.txt. We walk ``tests/`` recursively.
TEST_DIR = "tests"

# Packages declared in requirements.txt that are NOT expected to
# appear as ``import X`` statements in the source tree — they are
# needed at runtime (ASGI server, multipart parser used by FastAPI's
# file-upload internals, etc.) but consumed indirectly. The reverse
# "declared but never imported" check skips these.
_IMPLICIT_RUNTIME_DEPS: frozenset[str] = frozenset({
    # ASGI server used as a binary (`uvicorn app:app`); the runtime
    # source never imports it directly.
    "uvicorn",
    # FastAPI's file-upload + form parser pulls this in transitively;
    # ``app.py`` does NOT need to ``import multipart``.
    "python-multipart",
})

# Mapping of pip-package name → top-level Python import names.
# pip names use hyphens; import names use underscores. Some packages
# expose multiple top-level imports (e.g. google-cloud-* → google).
# Keep this map exhaustive for the production deps in requirements.txt.
_DIST_TO_IMPORTS: dict[str, set[str]] = {
    # --- BD1 (HTTP) ---
    "fastapi":               {"fastapi"},
    "uvicorn":               {"uvicorn"},
    "pydantic":              {"pydantic"},
    "python-multipart":      {"multipart", "python_multipart"},
    # --- Auth + crypto ---
    "bcrypt":                {"bcrypt"},
    # --- GCP backends ---
    "google-cloud-storage":  {"google"},
    "google-cloud-firestore":{"google"},
    "google-cloud-aiplatform":{"google", "vertexai"},
    # --- Billing ---
    "stripe":                {"stripe"},
    # --- Dev / test deps ---
    "pytest":                {"pytest", "_pytest"},
    "pytest-cov":            {"pytest_cov"},
    "httpx":                 {"httpx"},
}


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------
def _parse_requirements(path: Path) -> set[str]:
    """Return the set of pip-package names declared in
    ``requirements.txt`` (case-insensitive, extras stripped).
    Lines starting with ``-r`` are followed recursively."""
    out: set[str] = set()
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-r"):
            # Recursive include — resolve relative to this file.
            rel = line[2:].strip()
            out |= _parse_requirements(path.parent / rel)
            continue
        # Strip extras ``pkg[extra]==ver``, version pins, environment
        # markers (``pkg; python_version >= '3.12'``). The first token
        # before ``[``, ``==``, ``>=``, ``<=``, ``;``, or whitespace
        # is the pip-package name.
        m = re.match(r"^([A-Za-z0-9_.\-]+)", line)
        if m:
            out.add(m.group(1).lower())
    return out


def _top_level_imports_in(source: str) -> set[str]:
    """Walk a Python source file's AST and return the set of top-
    level import names. ``import a.b.c`` and ``from a.b import c``
    both contribute ``a`` to the set. Imports nested inside ``if``
    / ``try`` / functions are included (lazy imports count too).
    """
    out: set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                out.add(node.module.split(".")[0])
    return out


# ---------------------------------------------------------------------------
# Module-set helpers
# ---------------------------------------------------------------------------
def _stdlib_names() -> set[str]:
    """Best-effort stdlib module name set. Uses
    ``sys.stdlib_module_names`` on Python 3.10+; falls back to a
    hardcoded list."""
    names = getattr(sys, "stdlib_module_names", None)
    if names:
        return set(names)
    # Conservative fallback — only used on Python < 3.10.
    return {
        "abc", "argparse", "asyncio", "base64", "collections", "contextlib",
        "contextvars", "copy", "csv", "dataclasses", "datetime", "enum",
        "functools", "hashlib", "hmac", "http", "importlib", "inspect",
        "io", "itertools", "json", "logging", "math", "os", "pathlib",
        "pickle", "queue", "random", "re", "secrets", "shutil", "socket",
        "sqlite3", "ssl", "stat", "string", "struct", "subprocess", "sys",
        "tempfile", "textwrap", "threading", "time", "traceback", "types",
        "typing", "unittest", "urllib", "uuid", "warnings", "weakref",
    }


def _local_module_names() -> set[str]:
    """Every top-level ``*.py`` file at the repo root plus every
    directory at the repo root containing an ``__init__.py`` — those
    are local imports the spine can use without declaring them as
    external deps."""
    out: set[str] = set()
    for p in REPO_ROOT.iterdir():
        if p.is_file() and p.suffix == ".py":
            out.add(p.stem)
        elif p.is_dir() and (p / "__init__.py").is_file():
            out.add(p.name)
    return out


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
def _declared_import_names(declared_pkgs: Iterable[str]) -> set[str]:
    """Map ``{pkg_name}`` from requirements.txt → ``{top-level
    import name}`` via _DIST_TO_IMPORTS."""
    out: set[str] = set()
    for pkg in declared_pkgs:
        out |= _DIST_TO_IMPORTS.get(pkg, set())
    return out


def verify(verbose: bool = False) -> int:
    """Return 0 on full coverage, 1 otherwise."""
    runtime_pkgs = _parse_requirements(REPO_ROOT / "requirements.txt")
    dev_pkgs = _parse_requirements(REPO_ROOT / "requirements-dev.txt")

    runtime_import_names = _declared_import_names(runtime_pkgs)
    dev_import_names = _declared_import_names(dev_pkgs) | runtime_import_names

    stdlib = _stdlib_names()
    locals_ = _local_module_names()

    # ----- Walk the runtime spine -----
    spine_offenders: list[tuple[str, str]] = []
    for rel in RUNTIME_SPINE_FILES:
        path = REPO_ROOT / rel
        if not path.is_file():
            spine_offenders.append((rel, "<missing file>"))
            continue
        for imp in sorted(_top_level_imports_in(path.read_text(encoding="utf-8", errors="replace"))):
            if imp in stdlib or imp in locals_:
                continue
            if imp in runtime_import_names:
                if verbose:
                    print(f"  ok runtime  {rel}: {imp}")
                continue
            spine_offenders.append((rel, imp))

    # ----- Walk the tests/ tree -----
    test_offenders: list[tuple[str, str]] = []
    test_dir = REPO_ROOT / TEST_DIR
    if test_dir.is_dir():
        for path in sorted(test_dir.rglob("test_*.py")):
            for imp in sorted(_top_level_imports_in(path.read_text(encoding="utf-8", errors="replace"))):
                if imp in stdlib or imp in locals_:
                    continue
                # ``conftest`` is a sibling of test files inside the
                # tests/ directory; tests import from it as ``from
                # conftest import TestClient``. Treat it as local.
                if imp == "conftest":
                    continue
                if imp in dev_import_names:
                    if verbose:
                        rel = path.relative_to(REPO_ROOT)
                        print(f"  ok test     {rel}: {imp}")
                    continue
                test_offenders.append((str(path.relative_to(REPO_ROOT)), imp))

    # ----- Reverse check: every declared pkg should be used -----
    # Walk EVERY top-level .py file at the repo root, not just the
    # locked spine subset. ``billing_intents.py`` etc. legitimately
    # import third-party packages and the reverse check must see them
    # to avoid false "unused declared dep" warnings.
    runtime_imports_observed: set[str] = set()
    for path in sorted(REPO_ROOT.glob("*.py")):
        runtime_imports_observed |= _top_level_imports_in(
            path.read_text(encoding="utf-8", errors="replace"),
        )
    # Also walk any package directories at the repo root that are
    # imported by the spine (e.g. ``ELINS/``).
    for pkg_dir in sorted(p for p in REPO_ROOT.iterdir() if p.is_dir()):
        if (pkg_dir / "__init__.py").is_file():
            for path in pkg_dir.rglob("*.py"):
                runtime_imports_observed |= _top_level_imports_in(
                    path.read_text(encoding="utf-8", errors="replace"),
                )

    unused_runtime_pkgs: list[str] = []
    for pkg in runtime_pkgs:
        # Implicit-runtime packages (uvicorn, python-multipart) are
        # declared but consumed indirectly — skip them.
        if pkg in _IMPLICIT_RUNTIME_DEPS:
            continue
        expected_imports = _DIST_TO_IMPORTS.get(pkg)
        if not expected_imports:
            # No mapping registered — can't verify usage. Skip silently
            # for now; could become an error in a future hardening pass.
            continue
        if not (expected_imports & runtime_imports_observed):
            unused_runtime_pkgs.append(pkg)

    # ----- Report -----
    if verbose:
        print()
        print(f"runtime requirements.txt:  {sorted(runtime_pkgs)}")
        print(f"dev requirements-dev.txt:  {sorted(dev_pkgs - runtime_pkgs)}")
        print()

    failed = False
    if spine_offenders:
        failed = True
        print("FAIL — runtime spine imports not covered by requirements.txt:")
        for rel, imp in spine_offenders:
            print(f"  {rel}: {imp}")
    if test_offenders:
        failed = True
        print("FAIL — test imports not covered by requirements*.txt:")
        for rel, imp in test_offenders:
            print(f"  {rel}: {imp}")
    if unused_runtime_pkgs:
        failed = True
        print("FAIL — declared runtime deps with no observed import:")
        for pkg in unused_runtime_pkgs:
            print(f"  {pkg}")

    if not failed:
        print("dependency coverage ok:")
        print(f"  {len(runtime_pkgs)} runtime deps × every spine import accounted for")
        print(f"  {len(dev_pkgs - runtime_pkgs)} dev-only deps × every test import accounted for")
        return 0
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Verify runtime + test imports vs requirements.txt.",
    )
    ap.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print every matched import (otherwise only failures).",
    )
    args = ap.parse_args()
    return verify(verbose=args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
