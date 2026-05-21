# Operator Notifications — Passive Templates

This document defines **when** to notify the operator of an acceptance
issue and **how** the notification should be composed. The harness
itself does not send notifications — Phase 5D is intentionally
documentation-only. No SMTP server, no Slack webhook, no SMS gateway,
no third-party SDK is wired in.

> **Path note.** The Phase 5D instruction referenced
> `backend/acceptance/notification_templates/`. Per Phase 1's path
> adaptation, no `backend/` directory exists; backend modules live at
> the repo root. The templates therefore live at
> `tests/acceptance/notification_templates/` (subdir of an existing
> top-level path), keeping notification artefacts colocated with the
> rest of the acceptance harness.

---

## When to notify

The harness produces machine-readable `report.json` and the dashboard
exposes `/founder/acceptance/{incidents,runs/recent,stability/curve}`.
A notification fires when an external observer (CI step, manual op
script, dashboard polling job — operator's choice of trigger) reads
those artefacts and detects a condition below.

| condition | severity | template |
|---|---|---|
| any P0 incident posted via `POST /founder/acceptance/incidents` | P0 | `p0_failure.txt` |
| `report.json::pass == false` for any scenario marked `vault isolation breach` | P0 | `p0_failure.txt` |
| `compute_stability_curve.summary.monotonicity_pass_rate` drops below 0.95 over the last 10 runs | P1 | `monotonicity_break.txt` |
| any single run shows `monotonicity_pass: false` in scenario 05 | P1 | `monotonicity_break.txt` |
| `compute_timing_drift.drift_pct > +0.30` ("severe slowdown") | P1 | `timing_drift.txt` |
| `compute_timing_drift.drift_pct` between +0.15 and +0.30 ("meaningful slowdown") sustained for 5+ runs | P2 | `timing_drift.txt` |

A notification does NOT fire for:
- normal jitter (`drift_pct ≤ 0.05`)
- improvement (`drift_pct < -0.05`)
- a single P3 incident (those are tracked, not announced)
- selector-drift fixes (P2.1) — operator handles inline

---

## How to notify (documented only)

The harness deliberately does not implement sending. Three options the
operator can wire externally:

### Email (operator wires via CI or local mail relay)

- Source: a CI step or a local `mail`-equivalent script.
- To: a static recipient list under operator control.
- Subject: `[ClarityOS acceptance] <severity> — <short title>`
- Body: rendered template (see `notification_templates/`).

The harness produces no MIME envelopes, no SMTP credentials, no
sendmail invocations.

### Slack (operator wires via webhook URL)

- Source: a CI step posting to an incoming-webhook URL.
- The webhook URL is operator-managed (env var or repo secret).
- Body: JSON `{ "text": "<rendered template>" }`.

The harness contains no webhook URL and posts nothing.

### SMS (operator wires via paging service)

- Source: a paging service like PagerDuty / Opsgenie.
- The paging service polls `/founder/acceptance/incidents?open_only=true`
  on its own cadence and pages on non-empty results.
- Body: rendered template, length-trimmed for SMS.

The harness ships no integration with any paging service.

---

## Template invariants

All three templates share these rules:

1. **Plain text only.** No markdown, no HTML, no MIME multipart.
2. **Placeholders use `{{snake_case}}` syntax.** Substitution is the
   responsibility of the wire-up layer (CI step, helper script);
   templates carry no rendering code.
3. **No PII leakage.** Templates never include vault contents,
   operator email addresses, or session tokens. Only run ids, scenario
   ids, surface names, OS names, and numeric metrics.
4. **Self-contained.** Each template carries enough context that the
   recipient can act without opening the dashboard, but with a clear
   pointer to the dashboard for follow-up.

---

## Files

The three templates live at:

```
tests/acceptance/notification_templates/
├── p0_failure.txt          — vault isolation, total outage, data loss
├── timing_drift.txt        — sustained drift across the stability curve
└── monotonicity_break.txt  — scenario 05 monotonicity failure
```

Each template's content is a fixed string with `{{placeholder}}`
markers. See the files themselves for the canonical content; the
sections below describe each one's intent and its placeholders.

### `p0_failure.txt`

**Trigger:** P0 condition detected.

**Placeholders:**
- `{{run_id}}` — the run that surfaced the failure
- `{{detected_at}}` — ISO 8601 UTC timestamp the observer detected it
- `{{scenario}}` — scenario id (e.g., `03_two_operators_concurrent`)
- `{{severity}}` — `P0`
- `{{surface}}` — `web` / `phone` / `desktop` / `backend`
- `{{title}}` — short human title (e.g., "vault isolation breach")
- `{{detail}}` — first ~400 chars of the failing message
- `{{dashboard_url}}` — `<base>/founder/acceptance`

### `timing_drift.txt`

**Trigger:** drift_pct > +0.15 sustained, or > +0.30 single observation.

**Placeholders:**
- `{{detected_at}}`
- `{{drift_pct}}` — formatted percent (e.g., `+24.5%`)
- `{{interpretation}}` — `mild drift` / `meaningful slowdown` / `severe slowdown`
- `{{baseline_ms}}` — formatted ms (e.g., `91200`)
- `{{current_ms}}`
- `{{n_runs}}` — runs included in the comparison
- `{{slope_ms_per_run}}` — ms per run (signed)
- `{{dashboard_url}}` — `<base>/founder/acceptance/curve`

### `monotonicity_break.txt`

**Trigger:** any scenario-05 record with `monotonicity_pass: false`,
OR pass rate over the last 10 runs falling below 0.95.

**Placeholders:**
- `{{detected_at}}`
- `{{run_id}}`
- `{{iteration_n}}` — failing iteration index (1-based)
- `{{count_at_n}}` — artifact count at the failing iteration
- `{{count_at_n_minus_1}}` — artifact count at the previous iteration
- `{{pass_rate_last_10}}` — formatted percent over the last 10 runs
- `{{dashboard_url}}` — `<base>/founder/acceptance/curve`

---

## Anti-execution boundary

This document and the three template files are passive artefacts.
Materialization wrote no SMTP envelopes, hit no webhooks, and posted
no incidents. Notification sending is wired by the operator outside
the harness.
