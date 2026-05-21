# Physics — Model Spec

## What this skill is

Identify the hard parts of the situation: invariants that must
hold, constraints that can't be relaxed, assumptions that are
hiding as facts, and the failure modes that follow if any of them
are violated.

The output sorts the situation into three buckets:

1. **Hard constraints** — things that genuinely cannot be true at
   the same time as the proposed plan. Physical, legal, mathematical,
   contractual.
2. **Soft constraints** — things that can in principle be relaxed
   but currently aren't. Cost, time, social capital, willingness.
3. **Assumptions presented as constraints** — things the input
   treats as fixed but which are actually choices.

Plus failure modes: what specifically breaks, in what order, if
each constraint is violated.

## Concepts

### Invariant
A property that must hold across all states of the system. Examples:
"every user's vault is encrypted at rest", "balance ≥ 0", "the
contract is governed by NY law". Invariants are non-negotiable and
should be tested, not assumed.

### Hard constraint
A boundary the system cannot cross. Differs from an invariant in
that invariants describe what's true; hard constraints describe
what isn't allowed. Often physical, legal, or mathematical.

### Soft constraint
A boundary that's currently respected but isn't fundamental.
Cost ceilings, deadlines that can slip, social norms that can be
challenged. Distinguishing these from hard ones is the main value
the skill provides.

### Assumption masquerading as constraint
The most useful output. The input says "we can't because X" but X
isn't actually a constraint — it's a default, a habit, or
something the speaker hasn't questioned.

### Failure mode
What specifically breaks if a constraint is violated. Failure modes
have:
* a trigger (which constraint failed)
* a description (what breaks)
* a blast radius (who/what is affected)
* a reversibility (can it be undone?)

### Feasibility
A summary verdict: feasible / feasible-with-changes / infeasible.
Backed by which constraints and at what cost.

## What this skill is NOT

* **Not a checklist.** The skill identifies the real load-bearing
  constraints, not every theoretical one.
* **Not pessimistic.** Physics doesn't say "no"; it says "here's
  what would have to be true."
* **Not a substitute for domain experts.** When stakes are high
  (legal, medical, regulatory), the output is a starting point
  for a real expert.

## Output shape

```
{
  "summary": "1-2 sentence feasibility read",
  "feasibility": "feasible | feasible_with_changes | infeasible",
  "invariants":         [ { "claim", "why_it_holds", "test" } ],
  "hard_constraints":   [ { "claim", "source", "violation_consequence" } ],
  "soft_constraints":   [ { "claim", "what_it_costs_to_relax" } ],
  "assumptions":        [ { "claim", "actually_negotiable", "what_changes_if_relaxed" } ],
  "failure_modes":      [ { "trigger", "description", "blast_radius", "reversible" } ]
}
```

See `schemas/outputs.json` for the precise spec.
