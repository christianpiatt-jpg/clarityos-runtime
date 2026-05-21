# Markov — Usage Patterns

## When to invoke

* **Litigation, compliance, regulatory timelines** — they're
  natively state machines.
* **Sales / fundraising / hiring pipelines** — same.
* **Bug reproduction sequences** — what state must the system be
  in for the bug to fire?
* **Onboarding flows / customer journeys** — where does a new
  user get stuck?
* **Recurring patterns** — relationship dynamics, team cycles,
  any "this keeps happening" situation. Cycles are where Markov
  earns its keep.
* **Process audits** — name the states, find the gaps.

## When NOT to invoke

* **Single-event questions** ("should I do X?"). State machines
  are overkill.
* **Static descriptions of how something works.** Use Clarity.
* **Probability-heavy decisions** where numerical calibration
  matters. Markov is qualitative; for hard probability work, use
  a real probabilistic model.

## Compose with

* **Emotional Physics → Markov** — the Physics output's
  "trajectories" become Markov's `trajectories`; the model
  promotes them to a state machine.
* **Markov → Clarity** — render the state graph as readable
  prose for a human caller.
* **Markov → Physics** — once the states + transitions are
  named, ask which transitions are blocked by hard constraints
  vs negotiable.
* **Galileo Meta** routes between these chains.

## Failure modes to avoid

* **Sentiment-as-state.** If the state names sound like feelings
  ("frustrated", "happy"), redo with structural labels.
* **Phantom transitions.** If you can't name the trigger, drop
  the edge. Don't paper over it with "naturally evolves into".
* **Linear-only trajectories.** Most real systems have branches.
  Reporting a single path when the system clearly has options
  is over-fit.
* **Missing the cycle.** If the input mentions "every few weeks"
  or "we keep ending up here", there's a cycle. Find it.
* **Over-stating likelihoods.** Don't use "high" liberally. If
  every transition is "high", none of them are informative.
