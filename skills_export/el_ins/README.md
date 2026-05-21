# EL/INS Ratio Framework

**Status:** v1.0 — canonical external bundle.

A reasoning-stability operator that classifies a piece of text by its
ratio of **Emotive Language (EL)** to **Institutional Signal (INS)**
and routes the consuming model into one of three reasoning modes:

| Classification | Mode       | What the model does                              |
|----------------|------------|--------------------------------------------------|
| `high_el`      | `stabilize`| reduce narrative, add precedent/constraint, run regression pipeline |
| `high_ins`     | `expand`   | add context, narrative framing, surface implications |
| `balanced`     | `normal`   | proceed; optional regression / precedent mapping |

## Files

| File                | Purpose                                              |
|---------------------|------------------------------------------------------|
| `system_prompt.md`  | The full system prompt an LLM uses when it operates as the EL/INS analyzer. |
| `schema.json`       | JSON Schema (Draft 07) for the analyzer's structured output. |
| `README.md`         | This file.                                           |

## Intended consumers

This bundle is the **canonical external spec**. Anyone (Claude API,
Langbridg, third-party LLMs) can use it directly without touching
ClarityOS:

1. Load `system_prompt.md` as the system prompt for the model.
2. Send the text to analyze as the user message.
3. Parse the model response against `schema.json`.

## Relationship to the ClarityOS kernel module

ClarityOS ships a sibling **kernel module** (`el_ins/`) that uses the
same prompt and schema for in-runtime analysis, plus a deterministic
Python fallback for offline / phone runtime / cost-sensitive paths.
The kernel module loads `system_prompt.md` from this bundle at import
time — meaning **this file is the single source of truth** for both
the external skill and the internal runtime.

Per [`ARCHITECTURE.md`](../../ARCHITECTURE.md), ClarityOS runtime
modules MUST NOT import any other file from `/skills_export/`. The
EL/INS kernel module reads `skills_export/el_ins/system_prompt.md` as
plain text — not as a Python import — which is allowed.

## Versioning

The bundle pins `version` in line with the broader `/skills_export/`
manifest at `/skills_export/manifest.json`. Breaking schema changes
require a major version bump and a parallel kernel update.

## License / use

Same license as ClarityOS. See repo root.
