# Floating Geometry — Lineage Map · 2026-08-04
**Status:** Corr'd against source documents at pin `ae221b6`. Banked by K3 at pen's order.
RFI status: 1-3 RESOLVED (negative) by ET-1 return ~15:30 EDT, folded below with one
factual correction to that return; RFI 4 open. This is v0.2.

**Corpus:** nine documents in `source_docs\floating_geometry_2026-08-04\` (v2_Godhard Curve
Integration · v2_Individual_Learning · v2_Individual_Support · v2_Multi-Agent Individual
Support · PATTERN EVALUATION PROTOCOL · DYNAMIC PRESSURE MAP · Hydronic CI · Universal
Primitive–Geometry · CROSSREGRESSION_analytic). Read structurally + targeted greps;
not cover-to-cover (see Missing Middle).

---

## 1 · The method as the documents specify it

1. **State vector** — `SystemState` (`v2_Individual_Support.txt:33-37`):
   `pressure` P(t) force per unit capacity [0-10] · `margin` M(t) distance to failure
   [0-10] · `temperature` T(t) internal agitation [0-10] · `drift` D(t) cumulative
   displacement [-5,+5] · `escalation_risk` E(t) proximity to critical point [0-1].
2. **Derived strain** (`v2_Individual_Support.txt:47-69`):
   `fragility = 10 − margin`;
   `base_strain = 0.3P + 0.25·fragility + 0.2T + 0.15|D| + 0.1·(10E)` — weights sum to 1.0;
   `strain = min(10, base_strain × (1 + pressure·fragility/100))` — **one** coupling
   multiplier. Sums preserve range by construction; the single product carries all
   nonlinearity.
3. **The floating geometry** (`v2_Godhard Curve Integration.txt:70-98`): cusp potential
   `V(x) = x⁴/4 − (margin/10)·x²/2 − (pressure/10)·x`. The surface **deforms as pressure
   and margin change** — the landscape moves under the point. Equilibria found
   numerically, stability classified, hysteresis + resilience computed
   (`GodhardCurve`, `GodhardAwareSystemState :307`, `GodhardDynamicsEngine :365`).
4. **The observer** (`v2_Individual_Support.txt:424-473`): Bayesian filter over noisy
   partial measurements; `observability: float = 0.7` and per-field `measurement_noise`
   are first-class state fields (`:44-45`). Provenance was designed in from the start.

## 2 · Two lineages, not one

| | primitives | overlap |
|---|---|---|
| `SystemState` (source) | pressure · margin · temperature · drift · escalation_risk | pressure, drift |
| `_PRIMITIVE_LEXICON` (`ELINS/standard_elins.py:62-69`) | pressure · tension · trust · drift · contradiction · alignment | **2 words** |

Not degradation from a common root — a different model that borrowed terminology.
**Open:** whether the six map onto the five under renamed semantics
(tension→temperature, contradiction→escalation_risk). RFI 4.

**What ELINS dropped:** `margin` — the denominator. Source doctrine: *pressure alone
doesn't hurt you; pressure with no margin does.* ELINS's `intensity: high` is high
relative to nothing; the source says high relative to remaining capacity.

**What ELINS changed structurally:** the source never multiplies primitives (weighted
sum + one coupling term). ELINS's `score_S4 = p·dr·(1−al)·cn` is four bare products —
the compression defect (band [0.17488, 0.47536]) with the intended form present in the
lineage.

## 3 · engine_v1 = doc 4 (Godhard), partially implemented

- `engine_v1.py:10` docstring self-identifies: "Godhard Curve Integration."
- Constants `GODHARD_CENTER/HALF_WIDTH/LOWER/UPPER` at `:36-39`; `compute_overlay`
  at `:126-145` derives fold distance, critical-zone membership, branch from live
  primitives. **Implemented, not referenced.** (Constant-by-constant correspondence
  with the doc: attested by COW-1, 4-for-4; not re-derived here.)
- Corollary already registered: deprecating engine_v1 orphans the only implemented
  slice of the manifold-physics vocabulary.

## 4 · The open sensor port — the finding inside the corpus

`observe()` takes `noisy_measurements: Dict[str, float]` **as given**
(`v2_Individual_Support.txt:432-446`). Nothing in the nine documents maps text,
self-report, or behavior into P/M/T/D/E values. **The words→magnitude gap predates
ELINS: the original design is a dynamics engine whose sensors were never specified.**

**Inherited trap:** missing measurements default to **mid-scale 5.0**
(`:442-446`: `noisy_measurements.get('pressure', 5.0)` etc.). Absent data renders as
"average" — the forced-choice disease at the sensor port, in the source lineage.
Any adoption must replace the default with a declared null.

## 5 · RFIs — INFLIGHT at banking

1. The document containing `OrganizationalState` / `phase_coherence` /
   `alignment_score` / `DECOHERENT` (COW-1's "doc 6"). ~~Zero hits across this corpus —
   unverified citation until produced.~~ **RESOLVED (positive) 08-04 15:46 EDT — doc
   produced: `v2_ Organizational Godhard Mapping.pdf`. See resolution block below.**
2. Any document/script that ever produced P/M/T/D/E values from real input. If none:
   the measurement model was never written, and structured intake is the original
   design's missing half, not a new invention.
3. Whether any of this ran on real data (example values at
   `v2_Individual_Support.txt:698, :773, :801` look simulated). Decides revive-tested
   vs adopt-untested.
4. The lineage break: who reduced SystemState(5) → ELINS(6), and whether renaming was
   intended mapping or independent invention. Decides degraded-fork (recoverable
   semantics) vs separate-model (translation needed). **STILL OPEN.**

### RFI resolutions — ET-1 return 2026-08-04 ~15:30 EDT, folded by K3

**RFI 1 — RESOLVED (negative), then RE-RESOLVED (positive) 2026-08-04 15:46 EDT.**
ET-1's repo-wide search was correct *as far as it ran*: `OrganizationalState`,
`phase_coherence`, `DECOHERENT` appear nowhere in the repo or the then-banked corpus.
But the conditional retirement ("retired unless the source document is produced")
did its job — **pen produced the source**: `v2_ Organizational Godhard Mapping.pdf`
(15 pp, extracted to `…_extracted.txt`, 33k chars, now banked in
`source_docs/floating_geometry_2026-08-04/`). K3 grep-verified: `DECOHERENT` :40
("Anti-correlated (canceling out)"), `class OrganizationalState` :42,
`phase_coherence` :64 ("How synchronized are individuals"), `alignment_score` :65
("Goal/value alignment"), compute methods :268/:301. **Every element COW-1 claimed
exists. Registered: the doctrine (conditional retirement, not outright rejection)
is what kept this claim alive long enough to be confirmed.** ET-1's negative result
was accurate within its stated scope — the gap was corpus incompleteness (true set
~14 docs, not 9), which is exactly what COW-1's manifest check caught.

**RFI 2 — RESOLVED (negative).** Three SystemState instantiation sites, none from
real input: hand-assigned goal state (`:692-699`, K3-verified), dynamics evolution
(`:217`), dynamics derivation (`:466`). `observability: 0.7` is a default literal;
`measurement_noise` never populated. Confirms and sharpens §4: the system propagates
state and accepts targets; nothing lets it read the world.

**RFI 3 — RESOLVED (negative, within searched scope).** Values only ever
hand-assigned or simulated; no real-data run found. Adopt-untested, not revive-tested.

**Correction to ET-1's bonus finding:** "`source_docs/` is gitignored — .gitignore:136"
is **false at pin `ae221b6`**: line 136 is blank, the file ends at :139, and
`source_docs` / `analysis` / `snapshots` appear nowhere in it (K3, grep + direct read).
Consistent with `git status` showing `?? source_docs/` as untracked — ignored paths
never list. The durability exposure is REAL but the mechanism is **untracked, not
ignored**: this corpus and the workspace artifacts (`source_docs/`, `analysis/`,
`snapshots/`) are one `git clean -xdf` from gone until committed. ET-1's "third
instance" table stands for τ and hydronics; the SystemState row should read
"`.txt` in an untracked dir, not a module."

## 6 · COW-1 extraction — verification status

| Claim | Status |
|---|---|
| Two lineages, 2-word overlap | **confirmed** (field lists vs PRIMITIVE_KEYS) |
| margin/fragility/strain formulas | **confirmed verbatim** (`:47-69`) |
| weighted sums, one coupling multiplier | **confirmed** |
| observability 0.7 + measurement_noise | **confirmed** (`:44-45`) |
| engine_v1 = doc 4 implemented | **confirmed** (docstring + code; constants attested) |
| OrganizationalState phase_coherence in "doc 6" | **CONFIRMED** — doc produced 08-04 15:46 EDT (`v2_ Organizational Godhard Mapping.pdf`); `DECOHERENT` :40, `OrganizationalState` :42, `phase_coherence` :64, `alignment_score` :65, compute :268/:301. Conditional retirement worked as designed |

**Addendum 2026-08-04 15:46 EDT — corpus completion.** Four docs restored:
`v2_Universal Primitives Across Sc.txt` (doc 1 — the 9-primitive manifold
foundation; grep-verified: Reynolds :72/:90, entropy :251, scale-invariant
categories — **not yet read in full; lineage sections may need revision**),
`v2_Phenomenological Metadata Coll.txt` (**unread by any lane** — COW-1 flags
read-priority: its title intersects the observability/provenance hole this map
documents), `v2_Godhard Curve Integration.pdf`, `v2_ Organizational Godhard
Mapping.pdf` (RFI 1 source, above). True corpus ~14 docs; the "9-doc set" framing
elsewhere in this map is stale.

---

**MISSING MIDDLE**

**· Verified near end:** §1 formulas, state fields, observer structure, 5.0 defaults —
read directly this turn with line citations. Lineage overlap — field list vs
`PRIMITIVE_KEYS` read same day at pin.

**· Extensions past it:** documents read structurally + targeted greps (measure/observe/
sensor/estimate/infer/intake/elicit/self-report), not cover-to-cover; CI doc,
CROSSREGRESSION, Learning-doc Markov machinery surveyed-not-read. "No sensor
specification" = absence-within-corpus, not absence-in-the-world. Godhard constant
correspondence attested, not re-derived. Whether `compute_overlay` is called by any
live path — untraced.

**· Own-distortion check:** finding-scope held; every claim carries a line cite or an
attested/RFI tag. The strongest sentence ("sensors were never specified") is scoped to
the corpus and paired with RFI 2 by construction.
