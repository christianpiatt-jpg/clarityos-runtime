# PIS / PISS Dual-Surface Public Identity — Phase 13 Spec

A read-only, founder-facing identity layer that makes the distinction
between **PIS** (Personal Intelligence System) and **PISS** (Personal
Intelligence Surfaces Stack) explicit and operator-grade.

This is **not** marketing copy. It is an internal taxonomy that
explains what is internal vs external, stable vs evolvable, and how
the two halves relate.

---

## 1. Definitions

### PIS — Personal Intelligence System

The internal operating system of ClarityOS. Owns:

- the math (kernel, alternator, contracts, gates, scoring),
- the posture (operator mode, readiness, drift),
- the identity coherence layer (Phase 8),
- the trust signal (Phase 7),
- the stability and run-quality math (Phases 5–6),
- the vault and continuity layers,
- the runtime that produces every record.

PIS is **stable by design**. Its public functions are versioned;
amendments are additive (per the v1.0 / v1.1 / v2.0 contract series).
A change to PIS without a versioned amendment is a regression.

### PISS — Personal Intelligence Surfaces Stack

The external surface stack that consumes PIS outputs. Owns:

- web routes (`/founder/*`, public site),
- phone surfaces (Expo screens),
- desktop surfaces (initiator + GUI),
- chat surfaces,
- founder dashboards,
- the operator console and its sub-views.

PISS is **evolvable by design**. New routes, new screens, new gauges
ship without touching PIS internals. PISS reads PIS via the public
function surface; it never bypasses the contract.

---

## 2. What lives only in PIS

| layer | purpose | not visible to PISS except via API |
|---|---|---|
| Kernel (`analysis/physics/up_kernel_spec.md`) | UP^ operator definition + DV vector | yes |
| Contracts (`UP_M123_CONTRACT_v*.md`) | Inferential bars, gates A–F | yes |
| Alternator registry | Gated vs region vs library alts | yes |
| Permutation engine | Paired sign-flip nulls | yes |
| Vault snapshot store | Per-session state on disk | yes |
| Continuity reentry layer | `continuity_reentry.py` cold start | yes |
| Token taxonomy | `canonical_up_supported`, `modulation_robust`, etc. | yes |
| Runtime scheduler | Cadence + macro passes | yes |

PISS surfaces never read these directly. They consume their
descriptive outputs through the public function surface (e.g.,
`compute_trust_signal`, `summarize_operator_state`).

---

## 3. What lives only in PISS

| surface | role | not visible to PIS |
|---|---|---|
| `web/src/routes/Founder*.tsx` | Founder console + acceptance / telemetry / identity / surfaces / operator / launch / pis-piss views | yes |
| Phone Expo screens | Operator-facing personal mode | yes |
| Desktop initiator / UI / chat | Operator surfaces with continuity | yes |
| `?verify=1` banners | Verification annotation | yes |
| Inline SVG gauges | Visual rendering | yes |
| Layout, typography, spacing tokens | Visual identity | yes |

PIS is unaware of PISS. The internal math doesn't know which surface
will render its output, and never special-cases for one. This is the
load-bearing property: PISS can be replaced wholesale without
touching PIS.

---

## 4. What is shared

A small, deliberate set of concepts crosses the PIS/PISS boundary:

| concept | source of truth | observable in PISS |
|---|---|---|
| Telemetry | `trust_center_math` + `narrative_drift` | `/founder/telemetry` |
| Readiness | `launch_readiness.py` | `/founder/launch` |
| Posture | `operator_mode.py` | `/founder/operator` |
| Identity coherence | `identity_engine.py` | `/founder/identity` (Phase 8C) |
| Surface coherence | `surfaces_unification.py` | `/founder/surfaces` |

Shared concepts always travel **PIS → PISS**, never the reverse. PISS
does not write back into PIS state. PISS does not infer values that
PIS would not have produced. Shared concepts are descriptive labels
on PIS-computed numbers.

---

## 5. Three example operator views

### View A — "the math is healthy and the surfaces are aligned"

Operator opens `/founder/console` and sees green readiness, steady
posture, ≥ 80 surface coherence, identity coherence ≥ 0.85.

→ Read: PIS is producing nominal signal; PISS is reflecting it
faithfully. No action.

### View B — "the math is healthy but a surface is lagging"

Operator opens `/founder/surfaces` and sees PHONE last-run > 72h while
WEB and OPERATOR are recent. Trust on recent surfaces is `stable`.

→ Read: PIS is healthy; PISS-PHONE branch is offline or stale. The
fix is a PISS-side ingest reset, not a PIS amendment.

### View C — "a surface looks healthy but the math doesn't"

Operator opens `/founder/launch` and sees yellow readiness with
`trust=critical` and `identity_coherence=0.40` even though all three
surfaces show recent activity.

→ Read: PIS is degraded; PISS is faithfully showing the degradation.
The fix is upstream — investigate the runner / vault / kernel — not
"polish the dashboard". Operator holds at `degraded` posture per
Phase 11 § 4.

---

## 6. Explicit boundaries

This layer performs **NO**:

- user-level personalization,
- recommendations,
- ranking of surfaces,
- automation across the boundary,
- writes to vault / JSONL / records,
- modifications to PIS public functions,
- modifications to PISS routing.

It only:

- produces a static taxonomic description of the two halves,
- emits a single payload at the configured endpoint,
- supports the founder's mental model when reading the other
  dashboards.

The descriptions are deliberately stable. Adding a new component to
PIS or a new surface to PISS does not require a Phase 13 update — the
top-level taxonomy holds.

---

## 7. Future extension notes (Phase ≥ 15)

Phase 15+ may extend the PIS/PISS layer with:

- A diff view that highlights newly-added components in PIS or
  surfaces in PISS since a prior reference snapshot.
- A "PIS contract version table" listing every contract version + its
  scope of authority across the PIS surface.
- A cross-reference of PIS public functions to the PISS routes that
  consume them (passively read; not enforced).
- A phone-side or desktop-side mirror of the same payload, so the
  taxonomy is reachable from any surface, not just `/founder/*`.

These are out of scope for Phase 13. Phase 13 is the descriptive
read-only floor for PIS / PISS taxonomy; later phases may build on
top, but must preserve § 6's boundaries.
