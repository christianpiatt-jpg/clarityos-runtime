# Category Definition + External Language — Phase 14 Spec

A read-only, founder-facing taxonomic layer that defines the
**external category** ClarityOS belongs to: what category it creates,
what problem it solves, what it explicitly is not, and how to speak
about it externally without drift.

This is **not** marketing copy. It is a structural definition that
keeps external language honest.

---

## 1. Category name

**Inferential Discipline System (IDS)**

ClarityOS is the first instance of an Inferential Discipline System.
The category name is the descriptive term for any reasoning runtime
that:

- carries a versioned, falsifiable contract,
- enforces gates on every inferential claim,
- retracts prior claims under stricter contracts without overwriting
  the evidence they were drawn from,
- surfaces its own posture, readiness, and continuity descriptively,
- is operator-graded (not user-graded).

The acronym **IDS** is used in operator-internal communication. The
public-facing label is "Inferential Discipline System". External
copy may use either; both refer to the same category.

---

## 2. The problem this category solves

Reasoning systems today produce confident outputs without an audit
trail of their own structural state. They cannot:

- tell you when a prior conclusion has been retracted by a stricter
  contract,
- distinguish a regime effect from a confound that lives in the
  wiring of the test itself,
- resume the operator's session honestly across surfaces,
- hold themselves to the rules they nominally follow.

The cost of that gap is invisible until it isn't. An Inferential
Discipline System is the category of runtime that closes the gap by
construction — not by promise.

---

## 3. Boundary of the category

The category boundary is structural, not branded:

- **An IDS is gated.** Every inferential claim passes through a
  documented set of gates before becoming a claim.
- **An IDS is contract-bound.** Gates are defined in a versioned
  contract. Versions are immutable; amendments are additive.
- **An IDS is falsifiable.** Patterns that don't survive a paired
  permutation null are not patterns; they are confounds.
- **An IDS is descriptive.** Surfaces report state; they do not
  enforce, gate, predict, or automate.
- **An IDS is operator-graded.** It is built for the person who runs
  the reasoning system, audits its claims, and can't afford silent
  drift.

A system that lacks any one of these five properties is not an IDS,
regardless of what it calls itself.

---

## 4. Inside vs outside the category

| inside | outside |
|---|---|
| ClarityOS (the reference instance) | Productivity tools (Notion, Asana, Linear) |
| Future reasoning systems that adopt the five structural properties | AI assistants that generate content (Claude, ChatGPT used as endpoints) |
| Audit-grade analytics with versioned contracts and falsifiable gates | Coaching frameworks (mental models, journaling apps, habit trackers) |
|  | Analytics dashboards that surface KPIs without contract-bound gating |
|  | Mental models, books, frameworks — descriptive but not runtime |

The "outside" column is not a criticism. Those categories are useful
in their own scope. They simply do not perform inferential discipline
the way an IDS does, and conflating them dilutes the language.

---

## 5. How an IDS differs from existing categories

### vs. Productivity tools

Productivity tools optimize for **action throughput** — get more done
faster. An IDS optimizes for **inferential honesty** — know which of
your claims actually hold. The two are orthogonal; an IDS does not
make you faster.

### vs. AI assistants

AI assistants generate content on demand. An IDS audits claims after
the fact (or before they're shipped) under a contract. An assistant
without a contract is not an IDS, even if it is internally rigorous;
the contract has to be inspectable, versioned, and falsifiable.

### vs. Coaching frameworks

Coaching frameworks (mental models, journals, habit trackers) help
the operator change *themselves*. An IDS audits *the system*. The
operator's posture (Phase 11) is descriptive, not prescriptive — the
IDS does not tell the operator what to do; it tells them what the
state is.

### vs. Analytics dashboards

Analytics dashboards surface KPIs. An IDS surfaces gate outcomes —
which claims passed, which were retracted, why. KPIs without gates
become decorative; gates without KPIs are sufficient.

### vs. Mental models

A mental model is a way of thinking. An IDS is runtime infrastructure
that holds a way of thinking *to a contract*. The model fits in your
head; the contract lives in the codebase.

---

## 6. Three example external statements (structurally correct)

Each statement below is operator-grade: no outcome promises, no
predictions, no claims of effectiveness.

### Statement A — definition

> "ClarityOS is an Inferential Discipline System: it carries a
> versioned, falsifiable contract that retracts inferential claims
> when stricter gates fire — without overwriting the prior reading
> or the prior evidence."

### Statement B — boundary

> "An IDS is not a productivity tool. It does not help you do things
> faster. It tells you when an inference does not hold and surfaces
> the gate that caught it. The operator decides what to do next."

### Statement C — posture

> "What ClarityOS produces is a single read on whether your reasoning
> system is in a state where you can ship. The operator decides; the
> system surfaces. There is no gating of action, no automation, no
> prediction."

A statement that violates the boundaries in § 7 is **not** a correct
external statement, no matter how compelling.

---

## 7. Explicit boundaries of external language

External statements about the category MUST NOT:

- promise outcomes ("ClarityOS will make you more productive"),
- predict success ("ClarityOS users ship N% faster"),
- claim effectiveness without falsifiability
  ("ClarityOS reduces drift" — without specifying which drift, under
  which contract, and with which permutation null),
- describe the system as an assistant or a coach,
- conflate descriptive output with prescriptive guidance.

They MAY:

- describe the structural properties (gated, contract-bound,
  falsifiable, descriptive, operator-graded),
- name what the category is and is not,
- quote the operator's own prior reading without prediction,
- describe what the surfaces show, what the contracts gate, and what
  the system refuses to do.

The category survives external speech only if external speech holds
to the boundary. This is the operator's responsibility; the category
definition is the floor.

---

## 8. Future extension notes (Phase ≥ 16)

Phase 16+ may extend the category layer with:

- A "category compliance check" that audits external statements
  against the boundaries in § 7 (descriptive only; not enforcement).
- A canonical glossary of category terms used internally and
  externally (versioned).
- A "non-ClarityOS IDS" registry if other systems adopt the five
  structural properties (descriptive only; no validation authority).
- An export of the category definition to the operator playbook for
  Fortune 500 review (already scaffolded under
  `tests/acceptance/operator_playbook_f500.md`).

These are out of scope for Phase 14. Phase 14 is the descriptive
read-only floor for category language; later phases may build on
top, but must preserve § 7's prohibitions.
