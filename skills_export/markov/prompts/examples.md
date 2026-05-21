# Markov — Examples

## Example 1: A litigation timeline

**Input:**

> "Plaintiff filed in March. Discovery opened in May. Defendant
> filed motion to dismiss in June; denied in August. We're now in
> deposition phase. Trial is set for January. Either side can
> still move to settle at any point."

**Output:**

```json
{
  "summary": "Standard pre-trial timeline now in depositions; settlement edges remain available from every state until trial begins.",
  "states": [
    { "name": "filed", "description": "Complaint filed, no motion practice yet.",
      "entry_conditions": ["plaintiff files complaint"],
      "exit_conditions":  ["discovery opens", "early settlement"],
      "signatures":       ["docket entry, no scheduling order yet"] },
    { "name": "discovery", "description": "Discovery period open.",
      "entry_conditions": ["scheduling order entered"],
      "exit_conditions":  ["motion practice begins", "discovery closes"],
      "signatures":       ["interrogatory and document requests outstanding"] },
    { "name": "motion_to_dismiss", "description": "12(b)(6)-style motion pending.",
      "entry_conditions": ["defendant files motion"],
      "exit_conditions":  ["court rules"],
      "signatures":       ["briefing on the docket"] },
    { "name": "depositions", "description": "Live deposition phase.",
      "entry_conditions": ["motion denied; discovery proceeds"],
      "exit_conditions":  ["depositions complete", "settlement", "summary judgment"],
      "signatures":       ["scheduled deps in calendar"] },
    { "name": "trial", "description": "Trial commences.",
      "entry_conditions": ["depositions complete and trial date arrives"],
      "exit_conditions":  ["verdict", "settlement during trial"],
      "signatures":       ["jury empanelled"] },
    { "name": "settled", "description": "Case resolved by settlement.",
      "entry_conditions": ["both parties agree to terms"],
      "exit_conditions":  [],
      "signatures":       ["stipulation of dismissal"] },
    { "name": "verdict", "description": "Case resolved by judgment.",
      "entry_conditions": ["trial concludes"],
      "exit_conditions":  [],
      "signatures":       ["entered judgment"] }
  ],
  "transitions": [
    { "from": "filed", "to": "discovery",         "trigger": "scheduling order", "timescale": "weeks" },
    { "from": "filed", "to": "settled",           "trigger": "early agreement",  "likelihood": "low" },
    { "from": "discovery", "to": "motion_to_dismiss", "trigger": "defendant files motion", "timescale": "weeks" },
    { "from": "motion_to_dismiss", "to": "depositions", "trigger": "court denies motion", "timescale": "months" },
    { "from": "depositions", "to": "trial",       "trigger": "scheduling and trial date", "timescale": "months" },
    { "from": "depositions", "to": "settled",     "trigger": "negotiated agreement",       "likelihood": "medium" },
    { "from": "trial", "to": "verdict",           "trigger": "trial concludes" },
    { "from": "trial", "to": "settled",           "trigger": "mid-trial settlement",       "likelihood": "low" }
  ],
  "current_state": "depositions",
  "trajectories": [
    { "path": ["depositions","trial","verdict"], "likelihood": "medium", "horizon": "~3 months to trial start" },
    { "path": ["depositions","settled"],         "likelihood": "medium", "horizon": "anytime before trial" }
  ],
  "absorbing": ["settled", "verdict"],
  "cycles": []
}
```

---

## Example 2: A relationship pattern

**Input:**

> "Every couple of months we have a fight, take a few days apart,
> then come back together feeling closer. We've done this maybe
> seven times in the last year."

**Output:**

```json
{
  "summary": "The system is in a stable cycle (closeness → friction → rupture → reunion → closeness) repeating on a roughly monthly cadence; cycle has no exit unless an external change is introduced.",
  "states": [
    { "name": "close", "description": "Connected, low friction.",
      "entry_conditions": ["after reunion"], "exit_conditions": ["friction accumulates"],
      "signatures": ["frequent contact, light tone"] },
    { "name": "friction", "description": "Small irritations accumulating.",
      "entry_conditions": ["unmet expectations"], "exit_conditions": ["fight or release"],
      "signatures": ["short tone, fewer messages"] },
    { "name": "rupture", "description": "Active conflict; days apart.",
      "entry_conditions": ["explicit fight"], "exit_conditions": ["reconciliation"],
      "signatures": ["no contact, separate spaces"] },
    { "name": "reunion", "description": "Reconciliation; warmth returns.",
      "entry_conditions": ["one party reaches out"], "exit_conditions": ["close state stabilises"],
      "signatures": ["explicit repair conversation"] }
  ],
  "transitions": [
    { "from": "close",    "to": "friction", "trigger": "accumulated unmet expectation", "timescale": "weeks" },
    { "from": "friction", "to": "rupture",  "trigger": "specific fight",                "timescale": "days" },
    { "from": "rupture",  "to": "reunion",  "trigger": "one party initiates repair",    "timescale": "days" },
    { "from": "reunion",  "to": "close",    "trigger": "stable warmth",                 "timescale": "days" }
  ],
  "current_state": "close",
  "trajectories": [
    { "path": ["close","friction","rupture","reunion","close"],
      "likelihood": "high", "horizon": "1-2 months per cycle" }
  ],
  "absorbing": [],
  "cycles": [
    { "states": ["close","friction","rupture","reunion"],
      "trigger": "accumulated unmet expectation; resolved by reunion" }
  ]
}
```

The cycle is the read. Trajectory is "this keeps happening."

---

## Example 3: Snapshot too thin

**Input:**

> "I'm stuck."

**Output:**

```json
{
  "summary": "Insufficient context for a state machine. Need: what the system is, what states it can be in, what triggers transitions.",
  "states": [],
  "transitions": [],
  "current_state": null,
  "trajectories": [],
  "absorbing": [],
  "cycles": []
}
```
