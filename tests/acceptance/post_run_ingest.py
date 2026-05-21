#!/usr/bin/env python3
"""
tests/acceptance/post_run_ingest.py

Reads a single run's report.json and appends a compact metrics record
to tests/acceptance/reports/acceptance_runs.jsonl for longitudinal
trend tracking.

Operator-invoked; Claude does NOT execute this during materialization.

Usage:
    python tests/acceptance/post_run_ingest.py <run_dir>

Where <run_dir> is a directory under tests/acceptance/reports/ that
contains report.json (e.g., tests/acceptance/reports/run-20260508T142133Z-7a3c).

Exit codes:
    0   success (record appended)
    2   missing report.json or unreadable input
    64  usage error
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _scenario_summary(scenarios: dict) -> dict:
    """Reduce per-scenario results to id → {pass, duration_ms}."""
    out: dict = {}
    for sid, s in (scenarios or {}).items():
        if not isinstance(s, dict):
            continue
        out[sid] = {
            "pass": s.get("pass"),
            "duration_ms": s.get("duration_ms"),
        }
    return out


def _stability_stats(scenarios: dict) -> dict | None:
    """Pull stability stats from scenario 05's encoded details, if any."""
    s05 = (scenarios or {}).get("05_stability_window")
    if not isinstance(s05, dict):
        return None
    raw = s05.get("details")
    if not isinstance(raw, str):
        return None
    try:
        parsed: Any = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    stats = parsed.get("stats")
    monotonicity = parsed.get("monotonicity_pass")
    if not isinstance(stats, dict):
        return {"monotonicity_pass": monotonicity}
    return {
        "monotonicity_pass": monotonicity,
        "iterations": stats.get("iterations"),
        "pass_count": stats.get("pass_count"),
        "mean_ms":    stats.get("mean_ms"),
        "max_ms":     stats.get("max_ms"),
        "min_ms":     stats.get("min_ms"),
        "stddev_ms":  stats.get("stddev_ms"),
    }


def ingest(run_dir: Path, *, dry_run: bool = False) -> int:
    """Ingest one run.

    Phase 4D additive — `dry_run=True` prints the record that *would*
    be appended and skips the file write. Default behaviour (dry_run
    omitted or False) is byte-for-byte unchanged from Phase 1.
    """
    report_path = run_dir / "report.json"
    if not report_path.is_file():
        print(f"[ingest] missing {report_path}", file=sys.stderr)
        return 2

    try:
        data = json.loads(report_path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[ingest] could not read {report_path}: {exc}", file=sys.stderr)
        return 2

    record = {
        "run_id":      data.get("run_id"),
        "mode":        data.get("mode"),
        "pass":        data.get("pass"),
        "started_at":  data.get("started_at"),
        "finished_at": data.get("finished_at"),
        "scenarios":   _scenario_summary(data.get("scenarios") or {}),
        "stability":   _stability_stats(data.get("scenarios") or {}),
    }

    out_path = run_dir.parent / "acceptance_runs.jsonl"

    if dry_run:
        # Phase 4D — no disk write. Print the record exactly as it
        # would be appended (compact JSON, one line, then a blank line
        # for readability) plus an explicit destination hint.
        print(f"[ingest] DRY RUN — no write performed")
        print(f"[ingest] would append to: {out_path}")
        print(json.dumps(record))
        return 0

    try:
        with out_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError as exc:
        print(f"[ingest] could not append to {out_path}: {exc}", file=sys.stderr)
        return 2

    print(f"[ingest] appended record for {record['run_id']} → {out_path}")
    return 0


def main(argv: list[str]) -> int:
    # Phase 4D additive — accept `--dry-run` flag in any position.
    # Phase 5A additive — accept `--rotate` flag; when set, no
    # positional run_dir is required and ingest() is not invoked.
    args = argv[1:]
    dry_run = False
    rotate = False
    positional: list[str] = []
    for a in args:
        if a == "--dry-run":
            dry_run = True
        elif a == "--rotate":
            rotate = True
        elif a.startswith("--"):
            print(f"[ingest] unknown flag: {a}", file=sys.stderr)
            return 64
        else:
            positional.append(a)

    # Phase 5A — rotation branch. When --rotate is set, the script
    # rotates run directories under tests/acceptance/reports/ (the
    # actual location of run dirs per Phase 1 path adaptation; the
    # spec referenced tests/acceptance/runs/). Rotation honours
    # --dry-run by printing the plan without deleting.
    if rotate:
        if positional:
            print(
                "[rotate] --rotate takes no positional argument; got: "
                + " ".join(positional),
                file=sys.stderr,
            )
            return 64
        return rotate_runs(dry_run=dry_run)

    if len(positional) != 1:
        print(
            "usage: post_run_ingest.py [--dry-run] <run_dir>"
            "       post_run_ingest.py --rotate [--dry-run]",
            file=sys.stderr,
        )
        return 64

    run_dir = Path(positional[0]).resolve()
    if not run_dir.is_dir():
        print(f"[ingest] not a directory: {run_dir}", file=sys.stderr)
        return 64
    return ingest(run_dir, dry_run=dry_run)


# ============================================================
# Phase 5A additive — run rotation. Operator-invoked via --rotate.
# ============================================================

import os as _os
import re as _re
import shutil as _shutil

_RUN_ID_RE = _re.compile(r"^run-\d{8}T\d{6}Z-[0-9a-f]{4}$")
_DEFAULT_RETENTION = 50


def _reports_root() -> Path:
    """Path to tests/acceptance/reports/, overridable via env."""
    return Path(_os.environ.get(
        "CLARITYOS_ACCEPTANCE_REPORTS",
        "tests/acceptance/reports",
    )).resolve()


def _retention_limit() -> int:
    """Parse CLARITYOS_ACCEPTANCE_RETENTION; default 50; min 1."""
    raw = _os.environ.get("CLARITYOS_ACCEPTANCE_RETENTION")
    if raw is None:
        return _DEFAULT_RETENTION
    try:
        n = int(raw)
        return max(1, n)
    except ValueError:
        return _DEFAULT_RETENTION


def rotate_runs(*, dry_run: bool = False) -> int:
    """Rotate run directories under tests/acceptance/reports/.

    Keeps the newest N (default 50) run-id-named directories. Anything
    that does not match ^run-\\d{8}T\\d{6}Z-[0-9a-f]{4}$ is left
    untouched — including acceptance_runs.jsonl and expected_outputs/.

    Returns 0 on success (or if no rotation needed); 2 on I/O failure.
    """
    root = _reports_root()
    limit = _retention_limit()

    print(f"[rotate] reports root: {root}")
    print(f"[rotate] retention limit: {limit}")

    if not root.is_dir():
        print(f"[rotate] reports root does not exist; nothing to rotate")
        return 0

    try:
        children = list(root.iterdir())
    except OSError as exc:
        print(f"[rotate] cannot list {root}: {exc}", file=sys.stderr)
        return 2

    matched: list[Path] = []
    for c in children:
        try:
            if c.is_dir() and _RUN_ID_RE.match(c.name):
                matched.append(c)
        except OSError:
            continue

    matched.sort(key=lambda p: p.name, reverse=True)  # newest first
    print(f"[rotate] matched run dirs: {len(matched)}")

    if len(matched) <= limit:
        print(f"[rotate] within limit; nothing to remove")
        return 0

    keep = matched[:limit]
    purge = matched[limit:]
    print(f"[rotate] keep (newest {len(keep)}): "
          f"{keep[0].name} ... {keep[-1].name}")
    print(f"[rotate] purge (oldest {len(purge)}): "
          f"{purge[0].name} ... {purge[-1].name}")

    if dry_run:
        print(f"[rotate] DRY RUN — no deletions performed")
        for p in purge:
            print(f"[rotate] would remove: {p}")
        return 0

    removed = 0
    failed = 0
    for p in purge:
        try:
            # Defensive: confirm the path is still inside `root`
            # and still matches the regex before delete.
            if not str(p.resolve()).startswith(str(root.resolve())):
                print(f"[rotate] skip out-of-root: {p}", file=sys.stderr)
                continue
            if not _RUN_ID_RE.match(p.name):
                print(f"[rotate] skip non-run: {p}", file=sys.stderr)
                continue
            _shutil.rmtree(p)
            print(f"[rotate] removed: {p}")
            removed += 1
        except OSError as exc:
            print(f"[rotate] failed to remove {p}: {exc}", file=sys.stderr)
            failed += 1

    print(f"[rotate] done. kept {len(keep)}, removed {removed}"
          + (f", failed {failed}" if failed else ""))
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
