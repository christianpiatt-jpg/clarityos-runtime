# Clarity — Theory

## The premise

Most messy text is messy in three ways at once:

1. **Repetition.** The same idea expressed multiple ways.
2. **Hidden structure.** The content has a real shape (sequence,
   hierarchy, branching), but the prose flattens it.
3. **Implicit context.** Assumptions the writer made about the
   reader, the situation, or the prior conversation.

Clarity addresses all three in one transform. Editing only one
leaves the others to confuse the reader.

## Why four outputs

The four outputs (summary, outline, clean_text, assumptions) target
four different reading modes:

* **Summary** — for someone who only has time for the gist.
* **Outline** — for someone who needs to navigate / find / cite.
* **Clean text** — for someone who needs to read the whole thing.
* **Assumptions** — for someone deciding whether to act on it.

Producing all four together also helps the model: writing the
outline reveals what the summary should highlight; surfacing
assumptions catches places where the clean text was about to
silently re-introduce a guess.

## Why "preserve intent"

It's tempting to "fix" inputs while clarifying them — close the
logical hole, soften the over-claim, hedge the unhedged. Doing so
defeats the purpose. The caller wants to see what's actually
there. If the input is wrong, Clarity should make the wrongness
easier to spot, not paper over it.

This is the strongest discipline in the skill: when you can see
the input is broken, your job is to make the breakage *more
visible*, not to fix it.

## Relationship to summarisation

Summarisation is lossy by design. Clarity is lossless rearrangement
plus assumption surfacing. The clean_text contains everything the
input contained; it just contains it once and in the right order.

When length must drop sharply, the summary handles it; the clean
text stays substantively complete.

## Limits

* **Voice.** Clarity normalises register lightly. If voice is
  load-bearing (a literary piece, a brand-specific tone), set
  `preserve_voice: true` in the input context.
* **Domain knowledge.** Clarity won't tell you whether a domain
  claim is correct; it'll just make the claim's structure visible.
  Pair with Physics if you also need invariant-checking.
* **Recursion.** Running Clarity on its own output usually
  produces no change — the transform is roughly idempotent. If
  it's not, the second pass is finding assumptions the first
  missed; that's a feature, not a bug.
