# Interpretation Ceiling — `delta.intensity_mean` · v0.1 [designed]

*2026-08-05 · K3 draft, pen-authorized (Item B) · status **[designed]** — doctrine, no
runtime enforcement. Closes ET-1's open item from the Lane 1 return ("the interpretation
ceiling is unwritten… the gap most likely to be rediscovered later as a defect").*

## What this bounds

`delta.intensity_mean` (`ef0c19d`, `ELINS/elins_project.py` `update_ep_baseline`) is the
system's first measured r−E: new observation minus stored smoothed prior, null on first
observation. This clause sets **what a reader — human, lane, or LLM restatement — may and
may not infer from its value.** A measurement without a ceiling gets read at whatever
resolution the reader feels like; that is the maneuver-regime failure the comms clause
(v0.4) exists to block, one level up.

## The mechanism, verified end-to-end (2026-08-05)

```
text → _PRIMITIVE_LEXICON substring match   (ELINS/standard_elins.py:75-94,
       · no negation window anywhere         matched by _count_matches :205)
     → primitives → ep_field_summary
     → intensity_mean                        (elins_project.py:274)
     → smoothed baseline (α=0.2)             (elins_project.py:299-303)
     → delta = new_obs − prior, or null      (elins_project.py:288-297)
```

Every link above was read at pin this week; none is inferred.

## The ceiling — five rules

1. **The delta measures lexical-mass movement, not situational change.** What may be
   inferred: *"the primitive-mass of this user's text, as the lexicon sees it, moved
   against their smoothed baseline."* Nothing stronger. The lexicon's blind spots
   (personal/interior text scores ~0 — the domain-mismatch finding) bound every value
   the delta can take.

2. **Negation flips valence, not mass.** The lexicon matches substrings with no
   negation window: "growing **distrust**" hits `("trust", 0.4)` at
   `standard_elins.py:82`. A trust *collapse* therefore **raises** `intensity_mean` —
   the delta moves, sometimes for the wrong reason. **No valence inference is legal
   from this delta, in either direction.** Worse: the inverted mass also feeds
   trust-derived scores (`score_S1/S2` contain `tr`,
   `ELINS/elins_v2_view.py:161-162`) — valence inversion contaminates state
   attribution downstream of the delta, not just the delta itself.

3. **A first post-upgrade delta on a legacy record is not a measurement.**
   `existing.get("intensity_mean", 0.0)` (:296): a baseline record lacking the key
   yields delta = new_obs − 0.0 — full-scale manufactured movement, indistinguishable
   from real signal. Until key provenance is confirmed, a first delta after any schema
   change reads as `[Δunsep]`, not as evidence.

4. **Zero delta is ambiguous by construction** (v0.4, applied): perfect stability or
   no contact — lexicon-miss text pins observations at the fixed point, and a delta of
   nulls-of-the-same-constant is 0.0 forever. Zero carries the contact tag `[grip]`
   or the ambiguity, never neither.

5. **This is baseline-delta, not dissonance.** The delta is r−E against a *smoothed
   trailing average* — not forecast-envelope vs realized outcome. The full |r − E|
   pairing (dated, horizon-bounded forecast vs what came back) remains unbuilt;
   `elins_project_runs` is its r-side. Do not restate the baseline delta as
   dissonance; that is the laundering move at loop scale.

## What the ceiling permits (the legal use)

The delta is a **contact detector**: it proves the instrument moved, which the
uniform-panel era could not. A non-null, non-manufactured delta is legal grounds to
*look closer* — a trigger for a read, never the read itself. Trigger, not verdict.

## Status & enforcement

[designed]. No runtime parses this. The natural enforcement point, when one exists, is
the render layer: any user-facing restatement of `delta.intensity_mean` composed under
comms clause v0.4/v0.5 rules — maneuver-grade shape, `[Δunsep]` on cause ambiguity,
identity withheld. Until then this clause governs lanes by adoption, not by gate.

## Provenance

Mechanism verified by K3 2026-08-05 (lexicon :75-94, `_count_matches` :205,
`elins_project.py:262-316`). Triggered by ET-1's Lane 1 return "still open" item 1.
Drafted under pen authorization 2026-08-05 11:37 EDT.
