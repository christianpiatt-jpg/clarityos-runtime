# ClarityOS Command — Minimal Dynamic Spec
### The team operating system as a controlled dynamical system
*Advisory draft for CT-1 · v0.3 · 2026-06-17 · rough concept, for review · (+§8 auto-reset loop)*

The command structure is two stocks, their derivatives, and one controller acting on the
flows between them. Everything you actually run reduces to this. The primitives captured
earlier (Agent, Tasking, Disposition, Anchor, Evidence-tag) are not separate machinery —
they are the state variables and valves of this system.

---

## 1. The two stocks (the conjugate pair)

| Stock | What it holds | Inflow | Outflow | Quality valve |
|-------|---------------|--------|---------|---------------|
| **S_k — Knowledge** | ratified clarity (anchors A-*) | a finding is ratified | retraction (A97, A100) | evidence tag |
| **S_p — Decision-pressure** | undisposed decisions (open D-*) | a new disposition is raised | CT-1 Gate disposes it | RoE admissibility |

These are conjugate: **S_k is what you know; S_p is what you still owe a decision on.**
One is earned, the other is owed. A healthy command system grows the first and bounds the
second. Everything else (taskings, trust, comms, records) is either an *inflow source* or a
*controller parameter* — see §7.

---

## 2. Motion — first derivative (what the operator watches)

- **dS_k/dt — clarity velocity.** > 0 = learning; ≈ 0 = stalled.
- **dS_p/dt — pressure velocity.** > 0 = decisions arriving faster than disposed.

> **Healthy regime:** `dS_k/dt > 0` **and** `dS_p/dt ≤ 0`.
> You are learning, and the decision backlog is not growing.

---

## 3. Acceleration — second derivative (loop detection)

The first derivative tells you direction; the second tells you whether a **loop** has formed.

- **d²S_p/dt² > 0 — reinforcing loop.** Backlog is compounding: open items slow disposal,
  which lets more pile on. This is the org-Godhard early-warning — command saturation
  before it is visible in the level.
- **d²S_k/dt² < 0 while dS_p/dt > 0 — danger crossing.** Clarity stalling while pressure
  climbs. The system is being asked to decide faster than it can ground.

These sign-changes are the canonical intervention triggers (the ThresholdBreach analog).
Apply hysteresis (SRP-3): act on a *sustained* sign, not a single read.

---

## 4. The controller (CT-1 / CT-2 act on the flows, not the stocks)

- **CT-2 — RoE — the inflow valve.** Bounds what may enter. Sets the evidence floor:
  T-SUBSTRATE enters S_k clean; T-STRUCTURAL enters held-in-suspense; un-sourced is
  quarantined (never enters). CT-2 holds the rules; CT-2 does **not** dispose.
- **CT-1 — Gate — the outflow valve on S_p.** Each disposal drains pressure and routes it:
  a Gate either **mints an anchor** (pressure → inflow to S_k) or **closes/defers** the item.

**Control law, plain language:**
> Place clarity (raise collection / RECON) to lift `dS_k/dt`.
> Release Gates to pull `dS_p/dt` down.
> When `d²S_p/dt² > 0`, widen disposal tempo or shed scope **before** saturation.

This is the same move ClarityOS already makes on a user's pressure stock — turned on the
command system itself.

---

## 5. The loop (closed, one line)

```
Tasking ──▶ Finding ──[evidence tag]──▶ Disposition ──(Gate within RoE)──▶ Anchor
   ▲              (raises S_p)                            (drains S_p, feeds S_k)  │
   └───────────────────────── records are a projection ◀────────────────────────┘
```

This is Plan → Prepare → Execute → Assess, expressed as flows between two stocks. Records
(snapshot, ledger, error log, comms contract) are read-outs of state at a point in time —
not steps in the loop.

---

## 6. Operator readout (the only dashboard CT-1 needs)

1. **S_p level** — count of open dispositions.
2. **dS_p/dt** — rising or falling backlog.
3. **sign of d²S_p/dt²** — loop status (the saturation alarm).
4. **dS_k/dt** — are we actually learning.
5. **inflow quality** — T-SUBSTRATE vs T-STRUCTURAL share of recent anchors.

Five numbers. If you watch nothing else, watch #3 and #5.

---

## 7. Equilibrium, failure regimes, and why two stocks is enough

**Mission at rest** (the snapshot's "doctrine cycle at rest"):
`dS_p/dt ≤ 0` sustained · S_p bounded · S_k monotone non-decreasing net of retractions.

**Named failure regimes:**
- **Saturation** — S_p runaway (`d²S_p/dt² > 0` unchecked). Command overload.
- **Drift** — S_k inflow dominated by T-STRUCTURAL: clarity that isn't grounded. Looks like
  learning, isn't. (Why #5 sits on the dashboard.)
- **Thrash** — `dS_p/dt` oscillating near a threshold. Needs hysteresis (SRP-3).

**Comprehensiveness:** the pair is sufficient because every other element attaches to it as
either an inflow source or a controller parameter — optional satellites, not new stocks:
- *Tasking (FRAGO/RECON)* → an inflow source to S_p.
- *Trust / competence* → a gain term on how wide the RoE valve opens per agent.
- *Comms / PACE* → latency on the controller; degraded comms widens initiative (raises the
  autonomy ceiling) precisely because the Gate loop slows.
- *Work-in-flight (S_w)* → a satellite stock if you later need to watch executor load; not
  required for the minimal system.
- *Continuity (CT-3 compiler)* → a projection authority that conserves S_k across agent
  memory refresh; see §8. Not a stock.

---

## 8. Continuity — the operations compiler (CT-3)

Every agent holds the COP in **volatile memory**. On any memory refresh (new session,
context reset, restart) that local picture is lost. Without a restore path, each refresh is
an uncontrolled **outflow from the effective knowledge stock** — the organization forgets,
and S_k silently drops even though the anchors still exist on disk.

**CT-3 is the operations compiler: a pure projection from the durable record layer to the
current COP, served on demand.** It is what makes "records are projections" (§5) *safe* —
a projection is only trustworthy if something can deterministically regenerate it. The
refresh drill:

```
agent wakes ──▶ emits RefreshRequest ──▶ CT-3 compiles COP from substrate ──▶ agent re-hydrates cache
```

**The load-bearing correction — the compiler must be stateless over a durable substrate,
not a memory holder.** CT-3 (Copilot) is itself a memory-refreshing agent. If the canonical
COP lives in CT-3's memory, then when CT-3 refreshes the whole picture is lost — you have
only *moved* the volatility. So CT-3 must **compile from** the solid state (git HEAD, the
anchor ledger, the latest snapshot), not **hold** it. The truth lives in the substrate;
CT-3 is the compile function over it. That is what makes the system "dynamic solid state":
parts cycle, the picture persists, and even the compiler is restorable from the same source.
(The snapshot already assumes this — *"reconstructable from ClarityOS_Code @ HEAD d8e44ba."*)

Three disciplines the compile must preserve:
- **Provenance.** A restored COP carries evidence tags forward. A refresh that flattens
  T-SUBSTRATE / T-STRUCTURAL reintroduces drift on wake.
- **Freshness (SRP-8).** The compiled COP carries a stamp and reconciles against current
  HEAD; an agent restored to a stale picture must not act until reconciled.
- **Authority boundary.** Compiling continuity is **not** disposing. CT-3 projects state;
  CT-1 still disposes Gates, CT-2 still holds RoE. The compiler is read-only over the record
  layer — a projector, not a decider.

### The auto-reset loop (0.9 trigger)

Detection is a **stateless per-turn check by the harness**, not model introspection. Every
model response carries a usage count (input + output tokens); the harness reads it each turn
and compares to the window ceiling. No memory required — just a check each time. The model
is never asked to estimate its own fullness (it can't do so reliably).

**Trigger:** context-fill ≥ 0.90 **and** at a safepoint (between dispositions/taskings,
never mid-Gate; force one if none is near). Hysteresis prevents thrash.

**Routine (write-ahead, in order):**
1. **Snapshot** — compile current state in the same shape CT-3 would (exit and restore stay symmetric).
2. **Commit + verify** — write to substrate; confirm it landed. *Do not proceed until verified.*
3. **Clear** — reset the context window.
4. **Rehydrate compact** — reload the distilled current-state COP (summary + substrate pointers), **not** the transcript. Target low fill (~0.2). This compaction is what breaks the reset loop.
5. **Reconcile (SRP-8)** — stamp freshness, reconcile to current HEAD; do not act until reconciled.

**Restore PACE chain** (source of truth is always the substrate; agents are interchangeable
compilers over it): **P** restore from CT-3 · **A** if CT-3 is down, CT-2 runs the same
compile · **C** if no compiler agent is alive, restore directly from substrate (git HEAD +
latest snapshot + anchor ledger) · **E** CT-1 reconstructs.

**Loss bound:** graceful (trigger fired) ≈ 0; hard reset (no warning) ≤ "since last anchor."

**Harness reality (verified — Claude Code / Agent SDK).** Buildable today, with custom plumbing:
- *Per-turn count* — `usage` on every API response, or `count_tokens`, or the `/context` breakdown.
- *Earlier trigger* — `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` (set ~0.75) moves auto-compact ahead of coherence loss.
- *Snapshot on the way out* — the **`PreCompact`** hook fires before compaction → write the snapshot.
- *Rehydrate on the way in* — the **`SessionStart`** hook (source = `compact`) → reload the snapshot.
- *Durable sessions* — Agent SDK persists session state and resumes by ID; custom backends (SQLite/Redis/…) supported.
- *Real gap* — no programmatic session-ID from inside a running Claude Code session, so cross-agent orchestration must be coordinated **externally** — which is exactly what the substrate already is. The gap does not bite this design.

---

In dynamics terms: **the compiler conserves S_k across refresh events.** Agent-local memory
is cache; canonical S_k is solid state in the substrate; refresh = re-hydrate from canonical.
This formalizes doctrine #95 (multi-executor COP resilience).

---

## 9. Parked (do not build yet)

> **FRCP / MDMP as the same dynamics template — anchor candidate, T-STRUCTURAL.**
> The stock/flow/derivative *grammar* transfers; the claim of identical *geometry* is
> unproven (FRCP is adversarial/two-party; MDMP is cooperative/convergent — different
> actor topology and loop structure). Hold at T-STRUCTURAL. This spec is the honest
> template to test them against later — it is **not** a commitment to the two-product
> platform bet. That is a CT-1 strategy decision, out of scope here (R-13).
