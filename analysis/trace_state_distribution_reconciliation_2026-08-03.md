# Trace: state-distribution reconciliation — 2026-08-03 ~17:10 EDT
**v2 · 2026-08-04 ~15:50 EDT — correction pass (pen-authorized).** Changes: τ
restatement (Finding: no τ exists) · band figures clarified (measured vs analytic) ·
citations re-anchored to symbols @pin · lexicon-hit addendum · wave-layer verdict ·
causal-chain delta candidate. v1 content preserved unless explicitly corrected.

Lanes: COW-1 (derivation, forward + backward) · K3 (verification, empirical probe).
Classification: **WIRE** — reference mismatch between probability-scale inputs and
softmax-expecting-logits. Both ends individually sound; the interface between them
is wrong.

## COW-1 derivation (verified)

Forward: `_count_matches` → raw/4.0 clipped [0,1] → `score_S1..S4` (products of [0,1]
factors; S4 has four factors) → softmax over raw scores (`compute_state_distribution`,
`elins_v2_view.py` @ae221b6). Backward: thresholds 0.25/0.40, `COLLAPSE_WEIGHTS`,
P0–P8 = resolution × timescale (`compute_p0_p8` @ae221b6).

**Core finding:** softmax expects unbounded logits; it receives [0,1]-bounded
products. Output structurally compressed near uniform; thresholds were calibrated on
a [0,1] scale for a variable that cannot occupy it.

**Null derivation (all-zero input):** dist 25/25/25/25 → attractor S1 (state-order
tiebreak) → s4=0.25 ≥ `S4_SOFT_THRESHOLD=0.25` → `collapse_state="soft"` → c_w=0.5 →
raw_peaceful=.375, raw_contested=.250, raw_ruptured=.500 → resolution
.3333/.2222/.4444; etf=0 → timescale near=1.0 → **P0=33, P3=22, P6=44, rest 0**.

## K3 verification (empirical)

1. **Null panel: byte-exact.** `generate_ELINS` + `build_v2_envelope` on
   lexicon-miss text: `P0=0.333333, P3=0.222222, P6=0.444444`, all others 0,
   `collapse_state="soft"`.
2. **Band: two figures, keep them straight.**
   - **Measured (200k random intensity profiles): ≈ [0.147, 0.465].** This is the
     operative band — the four scores share factors, and correlation pushes corners
     past the independent-factor idealization (measured S1/S2 lo ≈ 0.147).
   - **Analytic independent-factor bound: [0.17488, 0.47536]** (= 1/(e+3), e/(e+3)).
     Clean closed form, but *narrower than reality* — v1 of this doc already flagged
     it as slightly off. **Correction registered 08-04:** COW-1 asserted this
     analytic bound as "the" band and K3 accepted it into boot.sys v1.2 against
     this document's own measurement. The measured band is authoritative.
   Direction (either figure): the distribution can never be decisive.
3. **Hard collapse reachability: 17 / 200,000** random profiles crossed
   dist_S4 ≥ 0.40 — random sampling overstates reachability (lexicon intensities
   are sparse and correlated). "Practically unreachable" confirmed.
4. **Corner probe (p=dr=cn=1, al=0, tr=0):** S4 maxes at **0.3655** — maximal
   catastrophe with no trust cannot cross 0.40.

## τ restatement (08-04 correction — supersedes v1's "τ recalibration" language)

**There is no τ.** `compute_state_distribution` computes `math.exp(v)` directly on
raw scores; τ appears only in comments (`elins_v2_view.py:25,168`). The docstring's
"Softmax with τ = 1.0 (locked)" describes the *absence of a divisor*, read by two
lanes (COW-1, K3) as a knob. **Consequence for the fix:** "retune τ" means
*introducing* a temperature parameter that does not exist, then recalibrating every
downstream threshold — not a one-line constant change. The (a)/(b) fork (feed
ratio-form magnitudes vs repair the [0,1]-product domain) re-prices accordingly;
(b) remains smaller than (a) but is a design change, not a tweak.

## New consequence (K3, beyond COW-1's three)

**The hard threshold has an inverted trust dependence.** With p≈1, al≈0, the only
competitor to S4 is `s3 = p·(1-al)·(1-tr)`. Suppressing it requires `tr ≈ 1`. So
`collapse_state="hard"` is reachable only by a profile of **saturated trust, zero
alignment, maximum pressure/drift/contradiction** — the system declares hard
collapse only for a *trusting* subject. The two thresholds sit at the two ends of
the reachable band: soft fires at the floor (always, on null), hard fires
effectively never. The classifier is saturated at both ends.

Also noted: null input → timescale near=1.0 (etf=0) — zero-evidence readings are
maximally *urgent* as well as maximally *ruptured*.

## Addendum 1 · First lexicon-hit observation (2026-08-04 ~08:31 EDT)

Six prior observations were lexicon-miss → uniform → derived constants. The seventh
(seed: technical dispute, conflict vocabulary present):

```
S1 23 · S2 23 · S3 30 · S4 23   attractor: S3 pressured incoherence
P0 12 · P1 23 · P2 1 · P3 14    collapse_state: none
```

- **Arithmetic verified by both lanes independently.** Forward from displayed
  dist with c_w=0: resolution contested = 0.4192 (COW-1: 0.419); panel reproduced
  within display rounding; timescale .333/.639/.028 ⟹ etf_agg_365 = 0.667,
  etf_agg_3650 = 0.028 — the point mass at near=1.0 is gone.
- **Knife-edge demonstrated from both sides:** uniform (s4=0.25) fires `soft`
  (≥); s4=0.23 does not. The threshold is parked on the noise floor.
- **Compression intact on a hit:** spread ≈ 0.067-0.070 against measured band
  width ≈ 0.318 → **~21-22% of available band on genuinely conflict-laden input.**
- **Correction to yesterday's "unresponsive":** the panel is responsive but
  **domain-conditional** — it moves when the lexicon matches. Fix implication:
  lexicon coverage is the first-order repair; gating is not.

## Addendum 2 · Wave-layer verdict (2026-08-04 ~09:12 EDT)

The wave/bond diagram's numeric substrate is this band-locked engine. A four-state
variable confined to the measured band has a **stddev ceiling ≈ 0.15**; observed
spread uses under a quarter of it. `Amp` would inherit a known false ceiling on
variance; `Harmony`/`BondCoeff` downstream would read manufactured calm as physics.
Fix order runs bottom-up: **lexicon → scale (now correctly priced) → Amp →
Harmony → ζ.** Diagram reality-pass findings (false-solid edges, `Corr` labels on
unbuilt nodes) recorded in the 08-04 session returns.

## Addendum 3 · First honest gradient candidate (2026-08-04 ~14:40 EDT)

`_layer_4_causal_chain` (`ELINS/standard_elins.py` @ae221b6) emits
`min(ia, ib)` over PRIMITIVE_KEYS declaration-order pairs — a co-occurrence floor
that discards magnitude and direction (docstring honest: "BOTH present"). The
one-line addition `"delta": round(ia - ib, 4)` yields a signed gradient in [-1,1]
with a **meaningful zero** — and the existing co-occurrence threshold (both ≥ 0.05)
already guards it: delta=0 can only mean balanced-by-evidence, never
balanced-by-miss. First quantity in the numeric path with a true origin. (Cousin:
`_layer_5_stress_relief`'s "balanced" bucket — a band around zero, not an origin.)

## Addendum 4 · Corner enumeration supersedes sampling (2026-08-04 ~16:00 EDT)

Claude's reflection (parse-vs-trace method regime) applied to this function, then
**K3-verified by exhaustive enumeration** (32 primitive corners, script this turn):

- The five scores are **multilinear** in (p, tr, dr, cn, al) — extrema live at
  corners. The corner set is finite (16 score vectors; 32 primitive corners), so
  enumeration, not sampling, is the correct method. Prior bands were samples:
  200k random profiles (interior) and the four one-hot corners (a subset).
- **True corner-extreme band: [0.13447, 0.47537]** = `1/(2+2e)`, `e/(e+3)`.
  Verified: min at primitives (p,tr,dr,cn,al) = (1,0,1,1,0) → scores (0,0,1,1);
  max at (0,1,0,0,1) → scores (1,0,0,0). The measured random-profile band
  [0.147, 0.465] sits strictly inside — interior sampling never reaches corners.
- **Only 6 of 16 score corners are reachable.** S1/S2 differ only by p vs (1−p);
  S2/S3 disagree on both al and tr. Ten corners are structurally impossible;
  only 6 distinct corner distributions exist at all.
- **Latent defect found by enumeration, invisible to sampling:** the uniform
  vertex 25/25/25/25 is produced by all-scores-zero (**19 primitive corners**,
  reachable — today's null-render) and would *also* be produced by all-scores-one
  (**0 primitive corners — structurally unreachable under product scoring**).
  Zero signal and maximum signal are softmax-identical. **Any future scoring-form
  change (e.g., the weighted-sum fix in §fix-ordering) that makes all-ones
  reachable renders "nothing is happening" indistinguishable from "everything is
  happening."** The weighted-sum fix must carry a guard for this before adoption.

Method note, adopted into doctrine: **parse samples because the space isn't
listable; trace enumerates because it is. Sampling a closed set is the defect.**
(Claude, 08-04; K3 verified the computation before banking — this addendum is
the verification record.)

## Fix ordering (re-priced 08-04)

1. **Pass 6 noise floor** — stops null/low-signal renders (floor analytically
   anchored: 1/4 = zero information in 4-state softmax).
2. **Lexicon coverage** — promoted by Addendum 1: the engine computes correctly
   when the lexicon matches; domain mismatch is the first-order defect.
3. **Scale fix** — introduce a temperature parameter (new) or logit-transform
   inputs, **plus** threshold recalibration against the achievable band —
   corner-enumerated **[0.13447, 0.47537]** (Addendum 4), with measured interior
   [0.147, 0.465] as corroboration. Design change, not a tweak. **New guard
   (Addendum 4): any scoring-form change must preserve distinguishability of
   zero-signal from max-signal — both are softmax-uniform.**

Consequence for the contract: row 3 (abstain floor) and Pass 6 block the floor
artifact; the scale mismatch is a separate defect class — **thresholds are policy
claims about a range the variable never occupies** — and needs its own row:
*threshold calibration must cite the achievable range of the variable it gates.*

## Corrections log (v2)

| # | Error | Correction |
|---|---|---|
| 1 | "τ recalibration" costed as one constant | No τ exists; comments only; fix = new parameter + recalibration |
| 2 | boot.sys v1.2 band cited as [0.17488, 0.47536] | Measured band [0.147, 0.465] is authoritative; analytic bound is the independent-factor idealization (v1.2 to be corrected) |
| 3 | "panel unresponsive" (08-03) | Responsive, domain-conditional (Addendum 1) |
| 4 | Measured band asserted "authoritative" (v2, same day) | Corner enumeration supersedes: true extremes [0.13447, 0.47537]; sampling a closed set was the defect — third band revision in one day, each by a better method (Addendum 4) |
