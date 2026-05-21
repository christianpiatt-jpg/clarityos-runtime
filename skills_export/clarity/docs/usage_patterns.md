# Clarity — Usage Patterns

## When to invoke

* **Briefs and specs** before they go to a team.
* **Long messages** the caller is about to send (email, Slack
  thread, PR description) and wants tightened.
* **Plans** that have been edited many times by different people.
* **Proposals** where surfacing the assumptions changes whether
  to accept.
* **Output of other skills** (Emotional Physics, Markov, Physics)
  when the structured JSON needs to be readable prose for a
  human caller.
* **One's own thinking** — running Clarity on a draft of your
  own argument exposes which parts are load-bearing and which
  are filler.

## When NOT to invoke

* **Tweets / single-sentence inputs** unless the caller is
  specifically interested in the assumptions list.
* **Creative writing** where voice is the point (set
  `preserve_voice: true` if you must run it anyway).
* **Already-clear inputs** — Clarity will report so honestly,
  but it's wasted compute if you knew the input was already
  tight.

## Compose with

* **Emotional Physics → Clarity** — translate a structural
  emotional read back into prose for the caller.
* **Markov → Clarity** — render a state machine as readable
  step-by-step prose.
* **Physics → Clarity** — render a list of invariants as a
  decision-ready memo.
* **Clarity → Physics** — surface assumptions, then test which
  ones are actually invariant.
* **Galileo Meta** routes between these chains based on what
  the caller asked for.

## Failure modes to avoid

* **Smoothing the surface and losing the load-bearing language.**
  If a phrase is unusual on purpose ("strict subset", "by
  construction", legal terms), preserve it verbatim.
* **Inventing structure.** If the input genuinely is unstructured,
  the outline can be flat. Don't impose hierarchy that wasn't
  there.
* **Editorial fixes.** Don't strengthen weak claims, don't soften
  strong ones, don't add caveats the writer didn't include.
* **Skipping assumptions.** Even short inputs hide assumptions.
  If the assumptions list is empty for a non-trivial input, the
  pass was incomplete.
