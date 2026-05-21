# Surfaces Unification Layer — Phase 10 Spec

A read-only coherence layer over the three ClarityOS surfaces. Adds no
state, no syncing, no cross-surface writes. Describes only.

---

## 1. Surface taxonomy

| surface | role | source |
|---|---|---|
| **PHONE** | Operator surface on iOS / Android (Expo). Personal mode, scenarios, ELINS feed, identity. | `phone/` |
| **WEB**   | Public + founder surface (Vite / React). Cockpit, ELINS, Founder console, dashboards. | `web/` |
| **OPERATOR** | Server-side runtime: ELINS pipeline, intelligence kernel, scheduler, vault, persistence. | `app.py` + ELINS + repo-root modules |

Each ingest record (`tests/acceptance/reports/acceptance_runs.jsonl`)
optionally carries a `surface` field identifying which surface produced
it. Records without a `surface` field are bucketed under `unknown` and
do not contribute to coherence comparisons.

---

## 2. Purpose of unification

The three surfaces operate independently. They share identity, trust
posture, run semantics, and telemetry, but each has its own runtime,
its own deployment cadence, and its own failure modes. Unification
gives the operator a single descriptive view that answers four
questions at once:

- Are all three surfaces active?
- Are they in the same trust posture?
- Are they running at coherent cadence?
- Is identity drifting between them?

The layer is **descriptive**. It does not enforce, gate, sync, or
correct. It surfaces deltas and lets the operator decide.

---

## 3. What unification DOES

- Reads the existing acceptance JSONL records.
- Buckets records by their declared `surface` field.
- Reports per-surface counts and last-run timestamps.
- Computes a single coherence score `0..100` from three signal deltas:
  timing, trust, identity.
- Returns the result as a static payload at
  `GET /founder/surfaces/unified`.
- Never modifies records. Never writes JSONL. Never alters per-surface
  state.

## 4. What unification does NOT do

- Does **NOT** sync records across surfaces.
- Does **NOT** merge records into a single canonical record.
- Does **NOT** rewrite the `surface` field on any record.
- Does **NOT** propagate state from one surface to another.
- Does **NOT** trigger any runtime action on any surface.
- Does **NOT** persist its own output. Each call recomputes from JSONL.

---

## 5. Example unification scenarios

### Scenario A — Three surfaces in lockstep

All three surfaces have ingested runs in the last 24h. Trust posture
is `stable` on all three. Identity coherence variance < 0.05 across
surfaces.

→ `coherence_score ≈ 95`. Interpretation: surfaces are operationally
unified; no delta worth investigating.

### Scenario B — Phone lagging

PHONE has not ingested a run in 72h while WEB and OPERATOR are active.
Trust signal on the recent surfaces is `stable`; PHONE's last record
shows `degrading`.

→ `coherence_score ≈ 55`. Interpretation: timing delta is the primary
contributor; PHONE may be offline or its acceptance harness has not
fired. Operator action: surface only, no automatic correction.

### Scenario C — Identity divergence

All three surfaces are active and recent. Trust posture is `stable`
on each. But the identity coherence score on OPERATOR diverges by
0.30 from PHONE and WEB (which agree).

→ `coherence_score ≈ 60`. Interpretation: identity drift between the
server-side pipeline and the user-facing surfaces — likely a fresh
deploy or a kernel-version skew. Operator reads the delta; layer does
not act.

---

## 6. Boundary contract

The unification layer is **read-only**. It is permitted to:

- read `acceptance_runs.jsonl`,
- read prior acceptance metrics (`run_quality`, `trust_center_math`,
  `identity_coherence`) only via their existing public functions,
- emit a JSON payload at the unification endpoint.

It is **NOT** permitted to:

- write to any vault snapshot,
- modify any acceptance record,
- emit any cross-surface signal,
- invoke any runner,
- trigger any scheduler tick.

A violation of this boundary is a regression — by Phase 10's design,
the unification layer is the safest possible read-only addition.

---

## 7. Future extension notes (Phase ≥ 12)

Phase 12+ may extend unification with:

- Per-surface drift trails (timeseries of coherence over rolling windows).
- A surface-level health card on `/founder/console` referencing the
  current coherence score.
- An export of the unification payload to the operator playbook for
  Fortune 500 review (already scaffolded under
  `tests/acceptance/operator_playbook_f500.md`).
- An optional alert posture that emits a notification (still passive)
  when coherence drops below a preregistered floor.

These are explicitly out of scope for Phase 10. Phase 10 is the
descriptive read-only floor; later phases may build on top, but must
preserve § 4's prohibitions.
