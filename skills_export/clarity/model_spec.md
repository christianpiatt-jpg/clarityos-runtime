# Clarity — Model Spec

## What this skill is

A transform from messy input to a clear structural read of the same
content. Operates at four levels simultaneously:

1. **Summary** — what is this actually about, in 1-2 sentences.
2. **Outline** — the explicit structure beneath the prose.
3. **Clean text** — the same content, rewritten with redundancy
   removed and structure surfaced.
4. **Assumptions** — the things the input took for granted but
   didn't state.

The four are produced together, not in sequence. They reinforce
each other: the assumptions list often clarifies the summary;
the outline often surfaces an assumption.

## Principles

### 1. Remove redundancy
If the same idea appears three times in the input, it appears once
in the clean text. Variations of phrasing are collapsed.

### 2. Expose structure
The clean text reflects the actual structure of the content.
Lists become lists. Sequences become numbered. Conditionals become
explicit ("if X then Y"). Implicit hierarchy becomes nested.

### 3. Preserve intent
The clean text says what the input was trying to say. It doesn't
add claims, doesn't drop nuance, doesn't soften strong positions.
If the input is wrong, Clarity makes the wrongness easier to see;
it doesn't fix the wrongness.

### 4. Surface assumptions
Every nontrivial input rests on assumptions the writer didn't
state — about the audience, about prior context, about what's
obvious. Clarity names these explicitly. Each assumption is
flagged as `confirmed`, `likely`, or `untested`.

### 5. Increase legibility
Reading time should drop. Comprehension should rise. If the clean
text is harder to read than the input, the transform failed.

## What Clarity is NOT

* **Not summarisation.** Summarisation throws away content.
  Clarity preserves all content but rearranges it.
* **Not editing for tone.** Clarity doesn't soften or sharpen;
  it restructures.
* **Not paraphrasing.** Direct quotes from the input are
  preserved when they carry load.
* **Not opinion.** Clarity doesn't add the model's judgment about
  whether the content is good; it makes the content's own
  structure visible.

## Output shape

JSON with four top-level fields:

```
{
  "summary":     "1-2 sentences",
  "outline":     [ ... structured list of points ... ],
  "clean_text":  "rewritten version",
  "assumptions": [ { "claim", "status", "would_change_outcome_if_false" }, ... ]
}
```

See `schemas/outputs.json` for the full spec.
