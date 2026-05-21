# Galileo Meta — Theory

## The premise

The four base skills are each load-bearing for a particular kind
of input. None of them generalises well outside its domain:

* Emotional Physics on a feasibility question produces empty
  arrays.
* Physics on a relationship pattern produces a list of invariants
  that miss the actual dynamics.
* Markov on a 3-page brief produces a state machine the caller
  didn't ask for.
* Clarity on a single sentence produces ceremony.

A caller who knows which skill they want can invoke it directly.
A caller who doesn't — or whose input straddles multiple kinds —
needs an orchestrator. Galileo Meta is that.

## Why "Galileo"

Borrowed because Galileo's contribution wasn't a new physical law;
it was the discipline of choosing the right frame of reference for
a given observation. The orchestrator is doing the same thing:
not adding a fifth reasoning mode, but selecting and composing
the four that exist.

## Selection over reasoning

The orchestrator's distinguishing property is that it doesn't
reason about content directly. It reads the input, recognises
which signals are present, and routes. The actual analysis happens
in the base skills.

This separation is deliberate. Mixing selection logic with
analysis logic produces a model that confidently runs the wrong
analysis. Keeping them separate means:

* the base skills can be improved independently,
* the orchestrator's selection is auditable,
* the rationale is informative — the caller sees *why* this path
  was chosen, not just what the analysis said.

## Composition vs sequencing

Two ways to combine skills:

* **Sequencing** — run skill A, feed its output into skill B as
  context. Used when B's analysis depends on A's structure
  (e.g. clarity → physics: clarity surfaces assumptions, physics
  tests them).
* **Parallel** — run two skills on the same input, then have a
  third (often clarity) compose them. Used when the input has
  two independent dimensions (e.g. emotional_physics + physics
  on a negotiation: forces and constraints are different layers).

Both produce structured output that the orchestrator stitches
into `composed_output`.

## When to answer directly

Many inputs don't need any base skill. Factual lookups, simple
acknowledgements, requests for specific information — these go
straight to `composed_output` with `selected_skills: []` and
`rationale` explaining why nothing was invoked.

Resist the urge to always invoke at least one skill. Empty
selections are valid and honest.

## Limits

* **Selection accuracy.** The orchestrator can pick wrong. Every
  rationale is exposed so the caller can override.
* **Cost.** Each skill invocation is a separate model call.
  Three-skill chains cost ~3x. The orchestrator is biased
  toward minimal selection for that reason.
* **Composition quality.** When two skill outputs need to be
  merged into a single prose answer, the merge can lose nuance.
  Calling out which intermediate output the caller should look
  at directly mitigates this.
* **No fifth skill.** If a future input needs analysis the four
  base skills don't cover, the orchestrator should report that
  honestly rather than forcing a fit.
