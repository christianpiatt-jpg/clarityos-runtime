# Physics — Examples

## Example 1: A "we can't" plan

**Input:**

> "We can't ship the new dashboard by Q1 because we don't have a
> designer, our backend can't handle the load, and legal needs to
> review it."

**Output:**

```json
{
  "summary": "One genuine hard constraint (legal review timeline) plus two assumptions presented as constraints (designer and backend). Feasible with changes.",
  "feasibility": "feasible_with_changes",
  "invariants": [
    {
      "claim": "Personally identifiable data displayed in the dashboard must be access-controlled per user.",
      "why_it_holds": "Privacy compliance + existing platform rule.",
      "test": "Every dashboard query goes through the per-user authorization layer."
    }
  ],
  "hard_constraints": [
    {
      "claim": "Legal must review user-data-rendering surfaces before launch.",
      "source": "Internal compliance policy + applicable privacy regulation.",
      "violation_consequence": "Launch is blocked; if shipped anyway, legal exposure + remediation cost."
    }
  ],
  "soft_constraints": [
    {
      "claim": "Backend currently sized for 5x current peak load, dashboard would push toward 8x at Q1 traffic.",
      "what_it_costs_to_relax": "Vertical scaling + caching; 1-2 engineering weeks + non-trivial infra cost."
    }
  ],
  "assumptions": [
    {
      "claim": "We need a dedicated designer to ship the dashboard.",
      "actually_negotiable": true,
      "what_changes_if_relaxed": "An engineer using existing design system components ships a less polished but adequate version on schedule."
    },
    {
      "claim": "Legal review takes the full window.",
      "actually_negotiable": true,
      "what_changes_if_relaxed": "Pre-engaging legal during build (1 hour weekly) compresses formal review at the end."
    }
  ],
  "failure_modes": [
    {
      "trigger": "Launch without legal sign-off",
      "description": "Compliance violation at first user impression.",
      "blast_radius": "Company-wide regulatory exposure; engineering rollback.",
      "reversible": false
    },
    {
      "trigger": "Backend not scaled before launch",
      "description": "Latency spike under traffic; 5xx rate climbs; user trust hit.",
      "blast_radius": "All dashboard users for the duration of the spike.",
      "reversible": true
    }
  ]
}
```

The bulk of the value is in the `assumptions` block — two of the
three "can't" reasons aren't actually hard.

---

## Example 2: A genuinely infeasible plan

**Input:**

> "Let's offer 0% APR for the first year, no credit check, on
> loans up to $50k, and break even in 18 months."

**Output:**

```json
{
  "summary": "Mathematically infeasible at the given parameters. At least one of {APR, credit policy, principal cap, breakeven horizon} must change for this to work.",
  "feasibility": "infeasible",
  "invariants": [
    {
      "claim": "Cost of capital + default loss + operating expense ≤ revenue",
      "why_it_holds": "Required for a lending business to break even.",
      "test": "Run the unit economics on representative cohorts."
    }
  ],
  "hard_constraints": [
    {
      "claim": "Default rate without credit checks is materially higher than with them.",
      "source": "Empirical lending industry data.",
      "violation_consequence": "Loss provision wipes out interest revenue."
    },
    {
      "claim": "Cost of capital is non-zero.",
      "source": "Capital markets.",
      "violation_consequence": "Negative gross margin on every loan during the 0% period."
    }
  ],
  "soft_constraints": [
    {
      "claim": "Operating expense scales with portfolio size.",
      "what_it_costs_to_relax": "Significant fixed-cost reduction or automation; unrealistic in 18 months."
    }
  ],
  "assumptions": [
    {
      "claim": "Customer acquisition is free.",
      "actually_negotiable": false,
      "what_changes_if_relaxed": "If marketing cost is included, breakeven horizon extends further."
    }
  ],
  "failure_modes": [
    {
      "trigger": "Plan executed as stated",
      "description": "Negative unit economics across the entire 0% period; default losses on the no-credit-check book exceed eventual interest revenue.",
      "blast_radius": "Company-wide; equity erosion + likely insolvency.",
      "reversible": false
    }
  ]
}
```

---

## Example 3: A clean, feasible plan

**Input:**

> "We're going to migrate the database from MySQL 5.7 to 8.0 over
> a maintenance window this Sunday. We've tested the migration in
> staging twice. Rollback plan is to revert the AMI."

**Output:**

```json
{
  "summary": "Plan is feasible and well-structured. One soft constraint (maintenance window length) and one assumption worth flagging.",
  "feasibility": "feasible",
  "invariants": [
    {
      "claim": "Application binary is compatible with MySQL 8.0.",
      "why_it_holds": "Verified by staging dry-runs.",
      "test": "Application smoke tests against 8.0 staging."
    }
  ],
  "hard_constraints": [
    {
      "claim": "Migration completes within the maintenance window.",
      "source": "User-facing SLA.",
      "violation_consequence": "Extended downtime; SLA breach."
    }
  ],
  "soft_constraints": [
    {
      "claim": "Rollback is via AMI revert.",
      "what_it_costs_to_relax": "If a faster path is needed, a binlog-based rollback would require additional setup."
    }
  ],
  "assumptions": [
    {
      "claim": "Staging dataset is representative of production size.",
      "actually_negotiable": true,
      "what_changes_if_relaxed": "If staging is smaller, real migration may exceed the window; spot-check production size before Sunday."
    }
  ],
  "failure_modes": [
    {
      "trigger": "Migration runs long",
      "description": "Window exceeded; partial migration state.",
      "blast_radius": "All users.",
      "reversible": true
    }
  ]
}
```
