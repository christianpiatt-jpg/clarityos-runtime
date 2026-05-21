# Markov — Model Spec

## What this skill is

Treat the situation as a finite set of **states** connected by
**transitions**. Each state has entry conditions (what gets you in)
and exit conditions (what gets you out). The current location in
the state space is identified, and the most likely next states are
named.

Probabilities are optional. The structure — which states exist,
what connects them, what triggers a move — is mandatory.

## Concepts

### States
A state is a configuration the system can be "in" for some
duration. States have:

* a name (short, descriptive)
* a description (1-2 sentences)
* entry conditions (what puts the system here)
* exit conditions (what moves it elsewhere)
* observable signatures (how you can tell from the outside)

### Transitions
A transition is a directed edge between two states. Transitions
have:

* `from` and `to` state names
* a trigger (the event that causes the move)
* a likelihood (low / medium / high — when probability matters)
* a timescale (instant / minutes / hours / days)

### Current state
Where the system is now, given the input. Uncertain inputs may
report multiple possible current states with reasons.

### Trajectories
Paths through the state graph the system is likely to follow,
ranked. Each trajectory is a sequence of state names plus the
triggering events between them.

### Absorbing states
States with no defined exit. Used to mark terminal configurations
(decision made, relationship ended, deadline passed).

### Cycles
Sequences of states that return to themselves. Important to name
because they predict repeated behaviour without resolution.

## What this skill is NOT

* **Not a probability model.** Edge probabilities are optional and
  qualitative when given. Markov reports structure, not p(next).
* **Not a workflow tool.** It describes what states the system
  passes through, not what the operator should do.
* **Not deterministic.** Multiple trajectories are normal output.

## Output shape

```
{
  "summary":      "1-2 sentence structural read",
  "states":       [ { "name", "description", "entry_conditions", "exit_conditions", "signatures" }, ... ],
  "transitions":  [ { "from", "to", "trigger", "likelihood", "timescale" }, ... ],
  "current_state": "name (or array of names if uncertain)",
  "trajectories": [ { "path": [...], "likelihood", "horizon" }, ... ],
  "absorbing":    [ ... ],
  "cycles":       [ { "states": [...], "trigger" }, ... ]
}
```

See `schemas/outputs.json` for the precise shape.
