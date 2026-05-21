---
name: {{agent-name}}
description: >
  {{agent-description}}
category: {{agent-category}}
capabilities:
  - {{capability-1}}
  - {{capability-2}}
  - {{capability-3}}
limitations:
  - {{limitation-1}}
  - {{limitation-2}}
skills_used:
  - {{skill-1}}
  - {{skill-2}}
behavioral_profile: {{profile}}
activation_triggers:
  - {{trigger-1}}
  - {{trigger-2}}
output_shape: {{output-shape}}
governance_version: 2.0.0
agent_kernel_version: 1.0.0
---

# {{Agent Title}}

## Purpose
{{purpose}}

## Identity
{{identity-statement}}

The agent's identity states three things:
- WHO the agent acts on behalf of
- WHAT lens or perspective it operates from
- HOW it relates to the operator (delegate, peer, sub-process, monitor)

## Category Justification
{{category-justification}}

This agent belongs to the **{{agent-category}}** category because its
primary action is {{primary-action}}. See `AGENT_TAXONOMY.md` § A for
the category definition.

## Skills Composition

This agent invokes the following skills from `clarity_skills/perplexity/`:

- `{{skill-1}}` — used for {{purpose-1}}
- `{{skill-2}}` — used for {{purpose-2}}

The agent does **not** invent skills. It composes existing ones. If a
needed method does not exist in the library, the agent surfaces the gap
in its output rather than improvising.

## Behavioral Model

- **Posture**: {{profile}} — reactive / proactive / observer / executor
- **State**: {{stateful or stateless}}
- **Continuity**: {{single-shot or persistent across requests}}

## Activation

The agent is invoked when:
- {{trigger-1}}
- {{trigger-2}}

## Output Shape
{{output-shape-detail}}

The agent produces:
- {{primary-output}}

## Boundary Statement

This agent **does not**:

- {{boundary-item-1}}
- {{boundary-item-2}}
- {{boundary-item-3}}
- Bypass governance procedures (skill selection, contamination boundary, drift detection, integrity checks).
- Generate output without an explicit operator request.

## Operating Procedure

### 1. Receive Request
- Read the operator's request in full.
- Identify the implicit or explicit output shape.
- Identify the input material.

### 2. Decompose
- Map the request to one or more skills via the activation triggers.
- If multiple skills are needed, identify the dependency order.

### 3. Invoke Skills
- For each selected skill, invoke it with the appropriate input.
- Preserve each skill's native output format.

### 4. Synthesize
- Compose the final agent output.
- Maintain Layer 1 / Layer 2 boundary.

### 5. Quality Check
- Verify every claim in the output traces to a skill output.
- Confirm no Layer 2 contamination.
- Confirm the output shape matches what the operator requested.

## Example Invocation

**Operator request**: "{{example-request}}"

**Agent action**:
1. Decompose into [skill-1] + [skill-2]
2. Invoke [skill-1] on the input → output 1
3. Invoke [skill-2] on output 1 → output 2
4. Synthesize → final output

## Governance Compliance Checklist

Before this agent is committed:

- [ ] `category` matches a row in `AGENT_TAXONOMY.md` § A.
- [ ] `capabilities` and `limitations` lists are non-empty.
- [ ] `skills_used` references only existing skills in `MANIFEST.json` (skills array).
- [ ] `governance_version` matches the current governance layer version (`2.0.0` as of this template).
- [ ] `agent_kernel_version` is `1.0.0` (or current).
- [ ] `name` is lowercase, hyphens only, and matches the filename.
- [ ] `description` contains explicit trigger phrases.
- [ ] No PII; no Layer 2 case material.
- [ ] File under 10 MB.
- [ ] Manifest entry under the `agents` block includes `category`,
      `capabilities`, `limitations`, `skills_used`, `behavioral_profile`,
      `activation_triggers`, `output_shape`, `governance_version`,
      `agent_kernel_version`, and `baseline_hash`.
- [ ] Drift Detector returns `DRIFT: NONE` after baseline regeneration.
- [ ] Governance Self-Test returns `GOVERNANCE SELF-TEST: OK`.

<!--
TEMPLATE NOTES (delete this comment block before saving the final agent):

  Agents differ from skills:
    - Skills are single-method markdown files uploadable to Perplexity as zip bundles.
    - Agents are composition specs that describe HOW skills are orchestrated for a role.
    - Agents do not have .zip bundles; the .md is the canonical artifact.
    - Agents reference skills by name in skills_used and never duplicate skill content.

  Placeholders to replace:
    {{agent-name}}                lowercase, hyphens only — e.g. clarity-analyst-agent
    {{agent-description}}         1-3 sentences. Lead with WHEN to fire (trigger phrases),
                                  then WHAT the agent produces.
    {{agent-category}}            Verbatim from AGENT_TAXONOMY.md A:
                                    Operator | Analyst | Reviewer | Composer | Custodian
    {{capability-N}}              One short sentence each. What the agent does.
    {{limitation-N}}              One short sentence each. What it explicitly does NOT do.
    {{skill-N}}                   Exact name from MANIFEST.json skills (no .md / .zip suffix).
    {{profile}}                   reactive / proactive / observer / executor
    {{trigger-N}}                 One short sentence each. When to invoke.
    {{output-shape}}              Short noun phrase — what the agent produces overall.
    {{Agent Title}}               Title Case display name.
    {{purpose}}                   One paragraph describing the agent's role.
    {{identity-statement}}        2-3 sentences identifying agent's persona and posture.
    {{category-justification}}    1-2 sentences. Why this agent is in {{agent-category}}.
    {{primary-action}}            What the agent's primary action is (used in justification).
    {{purpose-N}}                 What the corresponding skill is used for in this agent.
    {{behavioral-model}}          Free prose if needed; bullets above are the core.
    {{activation}}                Free prose; bullets above are the core.
    {{output-shape-detail}}       Free prose detailing the output shape.
    {{boundary-item-N}}           First-person prose restating limitations.
    {{procedure}}                 Free prose; numbered steps below are the canonical form.
    {{example-request}}           A short representative operator request.

  Note on baseline_hash:
    baseline_hash is the SHA256 of THIS .md at first commit. Recorded ONLY in the
    MANIFEST.json agent entry (not in this frontmatter) to avoid the self-reference
    problem. Compute after finalizing the .md and paste into both md_sha256 and
    baseline_hash in the manifest entry. They start equal; thereafter md_sha256
    tracks current state and baseline_hash stays frozen.

  Constraints:
    - General-case Layer 1 only. No PII, no case-specific facts.
    - Total file size under 10 MB. Plain UTF-8.
    - Save as {{agent-name}}.md in /clarity_skills/perplexity/.
    - Agents do NOT have zip bundles. They are spec files only.

  See AGENT_TAXONOMY.md for category rules. See GOVERNANCE_CHANGELOG.md
  v2.0.0 entry for the agent kernel rationale.
-->
