# Markov — Theory

## The premise

Most situations that look continuous are actually discrete: a small
set of stable configurations connected by event-triggered jumps.
The continuous appearance comes from being inside one configuration
for a stretch of time. The discrete reality shows up at the
transitions.

Markov decomposes the situation into states + transitions and
ignores the within-state continuity. What matters is which state
the system is in and what would move it elsewhere.

## Why "Markov"

Borrowed from Markov chains, but used loosely. We don't require
that the next state depends only on the current one (the strict
Markov property), and we don't require numerical probabilities.

What carries over:
* finite, named states
* directed transitions between them
* a current location
* the idea that you can reason about likely paths even when you
  can't predict them precisely

What we drop:
* the strict memorylessness assumption
* numerical transition matrices
* steady-state computation

The output is a graph, not a stochastic process.

## States and the discipline of naming

A state's name must be:
* short
* descriptive (you can guess the contents from the name)
* not sentimental

"Frustrated" is a feeling, not a state. "Stalled" is a state —
it has entry conditions ("blocking dependency unresolved for >N
days"), exit conditions ("dependency resolves" or "scope changes"),
and observable signatures ("PR sitting unmerged, last commit two
weeks ago").

Sentiment labels masquerade as states all the time. The discipline
of naming entry/exit conditions is what catches them: if you can't
name them, the state is fake.

## Transitions and triggers

Every transition has a trigger — a specific event. "Time passes"
counts only when the timescale itself is the mechanism (deadlines,
expiries, license terms). For everything else, name the actual
event.

Triggers without events are wishes. Modelling them as transitions
makes the system look more deterministic than it is.

## Cycles

Cycles are the most useful output the model produces. A cycle says
"this configuration repeats until something external changes."
That's a stronger claim than any individual trajectory. When
Markov reports a cycle, the operator has three choices:

1. accept the cycle (it's a feature, not a bug),
2. introduce an external change to break it,
3. find an absorbing state inside the cycle's neighbourhood and
   route the trajectory toward it.

Cycles also catch the writer when the input describes a pattern
they think is progress but is actually repetition.

## Limits

* **Hidden states.** The model only sees what the input describes;
  states the input doesn't reveal stay invisible. Pair with
  Emotional Physics or Physics if structural / motivational layers
  may have additional states.
* **Snapshot inputs.** A single moment doesn't define a state
  machine; the model has to work from one observation. Trajectories
  in this case are speculation, not extrapolation.
* **Probabilities.** Likelihoods are qualitative. Don't read them
  as Bayesian posteriors.
