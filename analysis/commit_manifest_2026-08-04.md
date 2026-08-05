# Commit Manifest — 2026-08-04 · for pen's execution
**Status:** proposed, [designed]. K3 stages; pen executes git. Nothing committed yet.
**Driver:** untracked ≠ ignored (ET-1's mechanism corrected) — the working record is one
`git clean` from gone; line-citation decay compounds every uncommitted hour.
**Pin:** `ae221b6` + working tree (kernel edit 106/8).

## C1 · The record — commit first (zero code risk)

| Path | Content | Size |
|---|---|---|
| `snapshots/` | K3 handoff restore points (12:56–22:10 08-03 chain + 0653 & **1637 EOD** 08-04) | 76K |
| `source_docs/` | doctrine (boot.sys v1.2 [designed] — band now corner-enumerated, ORI v0.1 [designed], **comms clause v0.3 + v0.4 answer-discipline amendment**, lane roster — K3 strip rule rewritten + method-regime rule) + source corpus (boot contract PDF, floating_geometry ~14-doc set — four docs restored 08-04 15:46 EDT; C1 hold lifted), mermaid maps, returns (incl. **pen+Claude "hat inverts" return, banked 16:12**) | 5.3M |
| `analysis/floating_geometry_lineage_2026-08-04.md` | lineage map v0.2 (**RFI 1 re-resolved POSITIVE** — doc 6 produced & grep-verified; corpus-completion addendum) | — |
| `analysis/trace_state_distribution_reconciliation_2026-08-03.md` | ±band trace **v2 + Addendum 4 (corner enumeration [0.13447, 0.47537], K3-verified; uniform-vertex latent defect; corrections log ×4)** | — |

**Decision flags inside C1:**
- Two Emotional Physics PDFs in `source_docs/mermaid_maps_2026-08-04/` (2 × 618K)
  are **NOT byte-identical** — COW-1 hashed them: `341cd48c…` vs `8c987791…`.
  Same size, exported 23 s apart, plausibly two different diagrams. **Deletion
  recommendation WITHDRAWN — keep both.** (K3's "byte-identical" was size-inferred,
  never hashed — registered as granularity error #5, and the first that would have
  destroyed something.)
- PDF binaries (~3.1M of the 5.3M): recommend include — they are the provenance
  corpus; size is trivial for git. Pen rules.

## C2 · Instruments — commit second

| Path | Content |
|---|---|
| `analysis/census_report.py` | enum census instrument |
| `analysis/prompt_interrogator.py` | EP field triage instrument (23 fields) |
| `analysis/R6_UNCLEAR_PREREG.md` | locked pre-registration (probe text still operator-held, §4 blank by design) |
| `tests/test_substantive_fields_counter.py` | counter test — **note: lives in `tests/`, not `analysis/`** (COW-1's spec said analysis/; actual location per git status) |

## C3 · R6 + counter — commit third, after C2 exists to verify it

| Path | Content |
|---|---|
| `intelligence_kernel.py` | 106 insertions / 8 deletions = R6's 8 enum appends + ~98-line substantive-fields counter |

**Gate:** v52 tests 21-pass + CI **688/13**-pre-existing — re-run at commit time
2026-08-05 (K3): 21/21 and 688+13 confirmed against the committed tree. [Corr
2026-08-05: this line read 667/13 — ET-1's pre-counter attestation. The counter
test carries `pytestmark = runtime_spine` (`tests/test_substantive_fields_counter.py:37`),
so the subset is 688/13 from `2fb4928` onward.] Commit messages cite **symbols,
not lines** (`run_emotional_physics`, `_EMOTIONAL_PHYSICS_PROMPT`), per
cite-by-symbol doctrine.

## Ruling queue — NOT staged; per-item or batch ruling needed

Root-level ops history, all untracked: `ClarityOS_ClarityEngine_Background_SocialThermodynamics.md` ·
`SPEC_READER_GROUNDING_v0.1_DRAFT.md` · `bucket-before-phase4.txt` ·
`phase5a_engine_before.yaml` · `phase5a_rollback_revision.txt` · two `preflight-4b-*`
yamls/json · `lb_snapshot_20260604_154124/` · `drafts/` · `review_packets/` ·
`command_structure/` · `specs/D1_CT2_REVIEW.md` · two `et1_*_reconciliation_return` files.

Recommendation: batch-rule as **ops-history → keep**, under one commit with a
`ops/` or `docs/ops-history/` relocation if pen wants root hygiene — but relocation
breaks any existing references; keeping paths as-is is the safer default.

## Order rationale

C1 secures the record at zero code risk. C2 lands the instruments before the code
they measure. C3 lands last so the counter ships with its test and its prereg in
history. If C3's re-run surprises, C1+C2 are already safe.

---

**MISSING MIDDLE**

**· Verified near end:** git status fresh this turn; sizes via du; PDF pair hashed by
COW-1 (`341cd48c…` / `8c987791…` — distinct, both kept); four missing corpus docs
restored to `source_docs/floating_geometry_2026-08-04/` at 15:46 EDT;
`tests/test_substantive_fields_counter.py` location from git status.

**· Extensions past it:** contents of ruling-queue files not reviewed — "ops-history"
is a classification by name/date, not by reading. Whether anything references those
paths — not grepped. The ~14-doc corpus count assumes no further docs exist beyond
the 18 upload stems seen; not exhaustively reconciled against pen's local folders.

**· Own-distortion check:** this manifest stages nothing itself; every unit is a
proposal. The ordering is engineering judgment, labeled.

---

## Execution block — prepared by K3 2026-08-04 16:05 EDT, refreshed 16:37 EDT, for pen's hand

Git status re-verified at refresh: unchanged — 1 modified (`intelligence_kernel.py`),
same untracked set. All edits since 16:05 are *content* changes inside paths already
staged by C1 (`git add source_docs/ snapshots/ analysis/...` covers them); one new
file (`source_docs/returns_2026-08-04_hat_inverts_something.txt`) also rides inside
`source_docs/`. **No command below needs changing.**

Git status verified fresh at prep time (pin `ae221b6`, tree matches this manifest).
Commands are Git-Bash-ready from repo root. **Nothing here has been run.**

```bash
# ── C1 · the record (zero code risk) ──────────────────────────────
git add snapshots/ source_docs/ \
  analysis/floating_geometry_lineage_2026-08-04.md \
  analysis/trace_state_distribution_reconciliation_2026-08-03.md \
  analysis/commit_manifest_2026-08-04.md
git commit -m "docs(record): bank 08-03/08-04 session corpus — snapshots, source_docs doctrine + ~14-doc floating-geometry set, lineage map, band trace (compute_state_distribution corner enumeration [0.13447, 0.47537])"

# ── C2 · the instruments (before the code they measure) ──────────
git add analysis/census_report.py analysis/prompt_interrogator.py \
  analysis/R6_UNCLEAR_PREREG.md \
  tests/test_substantive_fields_counter.py
git commit -m "test(analysis): enum census + EP field interrogator instruments, R6 unclear pre-registration (probe text operator-held), substantive-fields counter test"

# ── C3 · R6 + counter (gate first) ────────────────────────────────
# Gate: counter landed after ET-1's clean-pin attestation, so re-run:
python -m pytest tests/test_v52_emotional_physics.py -q          # expect 21 passed
python -m pytest -m "runtime_spine or privacy_surface or determinism_surface" -q
#   expect 688 passed + the same 13 pre-existing test_v44_model_router 403s
#   (entitlement-gate fixture gap, PL-Bravo B-1 — NOT R6; clean-pin isolated)
#   [Corr 2026-08-05: was 667 — the counter test joined the subset via its own
#    pytestmark at 2fb4928; actual gate result 688+13, EXECUTED 2026-08-05 ✓]
git add intelligence_kernel.py
git commit -m "feat(kernel): R6 — add | unclear null member to the 8 forced enums in _EMOTIONAL_PHYSICS_PROMPT; substantive-fields counter in run_emotional_physics meta (see analysis/R6_UNCLEAR_PREREG.md)"
```

**Left untracked deliberately** (ruling queue, §above): ops-history root files,
`command_structure/`, `drafts/`, `review_packets/`, `lb_snapshot_*/`,
`specs/D1_CT2_REVIEW.md`, the two `et1_*_reconciliation_return` files.

**After C3:** the working tree should show only the ruling queue as untracked and
zero modified files. Verify with `git status --short`. Then the citation-decay
hazard is closed and symbol re-anchoring for Phase 1 planning can proceed against
a stable pin.
