// Card 72 — Operator Resilience Engine (Phase-5, Tier-4).
//
// Fourth operator-meta card. Combines Card 69 (state), Card 70
// (diff), and Card 71 (stability) into a 14-section resilience
// assessment. Mirrors the structural pattern of Card 64 (Governance
// Resilience) but applied to the operator.
//
// Emits 14 sub-blocks:
//
//   [Resilience Level]             LOW … HIGH
//   [Operator Recovery]            weak / partial / strong
//   [Operator Rebound]             weak / moderate / strong
//   [Drift-Recovery]               weak / partial / strong
//   [Clarity-Recovery]             weak / partial / strong
//   [Load-Recovery]                weak / moderate / strong
//   [Pressure-Recovery]            weak / moderate / strong
//   [Resilience Trajectory]        prev → resilience → projected (state)
//   [Resilience Drivers]
//   [Resilience Inhibitors]
//   [Resilience Risks]
//   [Resilience Reinforcement]
//   [Resilience Decay]
//   [Operator Resilience Summary]
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
type Volatility    = "low" | "moderate" | "high";
type Direction     = "improving" | "stable" | "deteriorating";

// ----- Section parser (same pattern as Cards 62-71) -------------------

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

function parseStabilityLevel(stabilityText: string): Level {
  const body = parseSection(stabilityText, "Stability Level");
  const m = body.match(/^(LOW-MEDIUM|MEDIUM-HIGH|LOW|MEDIUM|HIGH)/);
  return (m ? m[1] : "HIGH") as Level;
}

function parseVolatility(stabilityText: string): Volatility {
  const body = parseSection(stabilityText, "Operator Volatility");
  if (body === "high")     return "high";
  if (body === "moderate") return "moderate";
  return "low";
}

function parseListSection(text: string, header: string): string[] {
  const body = parseSection(text, header);
  const out: string[] = [];
  for (const l of body.split("\n")) {
    if (l.startsWith("- ")) out.push(l.slice(2).trim());
  }
  return out;
}

// Direction inferred from Card 70's summary — same pattern as Card 71.
function parseDirection(diffText: string): Direction {
  const summary = parseSection(diffText, "Operator Diff Summary");
  if (summary.includes("improving"))     return "improving";
  if (summary.includes("deteriorating")) return "deteriorating";
  return "stable";
}

// ----- Derived fields --------------------------------------------------

type Recovery       = "weak" | "partial" | "strong";
type Rebound        = "weak" | "moderate" | "strong";
type DimRecovery3   = "weak" | "partial" | "strong";
type DimRecoveryM   = "weak" | "moderate" | "strong";

// Resilience level = stability level with a high-volatility penalty.
// The downstream layer can't outrun the stability bottleneck, and
// high volatility further erodes the rebound capacity.
function resilienceLevelOf(stability: Level, volatility: Volatility): Level {
  let rank = LEVEL_RANK[stability];
  if (volatility === "high") rank -= 1;
  rank = Math.max(0, Math.min(4, rank));
  return RANK_TO_LEVEL[rank];
}

// Recovery: how quickly the operator returns to baseline. Improving
// trajectories with strong stability recover fast; deteriorating
// trajectories don't recover at all.
function recoveryOf(direction: Direction, stability: Level): Recovery {
  if (direction === "deteriorating") return "weak";
  if (LEVEL_RANK[stability] >= 3)    return "strong";
  return "partial";
}

// Rebound: count of dimensions sitting at their optimal floor.
function reboundOf(
  load:     LoadLevel,
  drift:    DriftLevel,
  clarity:  ClarityLevel,
  pressure: PressureLevel,
): Rebound {
  let optimal = 0;
  if (load     === "low")    optimal++;
  if (drift    === "low")    optimal++;
  if (clarity  === "strong") optimal++;
  if (pressure === "low")    optimal++;
  if (optimal === 4) return "strong";
  if (optimal === 0) return "weak";
  return "moderate";
}

function driftRecoveryOf(drift: DriftLevel): DimRecovery3 {
  if (drift === "low")      return "strong";
  if (drift === "moderate") return "partial";
  return "weak";
}

function clarityRecoveryOf(clarity: ClarityLevel): DimRecovery3 {
  if (clarity === "strong")  return "strong";
  if (clarity === "partial") return "partial";
  return "weak";
}

function loadRecoveryOf(load: LoadLevel): DimRecoveryM {
  if (load === "low")      return "strong";
  if (load === "moderate") return "moderate";
  return "weak";
}

function pressureRecoveryOf(pressure: PressureLevel): DimRecoveryM {
  if (pressure === "low")      return "strong";
  if (pressure === "moderate") return "moderate";
  // elevated and high both signal weak pressure-recovery.
  return "weak";
}

// Trajectory — same shape as Card 71.
function buildTrajectory(resilience: Level, direction: Direction): string {
  const resRank  = LEVEL_RANK[resilience];
  const slope    = direction === "improving" ? 1 : direction === "deteriorating" ? -1 : 0;
  const prevRank = Math.max(0, Math.min(4, resRank - slope));
  const projRank = Math.max(0, Math.min(4, resRank + slope));
  const prev = RANK_TO_LEVEL[prevRank];
  const proj = RANK_TO_LEVEL[projRank];
  const moves = prev !== resilience || resilience !== proj;
  const tail = moves ? "(projected)" : "(stable)";
  return `${prev.toLowerCase()} → ${resilience.toLowerCase()} → ${proj.toLowerCase()} ${tail}`;
}

// ----- Drivers / Inhibitors / Risks / Reinforcement / Decay -----------

function collectRisks(
  load:     LoadLevel,
  drift:    DriftLevel,
  clarity:  ClarityLevel,
  pressure: PressureLevel,
): string[] {
  const out: string[] = [];
  if (load !== "low" || pressure === "elevated" || pressure === "high") {
    out.push("operator overload");
  }
  if (drift !== "low" || pressure === "elevated" || pressure === "high") {
    out.push("drift reactivation");
  }
  if (clarity !== "strong") {
    out.push("clarity degradation");
  }
  return out;
}

function collectReinforcement(
  load:     LoadLevel,
  drift:    DriftLevel,
  clarity:  ClarityLevel,
  pressure: PressureLevel,
): string[] {
  const out: string[] = [];
  if (clarity   !== "weak") out.push("maintain clarity focus");
  if (drift     !== "high") out.push("maintain drift suppression");
  if (load      !== "high") out.push("maintain load balance");
  if (pressure  !== "high") out.push("maintain pressure control");
  return out;
}

function collectDecay(
  drift:    DriftLevel,
  clarity:  ClarityLevel,
  pressure: PressureLevel,
): string[] {
  const out: string[] = [];
  if (drift    !== "high") out.push("drift may increase");
  if (pressure !== "high") out.push("pressure may spike");
  if (clarity  !== "weak") out.push("clarity may weaken");
  return out;
}

// ----- Summary ---------------------------------------------------------

function buildSummary(
  direction:       Direction,
  pressure:        PressureLevel,
  driftRecovery:   DimRecovery3,
  clarityRecovery: DimRecovery3,
  rebound:         Rebound,
): string {
  let s1: string;
  if (direction === "improving") {
    if (pressure === "elevated" || pressure === "high") {
      s1 = "Operator resilience is improving but remains vulnerable to elevated pressure.";
    } else {
      s1 = "Operator resilience is improving.";
    }
  } else if (direction === "deteriorating") {
    if (pressure === "high") {
      s1 = "Operator resilience is deteriorating under high pressure.";
    } else if (pressure === "elevated") {
      s1 = "Operator resilience is deteriorating under elevated pressure.";
    } else {
      s1 = "Operator resilience is deteriorating.";
    }
  } else {
    s1 = "Operator resilience is steady.";
  }

  const s2 = `Drift-recovery is ${driftRecovery}, clarity-recovery is ${clarityRecovery}, and rebound is ${rebound}.`;
  return `${s1} ${s2}`;
}

// ----- Entry point -----------------------------------------------------

export function buildOperatorResilience(
  operatorState:     string,
  operatorDiff:      string,
  operatorStability: string,
): string {
  // Parse state dims.
  const load     = parseLoad(operatorState);
  const drift    = parseDrift(operatorState);
  const clarity  = parseClarity(operatorState);
  const pressure = parsePressure(operatorState);

  // Drivers + inhibitors carry over from Card 69's output.
  const drivers    = parseListSection(operatorState, "Operator Drivers");
  const inhibitors = parseListSection(operatorState, "Operator Inhibitors");

  // Parse Card 71 stability + volatility.
  const stability  = parseStabilityLevel(operatorStability);
  const volatility = parseVolatility(operatorStability);

  // Parse Card 70 direction.
  const direction = parseDirection(operatorDiff);

  // Derived fields.
  const resilienceLevel = resilienceLevelOf(stability, volatility);
  const recovery        = recoveryOf(direction, stability);
  const rebound         = reboundOf(load, drift, clarity, pressure);
  const driftRecovery   = driftRecoveryOf(drift);
  const clarityRecovery = clarityRecoveryOf(clarity);
  const loadRecovery    = loadRecoveryOf(load);
  const pressureRec     = pressureRecoveryOf(pressure);
  const trajectory      = buildTrajectory(resilienceLevel, direction);
  const risks           = collectRisks(load, drift, clarity, pressure);
  const reinforcement   = collectReinforcement(load, drift, clarity, pressure);
  const decay           = collectDecay(drift, clarity, pressure);
  const summary         = buildSummary(direction, pressure, driftRecovery, clarityRecovery, rebound);

  const blocks: string[] = [];
  blocks.push("=== Operator Resilience ===");
  blocks.push(`[Resilience Level]\n${resilienceLevel}`);
  blocks.push(`[Operator Recovery]\n${recovery}`);
  blocks.push(`[Operator Rebound]\n${rebound}`);
  blocks.push(`[Drift-Recovery]\n${driftRecovery}`);
  blocks.push(`[Clarity-Recovery]\n${clarityRecovery}`);
  blocks.push(`[Load-Recovery]\n${loadRecovery}`);
  blocks.push(`[Pressure-Recovery]\n${pressureRec}`);
  blocks.push(`[Resilience Trajectory]\n${trajectory}`);
  blocks.push(
    drivers.length === 0
      ? `[Resilience Drivers]\n(none)`
      : `[Resilience Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Resilience Inhibitors]\n(none)`
      : `[Resilience Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(
    risks.length === 0
      ? `[Resilience Risks]\n(none)`
      : `[Resilience Risks]\n${risks.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    reinforcement.length === 0
      ? `[Resilience Reinforcement]\n(none)`
      : `[Resilience Reinforcement]\n${reinforcement.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    decay.length === 0
      ? `[Resilience Decay]\n(none)`
      : `[Resilience Decay]\n${decay.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(`[Operator Resilience Summary]\n${summary}`);

  return blocks.join("\n\n");
}
