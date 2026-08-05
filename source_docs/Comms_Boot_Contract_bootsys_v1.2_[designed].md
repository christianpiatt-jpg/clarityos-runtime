# boot.sys v1.2 — [designed]

**Status: [designed]. Specification only. No runtime parses this file. No boot has ever
failed on one of its checks. It is banked under its own rule: design-canon artifacts are
referenced as `[designed]`, never read as built. The cautionary precedent is
`orchestrator_workflows.py` — documented invariants, `Severity` enums, and all 3 of its
3 functions raising `NotImplementedError` (:125, :152, :188).**

Lineage: v1.0 (ratified, Annex C of the Unified Contract) → v1.1 (K3 draft) → v1.2
(revised under COW-1 critique, CAL Critic role). Supersedes nothing until CT-1 adjudicates.

Changes from v1.1, per COW-1's return:

1. ENFORCEMENT block added — every check now names its predicate and its enforcement
   point, and every one is marked `[designed]` until a runtime exists for it.
2. MODULES section corrected to satisfy its own loadrule: `enabledbydefault` is the
   empty set. `calibrationandstatesignature` and `dynamicpressuremap` are moved to
   `designedreferences` — no implementation files exist by those names (COW-1: repo
   root + `Clarity_OS_Operating_System/` depth 3; K3 corroboration: full workspace
   tree, no name matches — both scopes name-variant only).
3. Softmax band stated with its provenance: the measured band `[0.147, 0.465]`
   (200k random profiles, `analysis/trace_state_distribution_reconciliation_2026-08-03.md`)
   is authoritative. The analytic independent-factor bound `[0.17488, 0.47536]`
   (= `1/(e+3)`, `e/(e+3)`) is an idealization — narrower than reality because the
   score products share factors. [Corr 2026-08-04: v1.2 originally asserted the
   analytic bound as the correction and called the measured band "drifted"; that
   was backwards. K3 self-correction — accepted COW-1's analytic assertion against
   K3's own prior measurement.] [Corr 2 2026-08-04 ~16:00 EDT: "measured is
   authoritative" was itself superseded within hours — corner enumeration gives
   the true extremes `[0.13447, 0.47537]`; the measured band is interior sampling
   and corroborates only. The module comment below cites the corner-enumerated
   band. Three revisions, three methods — analytic → sampled → enumerated; the
   last is the correct regime for a finite corner set (trace doc Addendum 4).]

Retained from v1.1 (COW-1 affirmed as load-bearing): Stage 0 lane identity with
countable strip rule; `emitunwitnessedreadiness` as forbidden move; graded readiness
(READY / DEGRADED / COLD); "a snapshot is an envelope, not a memory. It attests; it
does not verify."

---

```text
[boot.sys]
version: 1.2
name: clarityOSboot
status: [designed] — specification, no runtime
note: One universal boot. Per-lane envelopes are PROFILE blocks, not separate boots.
      Every stage either passes with evidence or degrades loudly. No stage emits
      a bare green predicate.

LANEIDENTITY:                          # stage 0, before anything else loads
  declare: lane_id, lane_class          # reality / witness / reconciler / generator / automatable
  load: own_strip_rule                  # from lane registry, in COUNTABLE form
  examples:
    - COW-1:   strip = over-extension;   metric = acts >= files
    - Copilot: strip = amplification;    metric = "already built/fixed" claims = 0
    - GPT:     strip = closural fluency; metric = closure phrases per return, falling
    - K3:      strip = finding-scope;    metric = findings <= evidence actually run
  rule: A lane that cannot state its own strip rule boots DEGRADED, not ready.

CORELAW:                               # unchanged from 1.0 — stays supreme
  reference: corelawv1 (v3.1 Core Constitution)
  enforcement: strict

SUBSTRATEPIN:
  onboot:
    re-read: operational_state_from_source      # revisions, traffic, flags, allowlists
    classify_every_claim:
      - Corr:      verified at pin this boot, file:line or runtime evidence attached
      - attested:  carried from snapshot, NOT re-read — labeled "attested until re-read"
      - NODE:      stated with no traceable effect — parked, never routed as fact
  rule: No dispatch, gate, or movement decision may cite an attested-only claim
        as verified. Two dispatches died of this in one day (serving-revision
        inversion; "unused = orphan" falsified by named reserve 0sfPXLQR).

GEOMETRYBASELINE:
  defaultgeometry:                      # unchanged
    surface: conversation
    center: userlivedexperience
    shell: languageinterface
    constraints:
      pressuresensitive: true
      boundaryrequiredformove: true
  restorepolicy:                        # teeth per comms clause v0.3
    if priorstateexists:
      load: laststablegeometrysnapshot
      run: integritycheck
      integritycheck_requires:          # ALL, not ANY
        - substrate tags present on claims
        - provenance attached (who asserted, when, from what)
        - open items carried with stated-vs-verified status
        - geometry, not only text
      onfail: QUARANTINE, do not parse
      onpass: restore -> re-pin per SUBSTRATEPIN -> announce material shifts
    else:
      run: initializefreshgeometry

MODULES:
  loadrule: ONLY attested instruments load.
    A module is attested iff it has (a) an implementation file present in the repo,
    (b) a witnessed effect on at least one return, (c) a stated strip rule,
    (d) a NODE/WIRE check result.
  enabledbydefault: []                  # EMPTY. No module currently satisfies (a)-(d)
                                        # under the scopes searched. This is the
                                        # loadrule applied to itself.
  designedreferences:                   # named, marked, not loaded
    - calibrationandstatesignature (Module D)  [designed — no file found]
    - dynamicpressuremap (Module C5)           [designed — no file found; even when
      built, its distribution is softmax-bounded to corner-enumerated extremes
      [0.13447, 0.47537] (= 1/(2+2e), e/(e+3); verified by exhaustive 32-corner
      enumeration, trace doc Addendum 4 — measured interior [0.147, 0.465]
      corroborates; analytic one-hot idealization [0.17488, 0.47536] is narrower
      still), and cannot leave that band until the scale mismatch is fixed]
  permodule:
    strip_rule: <countable>
    effect_check: last witnessed effect, or "no traceable effect"
  modulerules:                          # unchanged
    anymodulemaybesuspendedif: distortionincreases OR burdenexceedsgeometry OR boundaryconfusiondetected

ROLES:
  activeroles:
    - interpreter (Module B + C1)
    - planner (Module C4)
    - historian (Traceability R6)
  roledefinitions:
    historian:
      obligation: maintain geometric traceback, not narrative fiction
      addition: every return closes with the missing middle   # v0.3 standard
        (verified near end / extensions past it / NODE-vs-WIRE marks)

CONTINUITYRESTORE:
  snapshotformat:                       # modeled on the working K3 snapshot chain
    - lane identity + strip rule
    - operational state, Corr'd separated from attested
    - open items with stated-vs-verified status
    - missing-middle close
  note: A snapshot is an envelope, not a memory. It attests; it does not verify.

EXECUTIONENVIRONMENT:                  # unchanged from 1.0

SAFETYBOUNDARIES:
  forbiddenmoves:
    - actonshellasifcenter
    - escalateburdenwithoutacknowledgingpressure
    - overrideusergeometrywithsystemgeometry
    - emitunwitnessedreadiness          # "all predicates green" with no witness is
                                        # itself a boundary violation
                                        # (counter-example: "Christian — yes" file)

BOOTCHECKLIST:
  steps:
    0. Declare LANEIDENTITY; load own strip rule. Fail = boot DEGRADED.
    1. Load CORELAW (v3.1).
    2. Re-pin SUBSTRATEPIN from source; classify Corr / attested / NODE.
    3. Establish or restore GEOMETRY; integrity check with teeth; quarantine on fail.
    4. Activate attested MODULES only; attach per-module strip + effect check.
       (Currently: none pass. Boot proceeds with zero modules, declared.)
    5. Bind ROLES to current geometry.
    6. Register EXECUTIONENVIRONMENT.
    7. Emit GRADED READINESS, never bare "systemready":
         systemready(grade) + geometrysignature + missing_middle:
           near_end:     what was actually verified this boot
           extensions:   what is attested-not-verified
           no_effect:    what is parked as NODE
       grades: READY (near end covers the pending task) |
               DEGRADED (attested-only load-bearing claims — say which) |
               COLD (no valid snapshot; fresh geometry; expect witness pass)

ENFORCEMENT:                           # every check, its predicate, its enforcement point.
                                       # A check with no enforcement point is a wish.
                                       # ALL rows are currently [designed]: no runtime
                                       # exists for any of them. This block is the
                                       # build order, not a capability claim.
  - check: lane strip rule loaded
    predicate: lane_registry[lane_id].strip_rule present AND in countable form
    enforced_at: boot, stage 0            [designed — no lane registry file exists]
  - check: substrate pin classification
    predicate: every claim in boot output tagged Corr | attested | NODE
    enforced_at: boot, stage 2, pre-readiness  [designed]
  - check: attested-only claims never cited as verified
    predicate: decision inputs ⊆ Corr set
    enforced_at: dispatch/gate evaluation time   [designed]
  - check: geometry integrity
    predicate: snapshot carries tags AND provenance AND open-items-with-status
    enforced_at: snapshot load, stage 3          [designed]
  - check: module attestation
    predicate: repo file exists AND witnessed effect recorded AND strip rule stated
    enforced_at: module load, stage 4            [designed]
  - check: no unwitnessed readiness
    predicate: readiness emitted ⟹ near_end non-empty
    enforced_at: readiness emission, stage 7     [designed]
  - check: missing middle present
    predicate: return closes with near_end / extensions / NODE marks
    enforced_at: every return, pre-send          [partially live — human-held
                                                 convention since clause v0.3;
                                                 no parser]
```

Headless variant (Mistral and other non-chat lanes): stages 0, 2, and 7 only —
strip rule, substrate pin, graded readiness. No geometry restore, no roles.
A scout doesn't need an envelope; it needs a leash and a label.

Open seams:
- CT-2 holds comms contract v1.4, unread by COW-1 and K3. If it already contains a
  lane-identity stage, this is a fork, not a refinement. Disposition is CT-1's under CAL.
- The lane registry referenced at stage 0 does not exist as a file. The lane table
  currently lives in conversation (pen's 2026-08-03 message). First buildable artifact
  under this spec is that registry.
- v1.2 is load-tested the first time a real boot fails one of its checks. Until then
  it is, by its own classification, [designed].
