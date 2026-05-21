# Operator Playbook — F500 Mode

How to run this acceptance harness inside a large organization.
Companion to the per-task documents materialized in Phases 1–8.

> **Anti-automation boundary.** This file describes operator posture,
> not CI/CD. It does not authorize automation, install software,
> launch services, or replace any document under
> `tests/acceptance/`. The harness is run by a human (or a CI job
> that a human owns) on an explicit cadence; this playbook describes
> *how* a Fortune-500-scale operator approaches that responsibility.

---

## What this harness is (one-page overview)

The acceptance harness is a deterministic, additive layer that runs
the ClarityOS surfaces through five scenarios on each invocation,
ingests the resulting `report.json` into a longitudinal JSONL, and
exposes the longitudinal data to a small set of founder-only views.
It is **not** a feature, **not** a customer surface, and **not** a
substitute for the v2.0 contract.

What the harness produces:

| artefact | location | purpose |
|---|---|---|
| per-run report | `tests/acceptance/reports/<run-id>/report.json` | full machine-readable output of one run |
| per-run markdown | `tests/acceptance/reports/<run-id>/report.md` | human summary of the same |
| longitudinal record | `tests/acceptance/reports/acceptance_runs.jsonl` | one line per ingested run, used by all dashboards |
| dashboards | web routes under `/founder/*` | read-only views of the JSONL and the run reports |

What the harness does **not** produce:

- It does not auto-incident.
- It does not auto-mail.
- It does not auto-page.
- It does not gate deploys (the operator does, by reading the
  dashboard before shipping).

---

## How to run it in a large org

F500 mode = the harness is exercised by multiple operators across
multiple environments, and the longitudinal record is preserved long
enough to survive turnover. Three working configurations:

### Configuration A — single owner, daily local run

For early-stage projects with one acceptance owner:

- The owner runs `bash scripts/run_acceptance.sh fast` once per
  workday and ingests the result.
- Rotation kept on (default 50). The longitudinal JSONL is the only
  permanent record.
- All escalations are personal: the owner reads the dashboard and
  files incidents themselves.

### Configuration B — paired ownership, CI + manual audit

For mid-stage projects with a primary + secondary acceptance owner:

- A CI workflow (per `tests/acceptance/ci_readme.md`) runs `fast`
  mode on push to main + nightly `full` mode.
- Primary owner reviews `/founder/console` daily.
- Secondary owner reviews on Mondays for a "fresh eyes" pass and
  files any incidents the primary missed.
- Rotation tightened to 100 to retain a longer audit window.

### Configuration C — F500 enterprise

For deployment inside a large organization where the harness is
operated as a quality gate by a dedicated reliability function:

- CI runs on a regular schedule per environment (dev / staging /
  pre-prod / prod-mirror). Each environment has its own
  `acceptance_runs.jsonl` (via per-env `CLARITYOS_ACCEPTANCE_REPORTS`
  override) so trend data does not bleed across.
- The reliability function maintains the `tests/acceptance/`
  documentation and reviews incidents weekly with the engineering
  organization.
- Rotation policy varies by environment: prod-mirror keeps 200+
  runs; dev keeps the default 50; pre-prod keeps 100 during the
  release window and reverts to 50 after.
- Cross-environment comparison is a manual exercise — the harness
  does not federate JSONL files. The reliability function maintains
  a local notebook that aggregates as needed.

In every configuration, **ownership is named**. There is no "the
team" owner. A single person is the on-call accepter for any given
window; rotation is a matter of named transitions, not implicit
silence.

---

## How to read the dashboards

The founder web routes form a hierarchy from general → specific.
Read top-to-bottom for a daily review:

| route | what to glance at |
|---|---|
| `/founder/console` | the four-widget summary; if all green, you're done |
| `/founder/acceptance` | open P0/P1 incidents + 72h stability window |
| `/founder/analytics/quality` | run-quality trend; look for `degrading` |
| `/founder/telemetry` | trust signal level; look for `critical` |
| `/founder/identity` | identity coherence; useful when something feels off but no specific metric is screaming |
| `/founder/acceptance/curve` | longitudinal stability curve; useful when investigating a slowdown |
| `/founder/acceptance/runs` | last N runs in a table; useful for forensic walks |
| `/founder/acceptance/stability` | aggregate monotonicity / timing; useful for trend reviews |

A typical daily glance at `/founder/console` is 30 seconds. A weekly
deep review walking the full hierarchy is 15 minutes. Beyond that,
you are debugging a specific incident, not reviewing.

---

## How to escalate

The harness does not auto-incident. Every P0/P1/P2 is filed by a
person via `POST /founder/acceptance/incidents`. The mapping:

| signal | severity | template (`tests/acceptance/notification_templates/`) |
|---|---|---|
| vault isolation breach (scenario 03 reports overlap) | **P0** | `p0_failure.txt` |
| backend unreachable for 5+ runs | **P0** | `p0_failure.txt` |
| Maestro CLI crash unrecoverable | **P0** | `p0_failure.txt` |
| scenario 05 monotonicity break (single run) | **P1** | `monotonicity_break.txt` |
| timing drift > +30% (severe) | **P1** | `timing_drift.txt` |
| timing drift +15% to +30% sustained 5+ runs | **P1** | `timing_drift.txt` |
| onboarding timing budget violation, reproducible | **P1** | (compose from `failure_modes.md`) |
| selector drift, scenario passes after fix | **P2** | (note in commit, no notification) |
| individual scenario flakiness < 10% rate | **P2** | track via dashboard, no incident |
| timing drift +5% to +15% | **P2** | (note via the timing_drift template, severity P2) |

The full failure-mode catalogue (symptoms, causes, actions,
non-action rules) is `tests/acceptance/failure_modes.md`. The
notification templates are passive plain-text files; rendering and
delivery are operator-wired.

---

## What "F500 readiness" specifically means here

| readiness check | how to verify |
|---|---|
| named ownership for every environment | the operator can answer "who runs this?" without consulting a wiki |
| documented escalation per severity | the team can point at `failure_modes.md` and `operator_notifications.md` and say "this is how we triage" |
| longitudinal data retained for ≥ 90 days in at least one environment | rotation set high enough; JSONL file size reviewed quarterly |
| cross-environment trend visibility (manual is fine) | a notebook or worksheet exists; not relying on dashboard memory |
| dashboards bookmarked in operator browsers | `/founder/console` has been seen by the on-call within the last 7 days |
| anti-automation boundary respected | no daemon was added; rotation is opt-in; no Slack/SMS/email is wired into the harness |

If any row is unchecked, the harness is not yet operating in F500
mode.

---

## What this playbook does NOT do

- It does not authorize CI/CD changes. The CI workflow is documented
  in `tests/acceptance/ci_readme.md` and is operator-enabled.
- It does not authorize new top-level directories or new
  architecture. The harness lives where it lives.
- It does not replace the v2.0 contract. The contract is the
  governing artefact for inferential claims; the harness produces
  evidence the contract reads.
- It does not provide runbooks for individual incidents. Per-incident
  triage lives in `failure_modes.md`.

---

## Quick references

| document | purpose |
|---|---|
| `README.md` | one-time setup |
| `runbook.md` | daily operations reference |
| `operator_run_instructions.md` | end-to-end procedure for a single run |
| `run_sequence_diagram.md` | what happens when the operator hits enter |
| `failure_modes.md` | P0/P1/P2 catalogue |
| `operator_notifications.md` | when/how to notify |
| `notification_templates/` | rendered text for the three notification kinds |
| `continuous_mode_guide.md` | how to schedule + rotate + interpret long-running data |
| `ingest_validation.md` | confirm `post_run_ingest.py` is wired correctly |
| `dashboard_verification.md` | confirm the dashboards are reading current data |
| `stability_curves.md` | longitudinal metric definitions |
| `run_quality.md` | per-run scoring rubric |
| `cadence_analysis.md` | run-spacing patterns |
| `trust_center_telemetry.md` | composite trust signal |
| `narrative_drift.md` | drift detection signals |
| `identity_coherence.md` | descriptive identity layer (Phase 8) |
| `operator_playbook_f500.md` | this file |
