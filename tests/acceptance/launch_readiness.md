# Launch Readiness — Phase 12 Spec

A read-only, founder-facing single-screen view that unifies six
dimensional signals into one readiness score for public launch.

This is **not** a marketing site. It is a founder-only diagnostic.
It does not gate a launch, schedule one, predict one, or notify
anyone. It surfaces the state and lets the operator decide.

---

## 1. Purpose

The operator approaches a public launch with multiple signals already
present in the system:

- stability of the underlying runtime,
- trust posture from the telemetry layer,
- identity coherence across surfaces,
- surface coherence (Phase 10),
- operator posture (Phase 11),
- run-quality trend over the recent record window.

Each of these has its own dashboard. None of them on its own answers
the question *"is the system in a state where I can ship?"*. Phase 12
gives the founder a single screen that does — descriptively, with no
automation behind it.

---

## 2. Readiness dimensions

| dimension | source | what it measures |
|---|---|---|
| **stability** | `stability_math` + `run_quality` | Are runs producing monotone, low-variance results? |
| **trust** | `trust_center_math` | Is the trust signal stable, degrading, or critical? |
| **identity coherence** | `identity_engine` | Do surfaces agree on the operator's identity profile? |
| **surface coherence** | `surfaces_unification` | Are PHONE / WEB / OPERATOR aligned in cadence and posture? |
| **operator posture** | `operator_mode` | What posture should the operator hold given current signals? |
| **run quality trend** | `run_quality.score_series` | Is per-run quality holding or drifting downward? |

Each dimension contributes a per-dimension `0..1` sub-score. The
combined `readiness_score` is a weighted average mapped to `0..100`.

---

## 3. Readiness scoring bands

| band | range | meaning |
|---|---|---|
| **green** | `readiness_score >= 80` | All six dimensions nominal; operator may proceed with a public launch decision under their own discretion. |
| **yellow** | `50 <= readiness_score < 80` | One or more dimensions degraded. Operator should review the contributing signal(s) before deciding. |
| **red** | `readiness_score < 50` | Multiple dimensions degraded or one critical signal failing. Operator should hold and investigate. |

The bands are **descriptive labels**, not gates. A red readiness does
not block a launch in any code path; it simply tells the operator
that the descriptive read is hostile.

---

## 4. Explicit boundaries

Phase 12 performs **NO**:

- automation,
- gating of launches or runs,
- prediction of future readiness,
- scheduling of any kind,
- notifications,
- writes to vault, JSONL, or any persisted artefact,
- side effects on any surface.

It only:

- reads existing acceptance records,
- composes results from existing sibling modules via their public
  functions,
- emits a single payload at `GET /founder/launch/readiness`.

Each call recomputes from records. The Phase 12 layer holds no state
of its own.

---

## 5. Example readiness profiles

### Profile A — green, all dimensions nominal

- stability: monotone curve, no drift, n_runs ≥ 3.
- trust: `signal=stable`, drift=stable.
- identity: coherence ≥ 0.85 across surfaces.
- surface coherence: ≥ 90.
- operator posture: `steady`.
- run quality trend: avg ≥ 80, no negative slope.

→ `readiness_score ≈ 90`. Band: **green**. Notes: empty.

### Profile B — yellow, one dimension degraded

- stability: monotone curve.
- trust: `signal=degrading`, drift=stable.
- identity: coherence 0.78.
- surface coherence: 65.
- operator posture: `cautious`.
- run quality trend: avg 70, slight downward slope.

→ `readiness_score ≈ 65`. Band: **yellow**. Notes: trust degrading;
surface coherence below 80; operator posture cautious.

### Profile C — red, multiple dimensions degraded

- stability: non-monotone, n_runs_with_stability < 3.
- trust: `signal=critical`, drift=drifting.
- identity: coherence 0.40.
- surface coherence: 25.
- operator posture: `degraded`.
- run quality trend: avg 35.

→ `readiness_score ≈ 30`. Band: **red**. Notes: every dimension
contributing degradation; operator should hold.

---

## 6. Future extension notes (Phase ≥ 14)

Phase 14+ may extend launch readiness with:

- A passive timeseries of readiness scores over a rolling window
  (read-only history; no predictive model).
- A "what would change to reach green" advisory that points at the
  weakest dimension; descriptive only, not prescriptive.
- An exportable readiness snapshot for the operator playbook (already
  scaffolded under `tests/acceptance/operator_playbook_f500.md`).
- An optional notification when readiness transitions across a band
  boundary; still passive, no automation.

These are out of scope for Phase 12. Phase 12 is the descriptive
read-only floor for launch posture; later phases may build on top, but
must preserve § 4's prohibitions.
