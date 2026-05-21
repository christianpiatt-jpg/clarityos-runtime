# Galileo Meta — Examples

## Example 1: A negotiation read

**Input:**

> "I've been negotiating with this vendor for three weeks. They keep
> saying they can't go below $X because of their cost basis. Every
> time I push, they get a little colder. I think we both want this
> deal but I don't know if we'll get there."

**Output:**

```json
{
  "summary": "Three signals present: sustained pattern (weeks of cooling), 'we can't because' framing (cost basis), and an open question about feasibility. Routed through emotional_physics + physics, then composed via clarity.",
  "selected_skills": ["emotional_physics", "physics", "clarity"],
  "rationale": "Sustained cooling over three weeks plus phrases like 'we both want this' indicate emotional dynamics worth modelling structurally. The 'they can't go below $X because of their cost basis' is a stated constraint worth testing. Both reads are needed; clarity composes them into a single human-readable handoff.",
  "intermediate": {
    "emotional_physics": "...structured forces/constraints/trajectories output...",
    "physics":           "...constraints/assumptions/feasibility output..."
  },
  "composed_output": "Two layers running here. The vendor's stated 'cost basis' is likely an assumption presented as a constraint — vendors rarely have a true floor; what they have is a floor at which they're willing to walk. The cooling over three weeks suggests their willingness-to-walk threshold is near. Mutual desire for the deal still favours an agreement, but the trajectory is toward inversion within roughly another two cycles of pushback. Recommendation: stop pushing on price; reframe the next round around terms that change the cost basis (longer commitment, payment structure, scope) so the floor itself moves."
}
```

---

## Example 2: A plain factual question

**Input:**

> "What's the difference between a SoftWrap and a HardWrap in CSS?"

**Output:**

```json
{
  "summary": "Factual question. No base skill invoked.",
  "selected_skills": [],
  "rationale": "Input contains no sustained pattern, no messy text to clarify, no state machine, and no plan to test for feasibility. It's a direct factual lookup.",
  "intermediate": {},
  "composed_output": "There isn't a 'SoftWrap' / 'HardWrap' distinction in standard CSS — those terms come from text editors. The CSS equivalents are `white-space` (controls when wrapping happens) and `overflow-wrap` / `word-break` (controls where words can break). If you meant something else, point me at the source."
}
```

The orchestrator answering directly is a valid path. Don't invoke
skills when no signal is present.

---

## Example 3: A long messy plan

**Input:**

> [3-page brief about migrating an internal tool from Heroku to
> Cloud Run, with redundant context, unclear timelines, and
> several "we can't because" framings]

**Output:**

```json
{
  "summary": "Long redundant plan with embedded constraints. Routed clarity → physics; clarity surfaces assumptions, physics tests them.",
  "selected_skills": ["clarity", "physics"],
  "rationale": "Three pages of mostly-redundant prose is the dominant signal — clarity is the entry point. Once clarity has surfaced the assumptions list, physics tests which are actually load-bearing constraints. Markov is unnecessary because the plan doesn't describe a state-machine-shaped process; it describes a one-shot migration.",
  "intermediate": {
    "clarity": "...summary/outline/clean_text/assumptions output...",
    "physics": "...invariants/constraints/feasibility output..."
  },
  "composed_output": "Clean read of the plan + feasibility verdict (here, feasible_with_changes; two of the four 'we can't' items are actually negotiable). The blocking item is the Heroku → Cloud Run timezone-handling delta — that's a genuine invariant. The other three are habits."
}
```
