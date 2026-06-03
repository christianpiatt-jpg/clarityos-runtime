// Card 71 — Operator Stability Engine (Phase-5, Tier-3).
//
// Third operator-meta card. Combines Card 69 (operator state) and
// Card 70 (operator diff) into a 14-section stability assessment.
// Mirrors the structural pattern of Card 63 (Governance Stability)
// but applied to the operator.
//
// Emits 14 sub-blocks:
//
//   [Stability Level]              LOW … HIGH
//   [Operator Equilibrium]         weak / partial / strong
//   [Operator Volatility]          low / moderate / high
//   [Drift-Stability]              weak / partial / strong
//   [Clarity-Stability]            weak / partial / strong
//   [Load-Stability]               weak / moderate / strong
//   [Pressure-Stability]           weak / moderate / strong
//   [Stability Trajectory]         prev → stability → projected (state)
//   [Stability Drivers]
//   [Stability Inhibitors]
//   [Stability Risks]
//   [Stability Reinforcement]
//   [Stability Decay]
//   [Operator Stability Summary]
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

type LoadLevel      = "low" | "moderate" | "high";
type DriftLevel     = "low" | "moderate" | "high";
type ClarityLevel   = "weak" | "partial" | "strong";
type StabilityLevel = "weak" | "moderate" | "strong";
type PressureLevel  = "low" | "moderate" | "elevated" | "high";
type Direction      = "improving" | "stable" | "deteriorating";

// ----- Section parser (same pattern as Cards 62-68 and Card 70) -------

function parseSection(text: string, header: string): string {
  const re = new RegExp(`\\[${header}\\]\\s*\\n([\\s\\S]*?)(?=\\n\\[|$)`);
  const m  = text.match(re);
  return m ? m[1].trim() : "";
}

function parseOperatorLevel(text: string): Level {
  const body = parseSection(text, "Operator Level");
  const m = body.match(/^(LOW-MEDIUM|MEDIUM-HIGH|LOW|MEDIUM|HIGH)/);
  return (m ? m[1] : "HIGH") as Level;
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

function parseStabilityField(text: string): StabilityLevel {
  const body = parseSection(text, "Operator Stability");
  if (body === "weak")     return "weak";
  if (body === "moderate") return "moderate";
  return "strong";
}

function parsePressure(text: string): PressureLevel {
  const body = parseSection(text, "Operator Pressure");
  if (body === "high")     return "high";
  if (body === "elevated") return "elevated";
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

// Direction inferred from Card 70's summary text — the only place
// the trajectory verb actually shows up.
function parseDirection(diffText: string): Direction {
  const summary = parseSection(diffText, "Operator Diff Summary");
  if (summary.includes("improving"))     return "improving";
  if (summary.includes("deteriorating")) return "deteriorating";
  return "stable";
}

// ----- Derived fields --------------------------------------------------

type Equilibrium    = "weak" | "partial" | "strong";
type Volatility     = "low" | "moderate" | "high";
type DimStability3  = "weak" | "partial" | "strong";
type DimStabilityM  = "weak" | "moderate" | "strong";

function equilibriumOf(
  load:      LoadLevel,
  drift:     DriftLevel,
  clarity:   ClarityLevel,
  stability: StabilityLevel,
  pressure:  PressureLevel,
): Equilibrium {
  let critical = 0;
  let optimal  = 0;
  if (drift     === "low")    optimal++;
  else if (drift === "high")  critical++;
  if (load      === "low")    optimal++;
  else if (load  === "high")  critical++;
  if (clarity   === "strong") optimal++;
  else if (clarity === "weak") critical++;
  if (stability === "strong") optimal++;
  else if (stability === "weak") critical++;
  if (pressure  === "low")    optimal++;
  else if (pressure === "high") critical++;
  if (critical >= 3) return "weak";
  if (optimal  >= 4) return "strong";
  return "partial";
}

function volatilityOf(
  pressure:       PressureLevel,
  drift:          DriftLevel,
  clarity:        ClarityLevel,
  inhibitorCount: number,
): Volatility {
  let signals = 0;
  if (pressure === "elevated" || pressure === "high") signals++;
  if (drift    === "moderate" || drift === "high")     signals++;
  if (inhibitorCount >= 3)                              signals++;
  if (clarity === "weak")                               signals++;
  if (signals >= 3) return "high";
  if (signals >= 1) return "moderate";
  return "low";
}

// Stability level uses the parsed operator level as base, decremented
// when volatility is high so a chaotic state can't sit at the same
// stability as a calm one.
function stabilityLevelOf(operatorLevel: Level, volatility: Volatility): Level {
  let rank = LEVEL_RANK[operatorLevel];
  if (volatility === "high") rank -= 1;
  rank = Math.max(0, Math.min(4, rank));
  return RANK_TO_LEVEL[rank];
}

function driftStabilityOf(drift: DriftLevel): DimStability3 {
  if (drift === "low")      return "strong";
  if (drift === "moderate") return "partial";
  return "weak";
}

function clarityStabilityOf(clarity: ClarityLevel): DimStability3 {
  if (clarity === "strong")  return "strong";
  if (clarity === "partial") return "partial";
  return "weak";
}

function loadStabilityOf(load: LoadLevel): DimStabilityM {
  if (load === "low")      return "strong";
  if (load === "moderate") return "moderate";
  return "weak";
}

function pressureStabilityOf(pressure: PressureLevel): DimStabilityM {
  if (pressure === "low")      return "strong";
  if (pressure === "moderate") return "moderate";
  // elevated and high both signal weak pressure stability.
  return "weak";
}

// Trajectory: walks stability back one bucket, current stability, and
// forward one bucket — mirror of Card 61's "(projected)"/"(stable)"
// tail.
function buildTrajectory(stability: Level, direction: Direction): string {
  const stabRank = LEVEL_RANK[stability];
  const slope    = direction === "improving" ? 1 : direction === "deteriorating" ? -1 : 0;
  const prevRank = Math.max(0, Math.min(4, stabRank - slope));
  const projRank = Math.max(0, Math.min(4, stabRank + slope));
  const prev = RANK_TO_LEVEL[prevRank];
  const proj = RANK_TO_LEVEL[projRank];
  const moves = prev !== stability || stability !== proj;
  const tail = moves ? "(projected)" : "(stable)";
  return `${prev.toLowerCase()} → ${stability.toLowerCase()} → ${proj.toLowerCase()} ${tail}`;
}

// ----- Drivers / Inhibitors / Risks / Reinforcement / Decay -----------

function collectRisks(
  load:     LoadLevel,
  drift:    DriftLevel,
  clarity:  ClarityLevel,
  pressure: PressureLevel,
): string[] {
  const out: string[] = [];
  if (
    load !== "low" || pressure === "elevated" || pressure === "high"
  ) {
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
  direction:        Direction,
  pressure:         PressureLevel,
  driftStability:   DimStability3,
  clarityStability: DimStability3,
  volatility:       Volatility,
): string {
  let s1: string;
  if (direction === "improving") {
    if (pressure === "elevated" || pressure === "high") {
      s1 = "Operator stability is improving but remains vulnerable to elevated pressure.";
    } else {
      s1 = "Operator stability is improving.";
    }
  } else if (direction === "deteriorating") {
    if (pressure === "high") {
      s1 = "Operator stability is deteriorating under high pressure.";
    } else if (pressure === "elevated") {
      s1 = "Operator stability is deteriorating under elevated pressure.";
    } else {
      s1 = "Operator stability is deteriorating.";
    }
  } else {
    s1 = "Operator stability is steady.";
  }

  const s2 = `Drift-stability is ${driftStability}, clarity-stability is ${clarityStability}, and volatility is ${volatility}.`;
  return `${s1} ${s2}`;
}

// ----- Entry point -----------------------------------------------------

export function buildOperatorStability(
  operatorState: string,
  operatorDiff:  string,
): string {
  // Parse Card 69 (state) fields.
  const operatorLevel = parseOperatorLevel(operatorState);
  const load          = parseLoad(operatorState);
  const drift         = parseDrift(operatorState);
  const clarity       = parseClarity(operatorState);
  const stateStab     = parseStabilityField(operatorState);
  const pressure      = parsePressure(operatorState);
  const drivers       = parseListSection(operatorState, "Operator Drivers");
  const inhibitors    = parseListSection(operatorState, "Operator Inhibitors");

  // Parse Card 70 (diff) direction signal.
  const direction = parseDirection(operatorDiff);

  // Derived fields.
  const volatility       = volatilityOf(pressure, drift, clarity, inhibitors.length);
  const stabilityLevel   = stabilityLevelOf(operatorLevel, volatility);
  const equilibrium      = equilibriumOf(load, drift, clarity, stateStab, pressure);
  const driftStability   = driftStabilityOf(drift);
  const clarityStability = clarityStabilityOf(clarity);
  const loadStability    = loadStabilityOf(load);
  const pressureStab     = pressureStabilityOf(pressure);
  const trajectory       = buildTrajectory(stabilityLevel, direction);
  const risks            = collectRisks(load, drift, clarity, pressure);
  const reinforcement    = collectReinforcement(load, drift, clarity, pressure);
  const decay            = collectDecay(drift, clarity, pressure);
  const summary          = buildSummary(direction, pressure, driftStability, clarityStability, volatility);

  const blocks: string[] = [];
  blocks.push("=== Operator Stability ===");
  blocks.push(`[Stability Level]\n${stabilityLevel}`);
  blocks.push(`[Operator Equilibrium]\n${equilibrium}`);
  blocks.push(`[Operator Volatility]\n${volatility}`);
  blocks.push(`[Drift-Stability]\n${driftStability}`);
  blocks.push(`[Clarity-Stability]\n${clarityStability}`);
  blocks.push(`[Load-Stability]\n${loadStability}`);
  blocks.push(`[Pressure-Stability]\n${pressureStab}`);
  blocks.push(`[Stability Trajectory]\n${trajectory}`);
  blocks.push(
    drivers.length === 0
      ? `[Stability Drivers]\n(none)`
      : `[Stability Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Stability Inhibitors]\n(none)`
      : `[Stability Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(
    risks.length === 0
      ? `[Stability Risks]\n(none)`
      : `[Stability Risks]\n${risks.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    reinforcement.length === 0
      ? `[Stability Reinforcement]\n(none)`
      : `[Stability Reinforcement]\n${reinforcement.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    decay.length === 0
      ? `[Stability Decay]\n(none)`
      : `[Stability Decay]\n${decay.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(`[Operator Stability Summary]\n${summary}`);

  return blocks.join("\n\n");
}
