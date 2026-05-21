# Emotional Physics — Examples

## Example 1: Founder pulling back from a co-founder

**Input:**

> "My co-founder keeps telling me we need to ship the demo by
> Friday. I keep agreeing in meetings then doing other work. We
> haven't actually disagreed about anything yet, but every
> conversation feels colder than the last one."

**Output:**

```json
{
  "summary": "Two forces are pushing in opposite directions and a rigid constraint is preventing the conflict from surfacing; the trajectory is toward inversion of the working relationship within 1-2 weeks.",
  "forces": [
    {
      "name": "co-founder's deadline pressure",
      "source": "external",
      "direction": "ship by Friday",
      "magnitude": "high",
      "duration": "chronic for the past several meetings"
    },
    {
      "name": "subject's deprioritisation of the demo",
      "source": "internal",
      "direction": "delay / redirect work",
      "magnitude": "medium",
      "duration": "ongoing"
    }
  ],
  "constraints": [
    {
      "name": "norm against open disagreement",
      "prevents": "either party voicing the conflict",
      "rigidity": "high",
      "would_relax_if": "an external trigger (missed deadline, third-party intervention) makes silence costlier than confrontation"
    }
  ],
  "trajectories": [
    {
      "subject": "the working relationship",
      "heading": "toward inversion (warm collaboration → contempt)",
      "velocity": "slow but accelerating",
      "horizon": "1-2 weeks",
      "what_breaks_first": "the shared assumption that they are aligned"
    }
  ],
  "risk_zones": [
    {
      "condition": "Friday arrives and demo is not shipped",
      "why_fragile": "rigid constraint forced to break with no rehearsed language for the disagreement",
      "watch_for": "first explicit accusation; tone of the first message after the missed deadline"
    }
  ]
}
```

---

## Example 2: User describing a quiet morning

**Input:**

> "I've been waking up early and just sitting with coffee for an
> hour before doing anything. It's been three weeks."

**Output:**

```json
{
  "summary": "Subject has installed a recovery / decompression ritual; the structural read is consistent with sustained prior pressure that is now releasing.",
  "forces": [
    {
      "name": "carry-over load from prior period",
      "source": "internal",
      "direction": "demand for recovery",
      "magnitude": "medium",
      "duration": "chronic, possibly months"
    }
  ],
  "constraints": [
    {
      "name": "(none currently active)",
      "prevents": "—",
      "rigidity": "low",
      "would_relax_if": "—"
    }
  ],
  "trajectories": [
    {
      "subject": "subject's internal load",
      "heading": "downward",
      "velocity": "steady",
      "horizon": "weeks",
      "what_breaks_first": "the ritual itself, when load is low enough that mornings get reclaimed for activity"
    }
  ],
  "risk_zones": []
}
```

The mode reports clean configurations as cleanly as fraught ones.

---

## Example 3: Input too thin

**Input:**

> "I'm tired."

**Output:**

```json
{
  "summary": "Insufficient context to produce a structural read. Need: what's exerting force, against what constraints, over what horizon.",
  "forces": [],
  "constraints": [],
  "trajectories": [],
  "risk_zones": []
}
```

Don't invent. The caller asked for structure; if there's no
structure visible, say so.
