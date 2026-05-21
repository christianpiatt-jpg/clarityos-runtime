# Physics — Usage Patterns

## When to invoke

* **Plans about to be committed to** — feasibility check before
  the calendar fills with execution work.
* **"We can't because X" claims** — to test whether X is actually
  fixed.
* **Pre-mortems** — what's the failure mode for each constraint?
* **Architectural decisions** — invariants the system must
  preserve across versions.
* **Negotiations** — distinguish what the other side actually
  can't do from what they're framing as fixed.
* **Compliance-adjacent work** — to separate genuine regulatory
  invariants from internal habits dressed up as compliance.
* **Reviewing your own plans** — most usefully when you suspect
  you're constraining yourself unnecessarily.

## When NOT to invoke

* **Sentimental questions** — Physics will return empty arrays;
  use Emotional Physics.
* **Process descriptions** — use Markov.
* **Already-clear feasibility** — if the plan is obviously fine,
  Physics will say so but you didn't need it to.

## Compose with

* **Clarity → Physics** — the assumptions list from Clarity
  becomes the starting point for what Physics tests as
  constraints.
* **Physics → Markov** — once you know which transitions are
  blocked by hard constraints, build the state machine of
  remaining options.
* **Emotional Physics + Physics** — distinguish "the relationship
  has constraints" (real invariants) from "the speaker assumes
  it does" (assumptions). The two skills jointly produce a much
  cleaner read of negotiation situations than either alone.
* **Galileo Meta** routes between these chains.

## Failure modes to avoid

* **Padding the constraints list.** Five real load-bearing
  constraints beat thirty theoretical ones. If you list a
  constraint you can't connect to a failure mode, drop it.
* **Treating cost as a hard constraint.** Cost is almost always
  soft. The right place for cost is `soft_constraints` with a
  `what_it_costs_to_relax`.
* **Calling habits "compliance".** Lots of internal rules dress
  up as regulatory. Test the chain: which actual regulation,
  which clause, what's the violation consequence?
* **Grading every plan `feasible_with_changes`.** When the plan
  as stated works, the verdict is `feasible`. Don't seek
  changes for their own sake.
* **Skipping the failure mode.** A constraint without a failure
  mode is decoration. If you can't describe what breaks, the
  constraint isn't load-bearing.
