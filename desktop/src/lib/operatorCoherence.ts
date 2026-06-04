// Card 74 — Operator Coherence Engine (Phase-5, Tier-6).
//
// Sixth operator-meta card. Combines Card 69 (state), Card 70
// (diff), Card 71 (stability), Card 72 (resilience), and Card 73
// (immunity) into a 14-section coherence assessment — the operator's
// internal alignment, consistency, and integrative clarity. Mirrors
// the structural pattern of Card 66 (Governance Coherence) but
// applied to the operator.
//
// Emits 14 sub-blocks:
//
//   [Coherence Level]              LOW … HIGH
//   [Operator Alignment]           "<word> alignment"   (weak/partial/strong)
//   [Operator Integration]         "<word> integration" (weak/moderate/strong)
//   [Clarity-Alignment]            weak / partial / strong
//   [Drift-Alignment]              weak / moderate / strong
//   [Load-Alignment]               weak / partial / strong
//   [Pressure-Alignment]           weak / moderate / strong
//   [Coherence Trajectory]         curr → next → projected (state)
//   [Coherence Drivers]
//   [Coherence Inhibitors]
//   [Coherence Risks]
//   [Coherence Reinforcement]
//   [Coherence Decay]
//   [Operator Coherence Summary]
//
// Pure deterministic string IO — no backend, no styling, no new
// dependencies.

type Level = "LOW" | "LOW-MEDIUM" | "MEDIUM" | "MEDIUM-HIGH" | "HIGH";

const LEVEL_RANK: Record<Level, number> = {
  LOW: 0, "LOW-MEDIUM": 1, MEDIUM: 2, "MEDIUM-HIGH": 3, HIGH: 4,
};
const RANK_TO_LEVEL: Record<number, Level> = {
  0: "LOW", 1: "LOW-MEDIUM", 2: "MEDIUM", 3: "MEDIUM-HIGH", 4: "HIGH",
};

type LoadLevel     = "low" | "moderate" | "high";
type DriftLevel    = "low" | "moderate" | "high";
type ClarityLevel  = "weak" | "partial" | "strong";
type PressureLevel = "low" | "moderate" | "elevated" | "high";
type Direction     = "improving" | "stable" | "deteriorating";

// ----- Section parser (same pattern as Cards 62-73) -------------------

function parseSection(text: string, header: string): string {
  const re = new RegExp(`\\[${header}\\]\\s*\\n([\\s\\S]*?)(?=\\n\\[|$)`);
  const m  = text.match(re);
  return m ? m[1].trim() : "";
}

function parseLoad(text: string): LoadLevel {
  const body = parseSection(text, "Operator Load");
  if (body === "moderate") return "moderate";
  if (body === "high")     return "high";
  return "low";
}

function parseDrift(text: string): DriftLevel {
  const body = parseSection(text, "Operator Drift");
  if (body === "moderate") return "moderate";
  if (body === "high")     return "high";
  return "low";
}

function parseClarity(text: string): ClarityLevel {
  const body = parseSection(text, "Operator Clarity");
  if (body === "weak")    return "weak";
  if (body === "partial") return "partial";
  return "strong";
}

function parsePressure(text: string): PressureLevel {
  const body = parseSection(text, "Operator Pressure");
  if (body === "high")     return "high";
  if (body === "elevated") return "elevated";
  if (body === "moderate") return "moderate";
  return "low";
}

function parseLayerLevel(text: string, header: string): Level {
  const body = parseSection(text, header);
  const m = body.match(/^(LOW-MEDIUM|MEDIUM-HIGH|LOW|MEDIUM|HIGH)/);
  return (m ? m[1] : "HIGH") as Level;
}

// Direction inferred from Card 70's summary — same pattern as Cards 71-73.
function parseDirection(diffText: string): Direction {
  const summary = parseSection(diffText, "Operator Diff Summary");
  if (summary.includes("improving"))     return "improving";
  if (summary.includes("deteriorating")) return "deteriorating";
  return "stable";
}

// ----- Per-dim alignment ----------------------------------------------

type ClarityAlignment  = "weak" | "partial" | "strong";
type LoadAlignment     = "weak" | "partial" | "strong";
type DriftAlignment    = "weak" | "moderate" | "strong";
type PressureAlignment = "weak" | "moderate" | "strong";

function clarityAlignmentOf(c: ClarityLevel): ClarityAlignment {
  if (c === "strong")  return "strong";
  if (c === "partial") return "partial";
  return "weak";
}

function driftAlignmentOf(d: DriftLevel): DriftAlignment {
  if (d === "low")      return "strong";
  if (d === "moderate") return "moderate";
  return "weak";
}

function loadAlignmentOf(l: LoadLevel): LoadAlignment {
  if (l === "low")      return "strong";
  if (l === "moderate") return "partial";
  return "weak";
}

function pressureAlignmentOf(p: PressureLevel): PressureAlignment {
  if (p === "low")      return "strong";
  if (p === "moderate") return "moderate";
  return "weak"; // elevated / high
}

// ----- Overall alignment + integration --------------------------------

type Alignment   = "weak" | "partial" | "strong";
type Integration = "weak" | "moderate" | "strong";

function overallAlignmentOf(
  clarity:  ClarityAlignment,
  drift:    DriftAlignment,
  load:     LoadAlignment,
  pressure: PressureAlignment,
): Alignment {
  const strongs = [clarity, drift, load, pressure].filter((a) => a === "strong").length;
  if (strongs === 4) return "strong";
  if (strongs === 0) return "weak";
  return "partial";
}

function integrationOf(
  stability:  Level,
  resilience: Level,
  immunity:   Level,
): Integration {
  const ranks       = [LEVEL_RANK[stability], LEVEL_RANK[resilience], LEVEL_RANK[immunity]];
  const strongCount = ranks.filter((r) => r >= 3).length;
  const weakCount   = ranks.filter((r) => r === 0).length;
  if (strongCount === 3) return "strong";
  if (weakCount   === 3) return "weak";
  return "moderate";
}

// ----- Coherence level + trajectory -----------------------------------

// Coherence floors on the rounded-down average of the three upstream
// layer ranks (stability / resilience / immunity).
function coherenceLevelOf(
  stability:  Level,
  resilience: Level,
  immunity:   Level,
): Level {
  const sum = LEVEL_RANK[stability] + LEVEL_RANK[resilience] + LEVEL_RANK[immunity];
  const avg = Math.floor(sum / 3);
  return RANK_TO_LEVEL[Math.max(0, Math.min(4, avg))];
}

// Trajectory walks curr → next → projected — all forward. Unlike the
// stability/resilience/immunity trajectories (which centered on the
// current level), coherence shows the projected forward arc.
function buildTrajectory(coherence: Level, direction: Direction): string {
  const cohRank  = LEVEL_RANK[coherence];
  const slope    = direction === "improving" ? 1 : direction === "deteriorating" ? -1 : 0;
  const nextRank = Math.max(0, Math.min(4, cohRank + slope));
  const projRank = Math.max(0, Math.min(4, cohRank + 2 * slope));
  const next = RANK_TO_LEVEL[nextRank];
  const proj = RANK_TO_LEVEL[projRank];
  const moves = coherence !== next || next !== proj;
  const tail = moves ? "(projected)" : "(stable)";
  return `${coherence.toLowerCase()} → ${next.toLowerCase()} → ${proj.toLowerCase()} ${tail}`;
}

// ----- Drivers / Inhibitors / Risks / Reinforcement / Decay -----------

function collectDrivers(
  direction:   Direction,
  clarity:     ClarityLevel,
  drift:       DriftLevel,
  integration: Integration,
): string[] {
  if (direction !== "improving") return [];
  const out: string[] = [];
  if (clarity !== "weak")    out.push("improving clarity alignment");
  if (drift   !== "high")    out.push("stable drift alignment");
  if (integration !== "weak") out.push("strengthening integration");
  return out;
}

function collectInhibitors(
  pressure:      PressureLevel,
  loadAlignment: LoadAlignment,
  alignment:     Alignment,
): string[] {
  const out: string[] = [];
  if (pressure === "moderate" || pressure === "elevated" || pressure === "high") {
    out.push("elevated pressure");
  }
  if      (loadAlignment === "partial") out.push("partial load alignment");
  else if (loadAlignment === "weak")    out.push("weak load alignment");
  if (alignment !== "strong") out.push("residual fragmentation");
  return out;
}

function collectRisks(
  pressure:  PressureLevel,
  clarity:   ClarityLevel,
  alignment: Alignment,
  load:      LoadLevel,
): string[] {
  const out: string[] = [];
  if (pressure !== "low") out.push("misalignment under pressure");
  if (clarity !== "strong" || alignment !== "strong") {
    out.push("clarity fragmentation");
  }
  if (load !== "low") out.push("load imbalance");
  return out;
}

function collectReinforcement(
  clarity:     ClarityLevel,
  drift:       DriftLevel,
  integration: Integration,
  load:        LoadLevel,
): string[] {
  const out: string[] = [];
  if (clarity     !== "weak") out.push("maintain clarity focus");
  if (drift       !== "high") out.push("maintain drift control");
  if (integration !== "weak") out.push("maintain integration discipline");
  if (load        !== "high") out.push("maintain load balance");
  return out;
}

function collectDecay(
  pressure:  PressureLevel,
  drift:     DriftLevel,
  clarity:   ClarityLevel,
  alignment: Alignment,
): string[] {
  const out: string[] = [];
  if (pressure !== "low") out.push("pressure may disrupt alignment");
  if (drift    !== "low") out.push("drift may re-emerge");
  if (clarity !== "strong" || alignment !== "strong") {
    out.push("clarity may weaken");
  }
  return out;
}

// ----- Summary ---------------------------------------------------------

function buildSummary(
  direction:         Direction,
  clarityAlignment:  ClarityAlignment,
  integration:       Integration,
  pressureAlignment: PressureAlignment,
): string {
  let s1: string;
  if (direction === "improving") {
    s1 = `Operator coherence is improving, with ${clarityAlignment} clarity-alignment and ${integration} integration.`;
  } else if (direction === "deteriorating") {
    s1 = `Operator coherence is deteriorating, with ${clarityAlignment} clarity-alignment and ${integration} integration.`;
  } else {
    s1 = `Operator coherence is steady, with ${clarityAlignment} clarity-alignment and ${integration} integration.`;
  }

  if (pressureAlignment === "weak") {
    return `${s1} Pressure-alignment remains weak and may disrupt overall coherence.`;
  }
  return s1;
}

// ----- Entry point -----------------------------------------------------

export function buildOperatorCoherence(
  operatorState:      string,
  operatorDiff:       string,
  operatorStability:  string,
  operatorResilience: string,
  operatorImmunity:   string,
): string {
  // Parse state dims.
  const load     = parseLoad(operatorState);
  const drift    = parseDrift(operatorState);
  const clarity  = parseClarity(operatorState);
  const pressure = parsePressure(operatorState);

  // Parse upstream layer levels.
  const stability  = parseLayerLevel(operatorStability,  "Stability Level");
  const resilience = parseLayerLevel(operatorResilience, "Resilience Level");
  const immunity   = parseLayerLevel(operatorImmunity,   "Immunity Level");

  // Parse Card 70 direction.
  const direction = parseDirection(operatorDiff);

  // Derive per-dim alignments.
  const clarityAlign  = clarityAlignmentOf(clarity);
  const driftAlign    = driftAlignmentOf(drift);
  const loadAlign     = loadAlignmentOf(load);
  const pressureAlign = pressureAlignmentOf(pressure);

  // Derive overall fields.
  const alignment      = overallAlignmentOf(clarityAlign, driftAlign, loadAlign, pressureAlign);
  const integration    = integrationOf(stability, resilience, immunity);
  const coherence      = coherenceLevelOf(stability, resilience, immunity);
  const trajectory     = buildTrajectory(coherence, direction);
  const drivers        = collectDrivers(direction, clarity, drift, integration);
  const inhibitors     = collectInhibitors(pressure, loadAlign, alignment);
  const risks          = collectRisks(pressure, clarity, alignment, load);
  const reinforcement  = collectReinforcement(clarity, drift, integration, load);
  const decay          = collectDecay(pressure, drift, clarity, alignment);
  const summary        = buildSummary(direction, clarityAlign, integration, pressureAlign);

  const blocks: string[] = [];
  blocks.push("=== Operator Coherence ===");
  blocks.push(`[Coherence Level]\n${coherence}`);
  blocks.push(`[Operator Alignment]\n${alignment} alignment`);
  blocks.push(`[Operator Integration]\n${integration} integration`);
  blocks.push(`[Clarity-Alignment]\n${clarityAlign}`);
  blocks.push(`[Drift-Alignment]\n${driftAlign}`);
  blocks.push(`[Load-Alignment]\n${loadAlign}`);
  blocks.push(`[Pressure-Alignment]\n${pressureAlign}`);
  blocks.push(`[Coherence Trajectory]\n${trajectory}`);
  blocks.push(
    drivers.length === 0
      ? `[Coherence Drivers]\n(none)`
      : `[Coherence Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Coherence Inhibitors]\n(none)`
      : `[Coherence Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(
    risks.length === 0
      ? `[Coherence Risks]\n(none)`
      : `[Coherence Risks]\n${risks.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    reinforcement.length === 0
      ? `[Coherence Reinforcement]\n(none)`
      : `[Coherence Reinforcement]\n${reinforcement.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    decay.length === 0
      ? `[Coherence Decay]\n(none)`
      : `[Coherence Decay]\n${decay.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(`[Operator Coherence Summary]\n${summary}`);

  return blocks.join("\n\n");
}
