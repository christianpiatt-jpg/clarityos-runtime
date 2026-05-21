# Acceptance Harness — Run Rotation & Retention

Operator-run policy and procedure for keeping the
`tests/acceptance/reports/` tree bounded as continuous runs accumulate.

> **Path note.** Phase 5A's instruction referenced `tests/acceptance/runs/`.
> Per Phase 1's path adaptation, run directories actually live at
> `tests/acceptance/reports/run-<UTC>-<hex>/`. Rotation therefore
> operates on that location. The longitudinal JSONL
> (`acceptance_runs.jsonl`) is **never** rotated — it is the
> append-only ledger.

---

## Default retention policy

| field | value |
|---|---|
| retention limit | **50 runs** (newest 50 directories kept) |
| sort key | directory name, descending (encodes UTC timestamp) |
| match pattern | `run-<8d>T<6d>Z-<4hex>` |
| deletion target | `tests/acceptance/reports/<dir>/` (recursive) |
| protected paths | `acceptance_runs.jsonl`, `expected_outputs/`, anything not matching the run-id pattern |

The limit is overridable per-invocation via the
`CLARITYOS_ACCEPTANCE_RETENTION` environment variable (positive integer).
Examples:

```
# default — keep 50
python tests/acceptance/post_run_ingest.py --rotate

# keep only the last 10 (e.g., on a small CI machine)
CLARITYOS_ACCEPTANCE_RETENTION=10 python tests/acceptance/post_run_ingest.py --rotate

# keep 200 (longer audit window for stability investigations)
CLARITYOS_ACCEPTANCE_RETENTION=200 python tests/acceptance/post_run_ingest.py --rotate
```

---

## Rotation algorithm

1. Resolve the reports root: `tests/acceptance/reports/` (override via
   `CLARITYOS_ACCEPTANCE_REPORTS`).
2. List its direct children. Filter to directory entries whose names
   match `^run-\d{8}T\d{6}Z-[0-9a-f]{4}$`. Anything else is skipped.
3. Sort the matched directories by name, descending. Because the run-id
   is `run-<UTC>-<hex>`, lexicographic descending == newest-first.
4. Determine the retention limit (default 50, env-override).
5. Take the slice `keep = matched[:limit]` and `purge = matched[limit:]`.
6. Print the plan: keep count, purge count, paths.
7. If `--dry-run` is also set: stop; do not delete.
8. Else: for each path in `purge`, recursively `rmtree` that path.
   On per-path failure, log the error and continue with the next.

**Safety boundaries:**

- The rotation function operates only on directories matching the
  run-id regex. A file named `acceptance_runs.jsonl` or a directory
  named `expected_outputs/` is excluded by construction (they don't
  match the regex).
- The rotation function never traverses outside
  `tests/acceptance/reports/`. All path operations are pinned to that
  root; symlinks pointing outside are not followed.
- `--rotate` does nothing automatically. The operator invokes it
  manually or in CI; there is no scheduler.

---

## Operator override rules

| situation | recommended retention | rationale |
|---|---|---|
| local dev (single operator) | 10–20 | prefer fast filesystem operations over deep audit |
| pre-launch acceptance | 100+ | preserve runs across the 72h stability window with margin |
| CI (cron-driven) | 50 (default) | enough for trend analysis without unbounded growth |
| forensic / incident review | rotation **disabled** during the investigation | preserve the offending run-id and its surrounding context |

To disable rotation entirely during an investigation, simply do not
invoke `--rotate`. There is no implicit rotation.

---

## Example rotation sequence

Starting state (62 runs accumulated):

```
tests/acceptance/reports/
├── acceptance_runs.jsonl              (preserved)
├── expected_outputs/                   (preserved by location)
├── run-20260501T100000Z-0001/         oldest
├── run-20260501T120000Z-0002/
├── ... 58 more dirs ...
├── run-20260520T090000Z-0061/
└── run-20260520T140000Z-0062/         newest
```

Operator invokes:

```
python tests/acceptance/post_run_ingest.py --rotate
```

With default retention = 50:

```
[rotate] reports root: tests/acceptance/reports/
[rotate] retention limit: 50
[rotate] matched run dirs: 62
[rotate] keep (newest 50): run-20260520T140000Z-0062 ... run-20260503T080000Z-0013
[rotate] purge (oldest 12): run-20260502T160000Z-0012 ... run-20260501T100000Z-0001
[rotate] removed: tests/acceptance/reports/run-20260501T100000Z-0001
[rotate] removed: tests/acceptance/reports/run-20260501T120000Z-0002
... 10 more ...
[rotate] done. kept 50, removed 12.
```

End state:

```
tests/acceptance/reports/
├── acceptance_runs.jsonl              (untouched; still has all 62 entries)
├── expected_outputs/                   (untouched)
├── run-20260503T080000Z-0013/         oldest now
├── ... 48 more dirs ...
└── run-20260520T140000Z-0062/         newest
```

The JSONL retains all 62 ingested entries. The dashboard's
`Recent runs` view reads from JSONL and is unaffected by rotation.
The dashboard's `Runs` (full-report) view will show 50 entries instead
of 62 going forward.

---

## Dry-run preview (recommended for first use)

```
python tests/acceptance/post_run_ingest.py --rotate --dry-run
```

Same plan output as above, but no deletes. Use this to confirm the
keep/purge split before committing.

---

## Integration with continuous mode

In a continuous loop (cron, CI, manual cycle), the typical sequence is:

```
1. bash scripts/run_acceptance.sh fast     # produces a new run dir
2. python tests/acceptance/post_run_ingest.py <new run dir>   # appends to JSONL
3. python tests/acceptance/post_run_ingest.py --rotate        # bound the dir tree
```

Step 3 should run after step 2 so the latest run is included in JSONL
before the directory becomes a candidate for rotation. (The JSONL is
the long-term store; per-run directories are the short-term cache of
full reports + logs.)

See `tests/acceptance/continuous_mode_guide.md` for the full continuous
loop and CI integration notes.

---

## Anti-execution boundary

This document describes operator-run procedures. Materialization wrote
no run directories, deleted no files, and did not invoke
`post_run_ingest.py --rotate`. Rotation is opt-in and explicit.
