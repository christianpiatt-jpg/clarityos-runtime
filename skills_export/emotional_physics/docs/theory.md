# Emotional Physics — Theory

## The premise

Sentimental descriptions of people ("she's anxious", "he's angry")
collapse three things into one label:

1. The forces acting on the person.
2. The constraints those forces are pushing against.
3. The trajectory the system is on.

Collapsing these makes the description feel intuitive but kills
its predictive value. "She's anxious" tells you almost nothing
about what she'll do tomorrow. "Her need to belong is rising
against a rigid constraint about not appearing needy, and the
trajectory is toward either an ask that breaks the constraint or
a withdrawal" tells you what to watch for.

Emotional Physics is the practice of decomposing the sentimental
read back into its three components and reporting on them
separately.

## Why "physics"

Three borrowed primitives:

* **Force** has direction + magnitude. So does any motivation.
  Treating motivations as vectors lets us add them, observe when
  they oppose each other, and predict net direction.
* **Constraint** is what holds an object in place against force.
  In a rigid-body system, constraints either hold or fail; they
  don't gradually weaken. Same with social / identity constraints.
* **Trajectory** is the path through state space if forces and
  constraints stay constant. Easy to compute; the tricky part is
  knowing when something will change.

The borrowing doesn't go further than that. There's no equivalent
of mass, momentum, or energy conservation; humans aren't rigid
bodies. The three primitives are the parts that genuinely transfer.

## Pressure / release / inversion

Three observable phenomena worth naming:

**Pressure** is the gap between force and constraint. Force grows
or constraint weakens → pressure rises. Pressure is observable as
narrowing focus, irritability, sleep changes, increased reactivity.
You can read pressure without knowing which force or constraint is
involved.

**Release** is what happens when a constraint suddenly relaxes —
sleep, decision, confession, leaving the situation, a third party
taking the choice out of your hands. Release usually feels good
even when the underlying force is unchanged.

**Inversion** is when a force flips polarity. Love → contempt,
ambition → bitterness, hope → resignation. Inversion is the most
useful signal in the model: it's discontinuous, hard to reverse,
and predicts behavioural change far better than the magnitude of
any individual force.

A high-pressure system with no release path is at risk of
inversion. That's the structural read of "the breaking point."

## Why the output is JSON-shaped

Two reasons:

1. **Composition.** The Galileo Meta orchestrator can chain this
   skill's output into Clarity (clean it up) or Markov (treat the
   trajectories as state-machine transitions). Structured output
   composes; prose doesn't.
2. **Traceability.** A structural read can be argued with field-
   by-field. "I disagree that the constraint is rigid" is a
   productive disagreement. "I disagree with your vibe" isn't.

## Limits

* This skill **does not** prescribe action. Two structural reads
  can support opposite responses depending on the caller's values.
* It **does not** know the subject — only what the input describes.
  Ask for missing context if the read would be invented.
* It **does not** replace clinical judgment. Pressure → inversion
  → harmful behaviour is a real risk surface; in that zone the
  caller should escalate to humans qualified to handle it.
