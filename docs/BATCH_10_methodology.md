# Batch 10 — Documentation Methodology

> The architecture-documentation standard for ClarityOS. This is a meta-doc: it
> governs how every subsystem doc in `docs/` is written, how the naming ledger
> and change manifest are maintained, and how fiction is kept out of the
> corpus. It is not a subsystem doc.

## 1. Purpose

Batch 10 is the rewrite that turned `docs/` from an ad-hoc collection into a
coherent architecture corpus. It exists to eliminate four recurring failure
modes:

- **Drift** — docs that describe an older or imagined version of the code.
- **Fiction** — docs that describe features, modules, or behaviors that do not
  exist in the codebase.
- **Namespace bleed** — a doc importing semantics from an unrelated subsystem
  (billing concepts leaking into an infrastructure doc, and the like).
- **Missing invariants** — docs that say *what* a subsystem does but not what
  it *guarantees* or *refuses* to do, leaving contributors to guess.

The corpus this methodology produces is **code-first**: every statement in
every subsystem doc is traceable to a named module, function, endpoint, or
constant in the repository. A contributor can extend a subsystem by reading its
doc and trust that the doc and the code agree.

## 2. The PASS-3C pattern

Every sub-batch follows the same seven-step process. The name encodes the
steps — **P-A-S-S** + **3C**:

1. **Pre-flight** — Before writing anything, enumerate the *real* modules of
   the target subsystem from the repository. Do not trust module names supplied
   by an instruction; verify them.
2. **Audit** — Check every claim the instruction makes against the code: named
   files, suspected-fiction constructs, assumed call sites, assumed behavior.
   Record discrepancies; never silently absorb them.
3. **Scope** — Decide exactly what the doc covers. Define the boundary
   explicitly, especially for cross-cutting subsystems.
4. **Separate** — Enforce namespace boundaries. A subsystem doc documents its
   own subsystem and cross-references others; it never re-explains them.
5. **Code-first** — Write every section from the actual implementation. A
   construct that is not in the code does not go in the doc — except under
   *Fiction removed*.
6. **Canonize** — Produce the doc in the house-style template (§8): grounded,
   terse, invariant-explicit.
7. **Clean manifest entry** — Record the sub-batch in
   `docs/BATCH_10_manifest.md` — a naming-ledger row and a change-manifest
   entry. Nothing is appended to individual docs.

Steps 1–2 are mandatory and precede any writing. A pre-flight that uncovers a
wrong premise — a non-existent module, an absent call site, a mis-flagged
"fiction" that is real code — is a success, not a delay. It is the step that
keeps fiction out of the corpus.

## 3. Subsystem scoping rules

- **What belongs:** only what the subsystem's own modules implement — its
  purpose, data model, APIs, integration points, invariants, non-goals.
- **What does not belong:** the internals of any other subsystem. Reference
  them by doc name (`see docs/x.md`) instead of re-documenting them.
- **Cross-cutting concerns:** some logic is physically shared — e.g.
  `dewey_pipeline.py` hosts DEWEY geometry *and* ELINS-envelope *and*
  Markov-predictive helpers. Document each shared element in exactly one doc —
  the one whose subsystem owns that role — and have the others note the
  boundary in *Non-goals*.
- **Namespace collisions:** one word can name several unrelated things.
  "Continuity" names three — the runtime reentry module, the
  `/continuity/snapshot` cockpit surface, and the operator-state continuity
  slice. When this happens, the pre-flight surfaces it, the owner chooses which
  thing the doc covers, and *Non-goals* lists the others by name.
- **Dormant vs. wired:** see §7.

## 4. Fiction handling

This is the discipline at the center of Batch 10.

- **Detection** — during Pre-flight and Audit, test each construct an
  instruction names (module, endpoint, function, behavior) with `Glob` /
  `Grep` and by reading the code. A construct that cannot be found in the
  repository is fiction.
- **Rejection** — fiction is never documented as real, and never silently
  dropped. It is recorded.
- **Recording** — every subsystem doc ends with a **Fiction removed** section
  that names the rejected constructs and states plainly that they are absent.
  When an instruction's suspected-fiction list turns out to be entirely real
  code, *Fiction removed* says exactly that ("None — every construct flagged …
  is implemented").
- **"Instruction says X, code says not-X"** — the code is canon. When an
  instruction contradicts the code, the code wins: surface the discrepancy with
  evidence (file, function, grep result), correct it, and record the
  correction in *Fiction removed* and/or the manifest. Cases seen across Batch
  10 — a sub-batch named modules (`dewey_neighbors.py`, `dewey_index.py`,
  `continuity.py`) that do not exist; a sub-batch flagged constructs as
  "possibly fictional" that were fully implemented (the Markov 4/3-1 chat
  runtime and its Observer/Interpreter/Regulator/Projector processors); a
  sub-batch named call sites (`session_loop.py`) that never call the module in
  question.
- **Preventing drift** — because every claim is code-traceable and every
  rejected construct is named, a later reader can re-verify the doc against the
  code and catch the moment they diverge.

## 5. Naming ledger rules

The naming ledger is the first register of `docs/BATCH_10_manifest.md`.

- **An entry** is one row: `Term | Sub-batch | Resolution`.
- **The resolution** is a single canonical line stating what the subsystem
  *is* (its responsibilities) and, explicitly, what it is *not* (its
  non-properties) — e.g. "Deterministic model-id resolver + provider dispatch;
  mock-on-failure; no sandboxing."
- **Non-properties are mandatory** — the clause that says "not X, not Y" is
  what stops the term from being misread later.
- **Relation to docs** — the ledger line is the one-sentence summary; the
  subsystem doc is the full account. They must agree.
- **Evolution** — a ledger row is corrected only with evidence and only when
  the code or the doc changes. Wording supplied by an instruction is checked
  against code before it is entered (e.g. "deterministic region IDs" was
  corrected to "opaque random IDs" because the code uses
  `secrets.token_urlsafe`).

## 6. Change manifest rules

The change manifest is the second register of `docs/BATCH_10_manifest.md` —
one entry per sub-batch.

- **Structure** — `Added` (the new doc files), `Fiction removed` (the rejected
  constructs, or "none" with a reason), `Notes` (boundary clarifications,
  cross-references, status caveats).
- **Retroactive corrections are annotations, not rewrites.** To correct a past
  entry, add a labelled parenthetical beneath it; never edit or delete the
  original wording. The original is retained for provenance.
- **Provenance** — when an entry is recorded after the fact (a sub-batch that
  predates the manifest), it carries an explicit `Provenance:` line saying so.
- **Authoritative and readable** — the manifest is the single index for the
  batch: plain Markdown, tables and bullets, readable with no tooling.

## 7. Dormant vs. wired subsystems

A module can be fully implemented and tested yet have no production caller.
Such a subsystem is **dormant** — real code, not fiction, but not yet
load-bearing.

- **Document it as dormant, explicitly** — state the status in *Purpose* (a
  `Status:` line), in *Integration points* ("there are currently no production
  call-sites"), and in *Fiction removed* if an instruction assumed wiring.
- **Describe intended integration without implying it exists** — phrase it as
  design intent ("designed to seed the runtime kernel") and state plainly that
  the wiring is not in the codebase.
- **Distinguish a data contract from a call path** — two modules that read or
  write the same persisted shape share a *data contract*; that is not the same
  as one calling the other. Say which it is.
- **Goal** — a future engineer reading the doc must not hallucinate that a
  dormant module is wired. `runtime_continuity.py` (Continuity, 10g) is the
  reference example.

## 8. House-style template

Every subsystem doc uses exactly these eight sections, in this order — and no
sections outside them:

- **Purpose** — what the subsystem is and why it exists; one short paragraph,
  framed as infrastructure rather than product UX.
- **Implementation location** — the real modules (repo-relative paths), any
  version / unit labels, and where the HTTP endpoints live.
- **Data model** — persisted shapes, collections and keys, constants, and
  result contracts.
- **APIs / entrypoints** — the HTTP endpoints and the public functions,
  grouped by area — not every private helper.
- **Integration points** — what the subsystem consumes and what consumes it;
  cross-references to other docs by name.
- **Invariants** — what the code guarantees: determinism, idempotency, failure
  behavior, ownership, bounds.
- **Non-goals** — what the subsystem deliberately does not do, and the
  boundaries with adjacent subsystems.
- **Fiction removed** — constructs an instruction or a prior layout suggested
  that are not in the code, named explicitly; or "None", with a reason.

Subsystem-specific detail goes *inside* the relevant section, never into a new
top-level heading. Prose is terse and code-traceable; `docs/threads.md` is the
strict exemplar.

## 9. Provenance requirements

Trust in the corpus depends on never rewriting history silently.

- **Annotate, do not overwrite** — corrections to a recorded entry are added as
  labelled parentheticals; the original text stays.
- **Cite evidence** — a correction states what it is based on (a file, a
  function, a grep result) so a reader can re-verify.
- **No silent edits** — when a fact changes, the change is visible: a
  provenance line, a clarification note, a dated parenthetical.
- **The result** — any reader can reconstruct what was believed when, and why
  it changed. That is what makes the manifest and the docs trustworthy as a
  long-lived corpus.
