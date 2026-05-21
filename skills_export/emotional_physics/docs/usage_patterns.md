# Emotional Physics — Usage Patterns

## When to invoke

Use Emotional Physics when the input contains:

* **Conflict**, especially the kind that hasn't surfaced as
  explicit disagreement yet ("things feel off", "we keep avoiding
  the topic").
* **Sustained patterns** — three weeks of the same thing, every
  meeting going the same way, a relationship that's drifting in a
  specific direction.
* **Stress descriptions** that the caller wants modelled rather
  than soothed.
* **Decisions about people** where the caller is trying to
  predict how someone will behave.
* **Pre-mortems** for relationships, teams, or commitments —
  "what could break this, and when?"

## When NOT to invoke

* Single-incident questions where structure is overkill ("is it
  rude to skip this party?").
* Clinical or crisis situations — escalate to humans, don't try
  to model.
* Sentiment classification tasks — much simpler tools handle
  those better.
* When the caller wants to feel heard. The structural read can
  feel cold; pair with Clarity if the caller wants the read to
  also be human-readable.

## Compose with

* **Clarity (after)** — to translate the JSON back into prose for
  the caller.
* **Markov (after)** — to project the trajectories as a state
  machine, especially when there are multiple branching paths.
* **Physics (alongside)** — when constraints in the situation
  are actual hard constraints (legal, medical, contractual) and
  the caller needs to separate negotiable rigidity from real
  invariants.
* **Galileo Meta** — handles the "which of these to invoke" call.

## Failure modes to avoid

* **Inventing forces.** If the input doesn't show a force, don't
  put one in the list. Returning empty lists is a valid response.
* **Sliding into advice.** This skill describes; it doesn't
  prescribe. If the caller wants an action recommendation, that's
  a different skill.
* **Sliding into sentiment.** "She's anxious" is not a force.
  "Subject's need to maintain reliability under deadline pressure"
  is.
* **Over-fitting to the speaker's framing.** The input is one
  party's read; the model should note where the speaker's framing
  is itself a force ("subject's identity claim that they are
  always the patient one") rather than treating the framing as
  ground truth.
