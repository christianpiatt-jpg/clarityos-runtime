#!/usr/bin/env python3
"""
census_report.py — COW-1 Pathway-5 census substrate · 2026-08-04

Reads the repo AT PIN and classifies every in-scope Python module on two
independent axes:

  STUB / IMPL    — does the module contain real behavior, or only placeholders?
  WIRED / ORPHAN — is the module reachable from a declared deploy root?

Both axes are decided mechanically from the tree. Nothing is inferred from
commit history, issue text, or narrative. The report is derived-only: every
line is a restatement of what the blobs at pin say.

Design basis:
  - Read at pin, not working tree. Default source is `git show <pin>:<path>`
    so two runs at the same pin are byte-identical regardless of local edits.
    `--worktree` opts into working-tree reads and SAYS SO in the header.
  - Deterministic. No wall-clock, no timestamps, no iteration-order leakage;
    every collection is sorted before emission. The pin IS the timestamp.
  - On-demand. No daemon, no scheduler, no cache, no writes. Pure read →
    stdout. Running it twice changes nothing.
  - Declared rulebook. Every judgment call lives in the constants block below
    and is printed in the report header, so a reader can see which rule
    produced which verdict. Judgment calls are tagged [designed].

BOUNDS — what this module deliberately does NOT do:
  It stops at the classification substrate. It does not author the 10-item
  return format, the bounds attestation, or the regression / forward-trace /
  error-triangulation surfaces; those are specified in the HQ dispatch
  (hq_cow1_pathway_5_..._2026-08-04) which is not present in this tree.
  It is not an instrumentation engine and holds no state between runs
  (COW-1 punchlist, Condition 1: diagnostic map -> fix list, hard stop).

Usage:
  python analysis/census_report.py
  python analysis/census_report.py --pin <rev> --json
  python analysis/census_report.py --orphans-only
"""
from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Rulebook configuration — the census's judgment layer.
# Everything here is declared, tunable, and printed in the report header.
# ---------------------------------------------------------------------------

# Deploy entrypoints, read from the substrate that actually launches them:
#   Dockerfile      -> CMD exec uvicorn app:app
#   sos_runtime/    -> parallel Cloud Run service, main.py
# A module is WIRED iff it is transitively reachable from one of these.
DECLARED_ROOTS = ("app.py", "sos_runtime/main.py")

# Path prefixes excluded from the census. [designed]
# Archive/legacy trees are historical record, not runtime; skills_export is a
# bundle that is never imported by the runtime (ARCHITECTURE.md boundary).
EXCLUDED_PREFIXES = (
    "Clarity_OS_Operating_System/Archive/",
    "Index_Records/",
    "skills_export/",
)

# Path fragments excluded anywhere in the path. [designed]
EXCLUDED_FRAGMENTS = ("/venv/", "/site-packages/", "/node_modules/", "/.venv/")

# Modules matching these are roots of their own right — they are entered by a
# runner, not by an importer, so absence of an importer is not orphanhood.
# Reported under their own role rather than as ORPHAN. [designed]
TEST_PREFIXES = ("test_", "conftest")

# A function/method body is a STUB if, after the docstring is removed, it
# consists solely of these forms. [designed]
#   pass | ... | raise NotImplementedError | return | return None
# Anything else is IMPL. A module's verdict is the OR over its defs: one real
# def makes the module IMPL.

VERDICT_ORDER = ("ORPHAN", "STUB", "WIRED", "TEST")


# ---------------------------------------------------------------------------
# Substrate access — read at pin.
# ---------------------------------------------------------------------------

def _git(args: list[str]) -> bytes:
    """Run git and return raw bytes. Never text=True: this repo's console is
    cp1252 and text-mode would mojibake UTF-8 blobs."""
    proc = subprocess.run(["git", *args], capture_output=True)
    if proc.returncode != 0:
        raise SystemExit(
            f"git {' '.join(args)} failed: "
            f"{proc.stderr.decode('utf-8', 'replace').strip()}"
        )
    return proc.stdout


def resolve_pin(rev: str) -> str:
    return _git(["rev-parse", rev]).decode("ascii").strip()


def list_paths(pin: str, worktree: bool) -> list[str]:
    if worktree:
        raw = _git(["ls-files", "*.py"])
    else:
        raw = _git(["ls-tree", "-r", "--name-only", pin])
    paths = raw.decode("utf-8", "replace").splitlines()
    return sorted(p for p in paths if p.endswith(".py"))


def read_blob(pin: str, path: str, worktree: bool) -> str:
    if worktree:
        try:
            return Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
    return _git(["show", f"{pin}:{path}"]).decode("utf-8", "replace")


def in_scope(path: str) -> bool:
    if any(path.startswith(p) for p in EXCLUDED_PREFIXES):
        return False
    probe = "/" + path
    return not any(f in probe for f in EXCLUDED_FRAGMENTS)


# ---------------------------------------------------------------------------
# Axis 1 — STUB / IMPL
# ---------------------------------------------------------------------------

def _strip_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        return body[1:]
    return body


def is_stub_body(body: list[ast.stmt]) -> bool:
    """True iff the body is placeholder-only. See rulebook above."""
    stmts = _strip_docstring(body)
    if not stmts:
        return True
    for st in stmts:
        if isinstance(st, ast.Pass):
            continue
        if (isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant)
                and st.value.value is Ellipsis):
            continue
        if isinstance(st, ast.Raise):
            exc = st.exc
            name = None
            if isinstance(exc, ast.Name):
                name = exc.id
            elif isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name):
                name = exc.func.id
            if name == "NotImplementedError":
                continue
            return False
        if isinstance(st, ast.Return):
            if st.value is None:
                continue
            if isinstance(st.value, ast.Constant) and st.value.value is None:
                continue
            return False
        return False
    return True


def classify_defs(tree: ast.AST) -> tuple[int, int, int, list[str]]:
    """Return (n_impl, n_stub, n_class, sorted names of stub defs)."""
    n_impl = n_stub = n_class = 0
    stub_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            n_class += 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if is_stub_body(node.body):
                n_stub += 1
                stub_names.append(node.name)
            else:
                n_impl += 1
    return n_impl, n_stub, n_class, sorted(stub_names)


def is_facade(tree: ast.AST) -> bool:
    """A def-less module that re-exports names from another module.

    Without this rule a live façade (elins_persistence.py re-exporting the
    Unit-25 SQLite layer) reads as EMPTY, which is a false dead-code signal:
    the module carries no behavior of its own but is load-bearing. [designed]
    """
    for st in getattr(tree, "body", []):
        if isinstance(st, ast.ImportFrom) and any(
                a.name != "*" for a in st.names):
            return True
    return False


def has_substance(tree: ast.AST) -> bool:
    """Module-level code beyond imports/docstring/constants-free scaffolding."""
    for st in _strip_docstring(getattr(tree, "body", [])):
        if isinstance(st, (ast.Import, ast.ImportFrom, ast.Pass)):
            continue
        return True
    return False


# ---------------------------------------------------------------------------
# Axis 2 — WIRED / ORPHAN (reachability from declared roots)
# ---------------------------------------------------------------------------

def path_to_module(path: str) -> str:
    stem = path[:-3]  # drop .py
    if stem.endswith("/__init__"):
        stem = stem[: -len("/__init__")]
    return stem.replace("/", ".")


def module_package(path: str) -> str:
    """Package a module lives in, for resolving relative imports."""
    mod = path_to_module(path)
    if path.endswith("/__init__.py"):
        return mod
    return mod.rpartition(".")[0]


def resolve_import(name: str, index: dict[str, str]) -> str | None:
    """Longest-prefix match of a dotted name against repo-local modules."""
    parts = name.split(".")
    for i in range(len(parts), 0, -1):
        cand = ".".join(parts[:i])
        if cand in index:
            return index[cand]
    return None


def extract_edges(tree: ast.AST, path: str,
                  index: dict[str, str]) -> set[str]:
    """Repo-local paths this module imports."""
    pkg = module_package(path)
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                hit = resolve_import(alias.name, index)
                if hit:
                    out.add(hit)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg.split(".")
                base = base[: len(base) - node.level + 1] if node.level > 1 \
                    else base
                prefix = ".".join([p for p in base if p])
                root = f"{prefix}.{node.module}" if node.module else prefix
            else:
                root = node.module or ""
            if not root:
                continue
            # `from pkg import mod` may name a submodule; try that first.
            for alias in node.names:
                hit = resolve_import(f"{root}.{alias.name}", index)
                if hit:
                    out.add(hit)
            hit = resolve_import(root, index)
            if hit:
                out.add(hit)
    return out


def reachable(roots: list[str], edges: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    stack = [r for r in roots if r in edges]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(sorted(edges.get(cur, ())))
    return seen


def is_test(path: str) -> bool:
    name = path.rpartition("/")[2]
    return any(name.startswith(p) for p in TEST_PREFIXES)


# ---------------------------------------------------------------------------
# Census
# ---------------------------------------------------------------------------

def build_census(pin: str, worktree: bool) -> dict:
    paths = [p for p in list_paths(pin, worktree) if in_scope(p)]
    index = {path_to_module(p): p for p in paths}

    records: dict[str, dict] = {}
    edges: dict[str, set[str]] = {}
    unparsed: list[str] = []

    for path in paths:
        src = read_blob(pin, path, worktree)
        try:
            tree = ast.parse(src)
        except SyntaxError as exc:
            unparsed.append(f"{path}: {exc.msg} (line {exc.lineno})")
            edges[path] = set()
            records[path] = {
                "path": path, "impl_defs": 0, "stub_defs": 0,
                "classes": 0, "stub_names": [],
                "loc": len(src.splitlines()),
                "code": "UNPARSED", "stub_ratio": 0.0,
            }
            continue

        n_impl, n_stub, n_class, stub_names = classify_defs(tree)
        if n_impl:
            code = "IMPL"
        elif n_stub:
            code = "STUB"
        elif is_facade(tree):
            code = "FACADE"    # def-less re-export surface; load-bearing
        elif has_substance(tree):
            code = "DATA"      # constants / assignments only, no defs
        else:
            code = "EMPTY"     # imports and docstring only

        total = n_impl + n_stub
        records[path] = {
            "path": path,
            "impl_defs": n_impl,
            "stub_defs": n_stub,
            "classes": n_class,
            "stub_names": stub_names,
            "loc": len(src.splitlines()),
            "code": code,
            "stub_ratio": round(n_stub / total, 3) if total else 0.0,
        }
        edges[path] = extract_edges(tree, path, index)

    live = reachable([r for r in DECLARED_ROOTS], edges)

    for path, rec in records.items():
        if path in live:
            rec["wire"] = "WIRED"
        elif is_test(path):
            rec["wire"] = "TEST"
        else:
            rec["wire"] = "ORPHAN"
        rec["imports"] = sorted(edges.get(path, ()))
        rec["is_root"] = path in DECLARED_ROOTS

    indeg: dict[str, int] = {p: 0 for p in records}
    for src_path, dsts in edges.items():
        for d in dsts:
            if d in indeg:
                indeg[d] += 1
    for path, rec in records.items():
        rec["imported_by_count"] = indeg[path]
        # Imported, but only by modules that are themselves unreachable:
        # an island cluster, not a live dependency.
        rec["island"] = (rec["wire"] == "ORPHAN"
                         and rec["imported_by_count"] > 0)

    missing_roots = [r for r in DECLARED_ROOTS if r not in records]

    return {
        "pin": pin,
        "source": "worktree" if worktree else "pin",
        "roots": list(DECLARED_ROOTS),
        "missing_roots": missing_roots,
        "excluded_prefixes": list(EXCLUDED_PREFIXES),
        "modules": [records[p] for p in sorted(records)],
        "unparsed": sorted(unparsed),
    }


def summarize(census: dict) -> dict:
    mods = census["modules"]
    def count(**kw) -> int:
        return sum(1 for m in mods
                   if all(m.get(k) == v for k, v in kw.items()))
    return {
        "modules_total": len(mods),
        "wired": count(wire="WIRED"),
        "orphan": count(wire="ORPHAN"),
        "test": count(wire="TEST"),
        "island_orphans": sum(1 for m in mods if m.get("island")),
        "impl": count(code="IMPL"),
        "stub": count(code="STUB"),
        "facade": count(code="FACADE"),
        "data": count(code="DATA"),
        "empty": count(code="EMPTY"),
        "unparsed": len(census["unparsed"]),
        "wired_but_stub": count(wire="WIRED", code="STUB"),
        "impl_but_orphan": count(wire="ORPHAN", code="IMPL"),
        "loc_wired": sum(m["loc"] for m in mods if m["wire"] == "WIRED"),
        "loc_orphan": sum(m["loc"] for m in mods if m["wire"] == "ORPHAN"),
    }


# ---------------------------------------------------------------------------
# Emission — deterministic, derived-only.
# ---------------------------------------------------------------------------

def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--pin", default="HEAD",
                    help="git rev to read at (default: HEAD)")
    ap.add_argument("--worktree", action="store_true",
                    help="read the working tree instead of the pin "
                         "(non-deterministic; declared in the header)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--orphans-only", action="store_true")
    ap.add_argument("--stubs-only", action="store_true")
    args = ap.parse_args()

    pin = resolve_pin(args.pin)
    census = build_census(pin, args.worktree)
    summary = summarize(census)

    if args.json:
        print(json.dumps({**census, "summary": summary}, indent=2,
                         sort_keys=True))
        return

    src = census["source"]
    print(f"CENSUS - repo at pin {pin[:12]} (source: {src})")
    if src == "worktree":
        print("  WARNING: working-tree read. Not reproducible from the pin "
              "alone.")
    print(f"Roots: {', '.join(census['roots'])}")
    if census["missing_roots"]:
        print(f"  MISSING ROOTS: {', '.join(census['missing_roots'])} "
              f"- reachability is unsound; treat WIRED as a floor.")
    print(f"Excluded: {', '.join(census['excluded_prefixes'])}")
    print("Rulebook: STUB = body is pass/.../NotImplementedError/return-None "
          "after docstring strip;")
    print("          WIRED = transitively reachable from a declared root; "
          "TEST = runner-entered.")
    print("=" * 78)

    rows = census["modules"]
    if args.orphans_only:
        rows = [m for m in rows if m["wire"] == "ORPHAN"]
    if args.stubs_only:
        rows = [m for m in rows if m["code"] in ("STUB", "EMPTY")]

    for m in rows:
        flags = []
        if m["is_root"]:
            flags.append("ROOT")
        if m["island"]:
            flags.append(f"ISLAND(in={m['imported_by_count']})")
        if m["wire"] == "WIRED" and m["code"] == "STUB":
            flags.append("HOLLOW-WIRE")
        if m["wire"] == "ORPHAN" and m["code"] == "IMPL":
            flags.append("DARK-IMPL")
        tail = ("  " + " ".join(flags)) if flags else ""
        print(f"[{m['wire']:<6}][{m['code']:<8}] {m['path']}  "
              f"loc={m['loc']} impl={m['impl_defs']} stub={m['stub_defs']}"
              f"{tail}")
        if m["stub_names"] and m["code"] != "IMPL":
            print(f"           stubs: {', '.join(m['stub_names'][:8])}"
                  f"{' ...' if len(m['stub_names']) > 8 else ''}")

    if census["unparsed"]:
        print("\nUNPARSED (excluded from both axes):")
        for u in census["unparsed"]:
            print(f"  {u}")

    print("\n" + "=" * 78)
    s = summary
    print(f"MODULES {s['modules_total']} - "
          f"WIRED {s['wired']} - ORPHAN {s['orphan']} - TEST {s['test']}")
    print(f"CODE: IMPL {s['impl']} - STUB {s['stub']} - "
          f"FACADE {s['facade']} - DATA {s['data']} - "
          f"EMPTY {s['empty']} - UNPARSED {s['unparsed']}")
    print(f"CROSS: HOLLOW-WIRE {s['wired_but_stub']} - "
          f"DARK-IMPL {s['impl_but_orphan']} - "
          f"ISLAND-ORPHAN {s['island_orphans']}")
    print(f"LOC: wired {s['loc_wired']} - orphan {s['loc_orphan']}")


if __name__ == "__main__":
    sys.exit(main())
