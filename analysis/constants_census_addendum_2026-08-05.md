# Constants Census — Addendum · the responsive/static re-run

*2026-08-05 · K3 · pin `fa4fbf8` · triggered by Claude's filter correction (12:52 EDT),
applied with the adoption boundary named in the witness return. This amends the
12:39 census return, not the code.*

## The filter change (adopted)

The 12:39 census filtered on **declared vs undeclared** — locked policy constants were
excluded as "declared knobs with provenance." Claude's correction: provenance documents
a knob; it doesn't make it responsive. The right discriminator is **responsive vs
static**: a knob sits outside the flow (operator-set intent); a damper sits *in* the
flow and resists in proportion to what passes through it. A static element where a
responsive one belongs is the defect — wrong element *type*, not wrong value. No
amount of tuning `0.12` makes a knob into a damper.

**Adoption boundary:** the frame is adopted; the sweep ("the excluded 15 become the
first rows") is not. Applied strictly, the discriminator acquits or re-files most of
the 15 spec-lock literals. The net catch is **three rows**, one of which was never in
the excluded set at all.

## Finding 1 upgraded

`_layer_8_qc_self` (`standard_elins.py:334-349`) is not merely tautological — it is
**validator_overlap = 1.0** in code: the validator's input is entirely the producer's
input and its method is the producer's method (`:339` re-runs `_layer_1_primitives`
on the same text, deterministically). Previous census rows were *values that can't
move*; this is **a check that can't fail.** Same disease at the verification layer —
a new rung on the ladder. (Claude's restatement, verified in situ by K3.)

## The three rows (MMR four-field)

**A1 · `alpha = 0.2` EWMA — `ELINS/elins_project.py:263` (update_ep_baseline)**
- **What:** fixed exponential smoothing on the baseline that Lane 1's delta subtracts
  from (`ef0c19d`). Identical smoothing for a baseline built from 2 runs and one built
  from 200; ignores `sample_count` (stored at :291) and variance.
- **Why it matters:** the delta measures against a reference whose responsiveness is
  a set point. The system's first real measurement inherits a knob as its baseline.
  A baseline that should adapt to evidence volume is time-frozen instead.
- **Cost to close:** sample-count-aware alpha (e.g., alpha ∝ 1/(1+sample_count) or a
  variance-weighted rule) — small code change, but changes every baseline's meaning;
  needs a migration note, not just an edit.
- **Would it flip:** yes — deltas on thin histories currently move more than they
  should; on thick histories, less.

**A2 · Locked thresholds — re-filed as calibration, not responsiveness**
(`elins_v2_view.py:80-83, 89-91`)
- **What:** S4 hard/soft 0.40/0.25 · field-intensity 0.70 · trend 0.05 · tier
  boundaries 1.20/0.40/−0.20. Policy set points — static *by design*; intent-shaped.
- **Why it matters:** their defect is the already-named contract row — *threshold
  calibration must cite the achievable range of the variable it gates.* S4_HARD 0.40
  against the corner-enumerated max 0.47537 fires only near the (0,0,0,1) vertex;
  the tier boundaries against tier_score ∈ [−1, 2] are unverified.
- **Cost to close:** one achievable-range citation per threshold, anchored to the
  corner enumeration (trace doc Addendum 4) — documentation, not code.
- **Would it flip:** no — but it converts silent calibration risk into declared
  policy with a stated band.

**A3 · ETF λ block — ACQUITTED** (`elins_v2_view.py:73-77, 130-131`)
- **What:** `λ = base · (1 + α·ep0 − β·edge_count)`, clamped to [1e-4, 1e-2].
- **Why acquitted:** λ *responds* — decay slows with structural reinforcement
  (edge_count), quickens with intensity (ep0). That is a damper; the clamp is a
  travel limit, which dampers legitimately have. Recorded so the acquittal is
  auditable, not just the catches.
- **Would it flip:** no.

## Also acquitted (one line each)

Multiplier weights 0.4/0.3/0.3 + clamp (:94-100) — static coefficients inside a
formula that responds to fi, s4, c_w; the formula is the damper. COLLAPSE_WEIGHTS
(:86) — a category→number mapping, not a flow element.

## Previously banked, same frame

`cur − cur·0.12` (`standard_elins.py:295`, census finding 7) and
`RESISTANCE_GROWTH_PER_DAY` (`engine_v1.py:255`, 08-04 finding) are the same
element-type defect, already priced. This addendum gives them their reason.

---

**MISSING MIDDLE**

**· Verified near end:** all three rows' code read in situ this session at `fa4fbf8`
(:263/:291/:299-303 · :80-100 · :130-131); finding-1 upgrade verified against
:334-349. **· Extensions:** what alpha *should* be is a design judgment this census
deliberately doesn't make — the finding is staticness, not the replacement rule.
Whether `sample_count` is actually maintained on all write paths — not traced.
**· Own-distortion:** narrowing a praised correction risks reading as filter-defense;
the counterweight is that A1 *expands* the census into a file the dispatch didn't
name, and the acquittals were produced by the new frame, not the old one.
