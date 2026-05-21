# Agent Taxonomy

This document defines the canonical category system that classifies every
**agent** in `clarity_skills/perplexity/`. Every agent — existing or new —
must declare exactly one `category` value, drawn from the table in § A,
in both its frontmatter and its `MANIFEST.json` entry under the `agents`
block.

The Agent Kernel was introduced in **governance v2.0.0**. The current
`taxonomy_version` for agents is **1.0.0** (initial release).

The taxonomy serves four purposes, parallel to `SKILL_TAXONOMY.md`:

1. **Prevents category drift** in the agent kernel.
2. **Prevents overlapping agent scopes.**
3. **Ensures discoverability** via category-based dispatch.
4. **Enables future automation** — agent routing, composition planning,
   multi-agent workflow construction.

---

## A. Top-Level Categories

| Category | Definition |
|---|---|
| **Operator** | Agents that act on behalf of the human operator. Receive requests, compose skills, produce operator-grade outputs. The default agent persona for direct user interaction. |
| **Analyst** | Agents that perform multi-step analytical work — composing extraction skills, synthesizing across documents, producing structured analyses without making operational decisions on the operator's behalf. |
| **Reviewer** | Agents that review and audit work products — briefs, decisions, outputs from other agents — applying quality, governance, and consistency checks. |
| **Composer** | Agents that orchestrate multi-agent workflows — planning agent invocation sequences, managing handoffs between agents, composing larger procedures from existing agents and skills. |
| **Custodian** | Agents that maintain library and system health — running integrity checks, monitoring drift, auditing governance compliance, surfacing library gaps. |

An agent belongs in exactly one of the categories above. If an agent
seems to span multiple categories, classify it by its **primary action** —
what the agent does — not by what inputs it receives.

### Examples (with reasoning)

- An agent that **receives operator requests and composes skills to produce briefs** → primary action is delegation from the operator. Category: **Operator**.
- An agent that **chains contradictions + anchors + timeline skills to produce a structural document analysis** → primary action is multi-step analysis without operational decisions. Category: **Analyst**.
- An agent that **audits another agent's output for governance compliance** → primary action is review/audit. Category: **Reviewer**.
- An agent that **plans a workflow involving an Operator agent, two Analyst agents, and a Reviewer** → primary action is orchestration. Category: **Composer**.
- An agent that **runs the drift detector nightly and reports library health** → primary action is library maintenance. Category: **Custodian**.

---

## B. Rules for Adding a New Category

A new category may be proposed when:

1. At least **two** existing or planned agents clearly fall outside every
   existing category, AND
2. The new category has a primary-action definition that does not overlap
   with any existing category, AND
3. The category name is durable.

To add a category:

1. Open a governance change (v2.X+ release).
2. Append the new row to § A above with its definition.
3. Add an "Examples" entry illustrating the boundary.
4. Bump `taxonomy_version` per § D.
5. Run `GOVERNANCE_SELF_TEST.ps1`.
6. Regenerate `BASELINE_STATE.json`.
7. Add an entry to `GOVERNANCE_CHANGELOG.md`.

Single-agent categories are not permitted. If only one agent needs the
new label, the agent belongs in an existing category.

---

## C. Rules for Merging or Deprecating Categories

Same patterns as `SKILL_TAXONOMY.md` §§ C–D:

- **Merge** when two categories overlap to the point that classification
  is ambiguous.
- **Deprecate** when no agent is classified under a category and no
  reasonable future agent is expected to fall under it.

Both operations bump `taxonomy_version` (major) and require updating any
affected agents' `category` field in frontmatter and manifest.

---

## D. Versioning

This document carries an implicit `taxonomy_version` recorded in
`BASELINE_STATE.json` under `governance_files["AGENT_TAXONOMY.md"]`.

- **Patch** — typo / formatting / clarification of existing definitions.
- **Minor** — additive: a new category that doesn't reclassify any
  existing agent.
- **Major** — breaking: a category renamed, merged, removed, or its
  definition narrowed in a way that reclassifies existing agents.

---

## E. Mapping of Existing Agents → Categories

| Agent | Category | Primary Action |
|---|---|---|
| `clarity-operator-agent` | Operator | Acts on behalf of the human operator: receives requests, composes skills from `clarity_skills/perplexity/`, produces operator-grade outputs. |

This mapping is **authoritative**. If an agent's category is updated,
both this table AND the agent's frontmatter AND its manifest entry must
change in the same release.

---

## F. Relationship to Skills

**Agents compose skills. Skills do not compose agents.**

- **Skills** (`SKILL_TAXONOMY.md`) are individual methods. One skill =
  one method = one `.md` + `.zip` artifact pair, uploadable to
  Perplexity as a single skill.
- **Agents** (`AGENT_TAXONOMY.md`) are compositional roles. One agent =
  one role = one `.md` artifact (no zip), referencing one or more
  skills by name in its `skills_used` field.

An agent does **not** replace a skill. Skills remain the unit of method;
agents are the unit of composition.

An agent's `skills_used` field is validated by the governance self-test:
every skill named must exist in `MANIFEST.json` under the `skills`
array. Adding an agent that references a non-existent skill is a
governance violation.

---

## G. Boundary

The taxonomy is a **Layer 1** artifact. Agent categories describe
**roles**. They never describe **cases**. A category like
"VA-Litigation Operator" would violate the boundary — it would tie a
general-purpose agent role to a particular-case engagement. If you find
yourself wanting to add such a category, the underlying need belongs in
the personal envelope (Layer 2), not in the agent kernel.
