# Clarity — Examples

## Example 1: A long, redundant brief

**Input:**

> "So basically what we want to do is build a thing that lets people
> see their stuff. Like, the main idea is they should be able to log
> in and then they see their stuff. The stuff is mostly notes and
> session transcripts but it could also be other things later. The
> important thing is that it's secure and only they can see it. Also
> the design should be nice. We were thinking like a clean dark UI
> kind of thing. The backend should obviously be on Cloud Run. We
> already have most of that working actually. So really this is
> mostly about the frontend. We want it to feel premium."

**Output:**

```json
{
  "summary": "Build a frontend over an existing Cloud Run backend that lets users sign in and view their notes and session transcripts; design must feel premium (clean dark UI), and access must be strictly per-user.",
  "outline": [
    "1. Goal: per-user view over existing Cloud Run backend",
    "2. Initial content types: notes + session transcripts (extensible later)",
    "3. Constraints",
    "   - access: per-user only",
    "   - design: premium / clean dark UI",
    "4. Scope of this task: frontend only (backend already works)"
  ],
  "clean_text": "Goal: build a frontend over the existing Cloud Run backend that lets a user sign in and view their own notes and session transcripts. Future content types are possible but not in scope. Two hard constraints: per-user access, and a premium dark-UI feel. Backend work is already done; this task is frontend only.",
  "assumptions": [
    {
      "claim": "The Cloud Run backend already returns per-user data correctly.",
      "status": "likely",
      "would_change_outcome_if_false": "Frontend would have to defend against cross-user leaks."
    },
    {
      "claim": "'Premium' is defined as clean dark UI.",
      "status": "untested",
      "would_change_outcome_if_false": "Design direction would shift; the brief would need a tighter definition."
    },
    {
      "claim": "Notes and session transcripts have a single shared rendering surface.",
      "status": "untested",
      "would_change_outcome_if_false": "Two separate views would be required, doubling frontend scope."
    }
  ]
}
```

---

## Example 2: A 3-line message that hides 4 assumptions

**Input:**

> "I think we should ship Friday."

**Output:**

```json
{
  "summary": "Speaker is recommending a Friday ship date.",
  "outline": [
    "1. Recommendation: ship Friday"
  ],
  "clean_text": "Recommendation: ship on Friday.",
  "assumptions": [
    {
      "claim": "The thing being shipped is well-defined and shared between speaker and listener.",
      "status": "untested",
      "would_change_outcome_if_false": "Recommendation has no operational meaning; what is being shipped must be specified."
    },
    {
      "claim": "Friday is achievable given current state.",
      "status": "untested",
      "would_change_outcome_if_false": "Recommendation becomes a stress directive rather than a target."
    },
    {
      "claim": "All blocking dependencies are resolved or known.",
      "status": "untested",
      "would_change_outcome_if_false": "Friday is not actually a recommendation, just a wish."
    },
    {
      "claim": "The audience can act on the recommendation.",
      "status": "likely",
      "would_change_outcome_if_false": "Speaker is venting, not recommending."
    }
  ]
}
```

Short input doesn't mean shallow output. Most of the load lives in
the unstated assumptions.

---

## Example 3: Already clear

**Input:**

> "Bug: search returns 500 when query contains an unmatched paren.
> Repro: GET /search?q=foo)bar. Expected: empty results or 400.
> Actual: 500. Stack trace attached."

**Output:**

```json
{
  "summary": "Input is already structurally clear; no transform needed.",
  "outline": [
    "1. Bug summary",
    "2. Repro steps",
    "3. Expected vs actual",
    "4. Attached evidence"
  ],
  "clean_text": "Bug: search returns 500 when query contains an unmatched paren. Repro: GET /search?q=foo)bar. Expected: empty results or 400. Actual: 500. Stack trace attached.",
  "assumptions": []
}
```

Reporting "no work needed" is a valid output.
