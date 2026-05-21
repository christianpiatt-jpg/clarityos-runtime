# ClarityOS — Skills Export

> **These files are for external LLM products (e.g., Perplexity) to
> emulate the founder's internal reasoning modes. ClarityOS does not
> load or depend on them.**

---

## What this directory is

A standalone documentation package describing five reasoning modes
the founder uses when thinking through problems:

1. `emotional_physics/` — modeling affect, motivation, conflict as forces
2. `clarity/`           — structural simplification + refactoring
3. `markov/`            — temporal / sequence / state-transition reasoning
4. `physics/`           — hard constraints, invariants, feasibility
5. `galileo_meta/`      — orchestrator that selects among the other four

Each directory follows an identical layout:

```
{skill_name}/
   manifest.json              ← machine-readable contract
   model_spec.md              ← human-readable description of the mode
   prompts/
      system_prompt.txt       ← drop-in system prompt for an external LLM
      examples.md             ← before/after demonstrations
   schemas/
      inputs.json             ← JSON Schema for input shape
      outputs.json            ← JSON Schema for output shape
   docs/
      theory.md               ← short whitepaper / first-principles
      usage_patterns.md       ← when to invoke this mode
```

A top-level `manifest.json` in this directory enumerates all five
skills + their version + their relationship to each other.

---

## What this directory is **not**

* **Not a runtime dependency of ClarityOS.** No backend Python, no
  web TypeScript, no phone TypeScript, no desktop TypeScript ever
  imports from this directory. The architectural boundary at
  [`/ARCHITECTURE.md`](../ARCHITECTURE.md) makes this explicit and
  authoritative.
* **Not a plugin system.** ClarityOS does not have a plugin system.
  The skills here are descriptions of behaviour, not loadable code.
* **Not a Perplexity-specific format.** The layout (`manifest.json`
  + `prompts/` + `schemas/` + `docs/`) is intentionally generic so
  it can be consumed by any LLM product that wants to brief itself
  with a behavioural contract.

---

## How an external LLM uses these

Two paths:

### Path A — paste the system prompt

Open `{skill}/prompts/system_prompt.txt`, paste it into the system
prompt slot of the external LLM, then chat normally. The LLM will
adopt that reasoning mode.

### Path B — describe the bundle

Tell the external LLM:

> "Assume I have five internal reasoning skills: Emotional Physics,
> Clarity, Markov, Physics, Galileo Meta. Each has a manifest, an
> input/output schema, and examples. When I say 'use Emotional
> Physics' or 'run this through Clarity', adopt the corresponding
> system prompt below: …"

Then paste each `system_prompt.txt` body. The Galileo Meta system
prompt also describes when to combine the four base skills.

The bundles are intentionally short enough that all five can fit
inside a single context window.

---

## Versioning

The export bundle versions independently of ClarityOS. The current
release is **v1.0** — see `manifest.json`. Bumping happens when:

* a system prompt's behavioural contract changes,
* an input/output schema field is added/renamed/removed,
* a new skill is added to the bundle, or
* an existing skill is removed.

Patch-level edits (typo fixes, additional examples) don't bump
the version; treat them like editorial changes.

---

## Boundary check

If you find yourself writing ClarityOS runtime code that does any of:

```python
import json
with open("../skills_export/.../manifest.json") as f: ...
```

```typescript
import manifest from "../../skills_export/.../manifest.json";
```

…stop. That's a layer violation. Skills are documentation for
external systems; ClarityOS reasons through kernel functions
(see `intelligence_kernel.py` — `summarize_thread`, `run_thread_message`,
etc.). If you need a new reasoning mode inside the OS, build it as a
kernel function and wire through `model_router.TASK_DEFAULTS`. Do
not load this directory.

The boundary is enforced by [`/ARCHITECTURE.md`](../ARCHITECTURE.md);
the audit command there should always return empty for ClarityOS
source files.
