# Physics — Theory

## The premise

Most plans fail at one of three places:

1. They violate a constraint nobody named.
2. They treat an assumption as if it were a constraint.
3. They underestimate the failure mode if a constraint slips.

Physics targets all three. The output is a sorted list of what's
genuinely fixed, what's currently fixed but negotiable, what's
just being assumed, and what specifically breaks if any of them
is wrong.

The skill name is borrowed because physical systems have a useful
property: the laws don't bend. A bridge either supports the load
or it doesn't. Plans should be analysed with the same discipline:
identify the parts that don't bend, then check whether the plan
respects them.

## Invariants vs constraints

* An **invariant** is something that must remain true. It's a
  property of every valid state.
* A **hard constraint** is something the plan must respect. It's a
  rule about which transitions are allowed.

The distinction matters because invariants are tested (you check
each state) while constraints are gated (you check each action).
A bug in invariant enforcement produces silently corrupt state; a
bug in constraint enforcement produces forbidden actions that
attract attention.

## The "assumption masquerading as constraint" pattern

The most valuable output the skill produces. The input says
"we can't because X" and the model checks whether X is actually
fixed. About a third of stated constraints in real plans turn out
to be defaults nobody questioned.

This pattern is also what makes Physics different from a checklist.
A checklist surfaces missing items. Physics surfaces *unnecessary*
items.

Common shapes:

* "We need a designer." → Often: an engineer + design system can
  ship something adequate.
* "Legal review takes 6 weeks." → Often: 6 weeks if engaged at
  the end; 1 week if engaged from week 1.
* "We can't change the contract." → Often: not changeable
  unilaterally; changeable by mutual agreement, which has never
  been asked.
* "It has to be Python." → Often: the existing codebase is Python;
  a new component could be anything.

Physics flags these. It doesn't decide which to relax — that's
the caller's call — but it makes them visible.

## Failure modes

A failure mode is the answer to "what specifically breaks if X
fails?" A constraint without a failure mode is decoration.

Each failure mode includes blast radius (who/what is affected) and
reversibility. These two together let the caller prioritise: a
small reversible failure mode is cheap to risk; a large
irreversible one isn't.

## The feasibility verdict

Three values:

* **feasible** — every constraint is respected; the plan can be
  executed as stated.
* **feasible_with_changes** — at least one assumption needs to
  flip, but no hard constraint is violated.
* **infeasible** — a hard constraint is violated and there's no
  path to resolve it. Plan must be redesigned.

Resist the urge to grade everything `feasible_with_changes` to
seem agreeable. If the plan as stated works, say so.

## Limits

* **Domain knowledge.** Physics doesn't know domain-specific
  invariants (medical regulation, tax law, structural engineering).
  For high-stakes domains the output is a starting frame; pair
  with a real expert.
* **Empirical claims.** "Default rate is high" needs a number to
  be load-bearing. The skill flags the claim but can't confirm it.
* **Politics.** Some constraints are political (who owns the
  decision, who'll be upset). Physics names them as soft
  constraints; it doesn't model the politics.
