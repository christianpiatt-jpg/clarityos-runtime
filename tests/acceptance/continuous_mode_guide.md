# Continuous Mode — Operator Guide

End-to-end guide for running the acceptance harness on a continuous
cadence: scheduling, rotation, longitudinal inspection, drift
interpretation, dashboard verification, and escalation.

This is the Phase 5E document; it ties together the artefacts
materialized in Phases 1–5. Every command is operator-run.

---

## What "continuous mode" means

Continuous mode = the harness runs on a recurring cadence (cron, CI,
or a manual cycle the operator drives), each run produces one record
in `acceptance_runs.jsonl`, and the dashboard reads from that JSONL +
the recent run reports to surface trends.

The harness itself does not change between one-shot and continuous
modes — only the trigger does. There is no daemon, no scheduler, no
retry loop. The continuous loop is whatever invokes
`scripts/run_acceptance.sh` on schedule.

---

## How to schedule runs

Three operator-managed options. Pick one — they do not stack.

### Option A — cron (Linux / macOS)

Add to the operator's crontab (`crontab -e`):

```
# 05:00 UTC daily, fast mode, with rotation
0 5 * * * cd /path/to/clarityos_code \
  && bash scripts/run_acceptance.sh fast >> .acceptance.log 2>&1 \
  && python tests/acceptance/post_run_ingest.py \
       "$(ls -td tests/acceptance/reports/run-* | head -1)" \
  && python tests/acceptance/post_run_ingest.py --rotate
```

Notes:
- Backend must be running independently (cron does not start it).
- Confirm `npx`, `python`, `maestro` are on cron's PATH; cron's PATH is
  typically minimal — set it explicitly via a `PATH=...` line at the
  top of the crontab.
- `.acceptance.log` is the captured stdout/stderr; rotate it manually.

### Option B — GitHub Actions (CI)

The Phase 3B draft workflow at `tests/acceptance/ci/acceptance.yml` is
ready to migrate. See `tests/acceptance/ci_readme.md` for the
operator-only enable steps. Once active, GitHub triggers the run on
the cron / push / dispatch you configure; no cron entry needed.

### Option C — manual cycle

For pre-launch acceptance, an operator may simply run the harness on
their own cadence (e.g., once a day for a week, then once an hour
during the 72-hour stability window):

```
bash scripts/run_acceptance.sh fast
python tests/acceptance/post_run_ingest.py <new-run-dir>
```

This is the lowest-cost continuous mode and has no infrastructure
prerequisites.

---

## How to rotate runs

Rotation policy and procedure live in `run_rotation.md`. The default
is keep-last-50; override with `CLARITYOS_ACCEPTANCE_RETENTION`.

Recommended cadence:

- **Local dev:** rotate on every continuous tick.
- **CI:** rotate at the end of the workflow, after ingest.
- **Pre-launch / 72h stability window:** **disable rotation** for the
  duration of the window so all runs in the window remain inspectable.

Invocation:

```
# preview (no deletes)
python tests/acceptance/post_run_ingest.py --rotate --dry-run

# perform
python tests/acceptance/post_run_ingest.py --rotate
```

Rotation only affects per-run directories under
`tests/acceptance/reports/run-*/`. The longitudinal JSONL
(`acceptance_runs.jsonl`) is never rotated.

---

## How to inspect stability curves

After a few runs have been ingested:

1. Hit the curve endpoint:

   ```
   curl -fsS http://localhost:8000/founder/acceptance/stability/curve \
     | python -m json.tool | head -60
   ```

2. Open the web view:

   ```
   /founder/acceptance/curve
   /founder/acceptance/curve?verify=1   (with verification banner)
   ```

3. Read the response per `tests/acceptance/stability_curves.md`. The
   three blocks:

   | block | what it shows |
   |---|---|
   | `curve.points[]` | per-run mean / max / stddev / monotonicity |
   | `drift` | baseline vs current windows + linear slope |
   | `surface_health.scenario_health` | per-scenario pass rate + mean duration |

The math is computed by the three pure functions in
`stability_math.py` (repo root): `compute_stability_curve`,
`compute_timing_drift`, `compute_surface_health`.

---

## How to interpret drift

Quick-reference table (full version in `stability_curves.md` §
Timing drift thresholds):

| `drift_pct` | bucket | action |
|---|---|---|
| ≤ +0.05 | stable | no action |
| +0.05 to +0.15 | mild drift | track |
| +0.15 to +0.30 | meaningful slowdown | P2 |
| > +0.30 | severe slowdown | P1 |
| < −0.05 | improving | note, no action |

The `drift.interpretation` field carries the bucket name. Cross-check
the linear-regression `slope_ms_per_run` for the per-run trend — a
flat slope with a recent spike means the spike is the cause, while a
sustained positive slope means the system is gradually slowing.

---

## How to confirm dashboard correctness

Follow `tests/acceptance/dashboard_verification.md` end-to-end. The
six-step procedure walks:

1. `/runs/recent` direct hit
2. `/stability` direct hit
3. Web `runs?verify=1` view
4. Web `stability?verify=1` view
5. Metric interpretation
6. Optional onboarding-timing check

Phase 5C added a seventh endpoint: `/stability/curve`, surfaced at
`/founder/acceptance/curve`. Verify the same way:

```
curl -fsS http://localhost:8000/founder/acceptance/stability/curve | head
```

```
/founder/acceptance/curve?verify=1
```

---

## How to escalate P0 / P1 / P2

The harness does not auto-incident. The operator (or a watchdog
script) classifies and posts.

For each notification template, the trigger and target severity is
defined in `tests/acceptance/operator_notifications.md`. The three
templates:

| template | trigger | severity |
|---|---|---|
| `p0_failure.txt` | vault isolation, total outage, data loss | P0 |
| `timing_drift.txt` | drift > +15% sustained, or > +30% single | P1/P2 |
| `monotonicity_break.txt` | scenario 05 monotonicity_pass false, or pass rate < 0.95 | P1 |

To post an incident from a watchdog script:

```
curl -X POST http://localhost:8000/founder/acceptance/incidents \
  -H "Content-Type: application/json" \
  -d '{
        "severity": "P0",
        "surface": "web",
        "os": "macos",
        "title": "vault isolation breach in run-XXX",
        "detail": "scenario 03 reported shared ELINS keys"
      }'
```

The full failure-mode catalogue (symptoms, likely causes, operator
actions, non-action rules) lives in
`tests/acceptance/failure_modes.md`. Escalation is operator-managed.

---

## Continuous loop reference

The recommended continuous loop, once per tick:

```
1. bash scripts/run_acceptance.sh fast
2. python tests/acceptance/post_run_ingest.py "$(ls -td tests/acceptance/reports/run-* | head -1)"
3. python tests/acceptance/post_run_ingest.py --rotate          (skip during stability windows)
4. (optional) external watchdog reads /founder/acceptance/stability/curve
              and triggers operator_notifications.md flow when thresholds cross
```

Step 4 is not implemented by the harness. It is documented in
`operator_notifications.md` as a passive contract: any external system
that reads the dashboard can compose the templates with the live
metrics and dispatch via email / Slack / SMS at the operator's
discretion.

---

## Anti-execution boundaries

- Materialization (Phases 1–5) wrote no `.acceptance.log`, executed no
  `bash scripts/run_acceptance.sh`, posted no incidents, sent no
  notifications.
- The harness has no scheduler, no daemon, no retry loop.
- The continuous loop is whatever the operator wires (cron, CI, or a
  manual cycle). The harness simply produces well-shaped JSON whenever
  it is invoked.
- `--rotate` is opt-in and explicit; it never runs as part of an
  ingest invocation.
- Notification templates are passive text files with `{{placeholder}}`
  markers; the harness does not render or send them.

The continuous mode is therefore a property of the operator's
schedule, not a property of the harness.
