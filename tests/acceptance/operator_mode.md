# Operator Mode — Phase 11 Spec

A descriptive, non-executable layer that explains how the founder
should interpret system signals and maintain posture during runs.

Operator Mode is **not** automation. It is **not** a control plane.
It is a reading.

---

## 1. Definition

Operator Mode is composed of four disciplines:

1. **Posture** — a single label naming the operator's current
   interpretation stance (one of five).
2. **Interpretation discipline** — how telemetry / identity / trust
   signals are read into that posture.
3. **Movement discipline** — what kinds of operator actions are
   appropriate at each posture.
4. **Drift-avoidance discipline** — the rules that prevent the
   operator from sliding into a more permissive posture than the
   signals warrant.

The combined output of the four is a single read: *"given what the
system is telling me, this is the posture I should hold."*

---

## 2. The five postures

| posture       | meaning |
|---------------|---------|
| **steady**    | All signals nominal. Operator runs at normal cadence; no special action. |
| **cautious**  | One signal degraded but no failure. Operator slows cadence; reads more carefully; defers expansion. |
| **corrective**| A specific signal has failed in a way that has a known fix. Operator runs the fix; does not extend scope. |
| **degraded**  | Multiple signals failing or one critical signal failing without a known fix. Operator pauses new work; investigates. |
| **offline**   | Insufficient signal to read posture at all (no recent runs / records / telemetry). Operator restarts ingest; does not act on inference. |

A posture is always one label. There is no overlap. There is no
half-state. The combined signals collapse to exactly one of the five.

---

## 3. Mappings

Each mapping below produces a contributing posture vote. The final
posture is the **most degraded** vote across the three signals — the
spec deliberately biases toward conservative reading.

### 3.1 Telemetry → posture

| telemetry signal | posture |
|---|---|
| `trust_signal == "stable"` AND `drift == "stable"` | steady |
| `trust_signal == "degrading"` OR `drift == "drifting"` | cautious |
| `trust_signal == "critical"` AND a known recovery exists | corrective |
| `trust_signal == "critical"` with no known recovery | degraded |
| no telemetry payload available | offline |

### 3.2 Identity coherence → posture

| identity coherence | posture |
|---|---|
| coherence ≥ 0.80 | steady |
| 0.60 ≤ coherence < 0.80 | cautious |
| 0.40 ≤ coherence < 0.60 | corrective |
| coherence < 0.40 | degraded |
| no identity payload available | offline |

### 3.3 Run quality → posture

| run quality | posture |
|---|---|
| quality ≥ 0.80 AND `monotonicity_pass` AND `n_recent_runs ≥ 3` | steady |
| quality ≥ 0.60 OR a single failing scenario | cautious |
| quality between 0.40 and 0.60 with a clear failing scenario | corrective |
| quality < 0.40 | degraded |
| no quality payload available | offline |

### 3.4 Combination rule

Take the three votes; collapse to the most degraded:

`offline > degraded > corrective > cautious > steady`

If any signal votes `offline`, the combined posture is `offline`. The
operator never reads "steady" off a partial signal set.

---

## 4. Movement discipline (per posture)

| posture       | what the operator may do | what they should not do |
|---------------|--------------------------|-------------------------|
| **steady**    | Normal cadence. Add scope cautiously. | Skip a scheduled run because "things look fine." |
| **cautious**  | Read more carefully. Hold scope. Run an extra acceptance pass. | Expand scope. Sign off on a new feature. |
| **corrective**| Run the known fix. Document it. Verify quality recovers before next run. | Ignore the fix. Run new scenarios. |
| **degraded**  | Pause new work. Investigate root cause. Bring in the runbook. | Ship anything. Mark anything green. |
| **offline**   | Restart ingest. Verify the harness is firing. Do nothing else. | Read posture from cached records. |

---

## 5. Drift-avoidance discipline

The operator can drift into a more permissive posture in three ways:

1. **Cached signal drift** — reading posture from yesterday's records
   when today's are missing. Mitigation: a stale posture decays to
   `offline` after a preregistered window (default 24h since last
   record).
2. **Selective signal drift** — reading only the favorable signal and
   ignoring the others. Mitigation: the combination rule (§ 3.4) is
   non-overridable; all three must vote.
3. **Posture-of-convenience drift** — reading `steady` when the
   honest read is `cautious`. Mitigation: the spec is one-direction —
   when in doubt, hold the more degraded posture.

Drift-avoidance is the operator's responsibility. The layer surfaces
the read; it does not enforce.

---

## 6. Explicit boundaries

Operator Mode performs **NO**:

- automation,
- behavioral gating,
- prediction,
- enforcement,
- state changes,
- writes to vault,
- writes to acceptance records,
- side effects on any surface.

It only:

- reads existing records and existing pure-function signals,
- emits a posture label and the reasons that produced it,
- returns the result as a static payload at
  `GET /founder/operator/state`.

Each call recomputes from records. Nothing is persisted by Operator
Mode itself. The posture of last call has no effect on the posture of
this call.

---

## 7. Future extension notes (Phase ≥ 12)

Phase 12+ may add:

- Posture history (a passive timeseries of past postures).
- An optional notification when posture transitions across a boundary
  (e.g., `cautious → degraded`); still passive.
- An operator-acknowledgment field that the operator records by hand
  to mark "I read this posture and held it."

These are out of scope for Phase 11. Phase 11 is the descriptive
read-only floor for posture; later phases may build, but must
preserve § 6's boundary.
