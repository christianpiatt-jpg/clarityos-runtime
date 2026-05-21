# Galileo Meta — Usage Patterns

## When to invoke

* **The default top of every conversation** with an external LLM
  using this bundle. The meta layer routes; the base skills do
  the analysis.
* **Inputs that span multiple signals** (a long brief that also
  contains conflict; a plan that also contains a recurring
  pattern).
* **When the caller doesn't know which skill to ask for.**
* **When a chain of skills needs to be coordinated** — meta
  handles sequencing + composition.

## When NOT to invoke

* **When the caller asked for a specific skill by name.** Run
  that skill directly. Don't second-guess.
* **For pure mechanical tasks** (translate this, format this) —
  the meta overhead is unnecessary.
* **When the orchestrator would clearly invoke nothing.** If
  the input is "what's 2+2", just answer.

## Default chains

These show up often enough to be worth memorising:

| Input shape                                        | Default chain                              |
|----------------------------------------------------|---------------------------------------------|
| Negotiation read                                    | emotional_physics + physics → clarity       |
| Plan / brief feasibility                            | clarity → physics                           |
| Process or recurring pattern                        | markov                                      |
| Process + feasibility                               | markov → physics                            |
| "What's going on with this person/team"             | emotional_physics → clarity                 |
| Pre-mortem                                          | physics                                     |
| Long messy text needing structure                   | clarity                                     |
| Single-incident emotional question                  | (likely none — answer directly)             |
| Factual lookup                                      | (none)                                      |

## Failure modes to avoid

* **Over-routing.** If the rationale reads "this might involve
  emotional dynamics, also feasibility, also structure", you're
  hedging. Pick the dominant signal.
* **Skipping the rationale.** A selection without a rationale is
  unauditable. Always say which signals you saw.
* **Smuggling reasoning into the orchestrator.** When the
  composed_output contains analysis that none of the
  intermediate skill outputs supports, the orchestrator has
  drifted out of role. The composition should restate /
  rearrange / translate base skill outputs, not generate new
  analysis from scratch.
* **Always invoking something.** Empty selections are valid.
  The orchestrator's honesty about not needing a base skill is
  more useful than reflexive over-application.
