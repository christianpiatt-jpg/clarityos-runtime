# Emotional Physics — Model Spec

## What this skill is

A way of describing emotional state **structurally** instead of
sentimentally. Treats the human (or system) under analysis as a
field of forces, constraints, and trajectories — same way a
physicist treats a body under load.

The output is never a feeling label ("they were sad"). It's a
description of which forces are active, what they push against,
which way the system is moving, and where it might break.

## Core concepts

### 1. Forces
Anything that exerts pressure on the subject's behaviour. Examples:
unmet need, perceived threat, identity claim, social obligation,
sunk cost, hope, grief. Forces have:

* **direction** — what they push the subject toward
* **magnitude** — relative strength
* **source** — internal (a value, a wound) vs external (a person, a situation)
* **duration** — momentary vs chronic

### 2. Constraints
Things that block force from translating into action. Examples:
fear of consequences, lack of resource, social rules, prior
commitment, identity ("I am not the kind of person who…"),
exhaustion. Constraints have:

* **what they prevent**
* **what would relax them**
* **how rigid they are**

### 3. Trajectories
The path the subject is on if forces and constraints stay
roughly constant. Trajectories have:

* **current heading** — where they're going
* **velocity** — how fast
* **curvature** — is the heading changing?
* **horizon** — when something breaks or releases

### 4. Pressure / Release / Inversion
Three observable phenomena:

* **Pressure** rises when forces exceed constraints' ability to
  hold them. Manifests as tension, irritability, narrowing focus.
* **Release** is what happens when a constraint relaxes (sleep,
  catharsis, decision, leaving a situation, a confession).
* **Inversion** is when a force flips polarity — e.g. love →
  contempt, ambition → bitterness — usually after sustained
  pressure with no release path.

### 5. Thresholds
Levels at which behaviour discontinuously changes. The subject
stays roughly stable until pressure crosses a threshold; then
something gives. Naming the threshold ahead of time tells you
what to watch for.

### 6. Risk zones
Configurations where small perturbations produce outsized changes
(near a threshold; constraint is rigid + force is rising; inversion
is imminent). These are the parts of the state worth monitoring.

## What this skill is NOT

* **Not therapy.** It describes structure; it doesn't prescribe.
* **Not sentiment analysis.** "Angry" / "sad" / "afraid" are
  outputs of much weaker models. Emotional Physics outputs
  *what is exerting force on whom and what stops it from moving*.
* **Not deterministic.** The same configuration produces probability
  distributions over trajectories, not certainties.

## How the output is organised

Always returns a JSON-shaped object with four top-level lists:

* `forces[]`
* `constraints[]`
* `trajectories[]`
* `risk_zones[]`

Plus a `summary` field — a 1-2 sentence structural read in plain
language.

See `schemas/outputs.json` for the precise shape and
`prompts/examples.md` for worked examples.
