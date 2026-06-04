// Card 73 — Operator Immunity Engine (Phase-5, Tier-5).
//
// Fifth operator-meta card. Combines Card 69 (state), Card 70
// (diff), Card 71 (stability), and Card 72 (resilience) into a
// 14-section immunity assessment — the operator's long-term
// protective capacity. Mirrors the structural pattern of Card 65
// (Governance Immunity) but applied to the operator.
//
// Emits 14 sub-blocks:
//
//   [Immunity Level]               LOW … HIGH
//   [Operator Resistance]          weak / partial / strong
//   [Operator Shielding]           weak / moderate / strong
//   [Drift-Immunity]               weak / partial / strong
//   [Clarity-Immunity]             weak / partial / strong
//   [Load-Immunity]                weak / moderate / strong
//   [Pressure-Immunity]            weak / moderate / strong
//   [Immunity Trajectory]          prev → immunity → projected (state)
//   [Immunity Drivers]
//   [Immunity Inhibitors]
//   [Immunity Risks]
//   [Immunity Reinforcement]
//   [Immunity Decay]
//   [Operator Immunity Summary]
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

// ----- Section parser (same pattern as Cards 62-72) -------------------

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

function parseResilienceLevel(resilienceText: string): Level {
  const body = parseSection(resilienceText, "Resilience Level");
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

// Direction inferred from Card 70's summary — same pattern as Cards 71/72.
function parseDirection(diffText: string): Direction {
  const summary = parseSection(diffText, "Operator Diff Summary");
  if (summary.includes("improving"))     return "improving";
  if (summary.includes("deteriorating")) return "deteriorating";
  return "stable";
}

// ----- Derived fields --------------------------------------------------

type Resistance     = "weak" | "partial" | "strong";
type Shielding      = "weak" | "moderate" | "strong";
type DimImmunity3   = "weak" | "partial" | "strong";
type DimImmunityM   = "weak" | "moderate" | "strong";

// Immunity floors on Card 72's resilience level with a high-volatility
// penalty. The protective layer can't outrun the recovery layer, and
// active volatility further erodes long-term resistance.
function immunityLevelOf(resilience: Level, volatility: Volatility): Level {
  let rank = LEVEL_RANK[resilience];
  if (volatility === "high") rank -= 1;
  rank = Math.max(0, Math.min(4, rank));
  return RANK_TO_LEVEL[rank];
}

// Resistance: general resistance to destabilization. Improving
// trajectories with strong upstream resilience resist destabilization
// fully; deteriorating trajectories have no resistance.
function resistanceOf(direction: Direction, resilience: Level): Resistance {
  if (direction === "deteriorating")  return "weak";
  if (LEVEL_RANK[resilience] >= 3)    return "strong";
  return "partial";
}

// Shielding: count of dimensions sitting at their optimal floor.
function shieldingOf(
  load:     LoadLevel,
  drift:    DriftLevel,
  clarity:  ClarityLevel,
  pressure: PressureLevel,
): Shielding {
  let optimal = 0;
  if (load     === "low")    optimal++;
  if (drift    === "low")    optimal++;
  if (clarity  === "strong") optimal++;
  if (pressure === "low")    optimal++;
  if (optimal === 4) return "strong";
  if (optimal === 0) return "weak";
  return "moderate";
}

function driftImmunityOf(drift: DriftLevel): DimImmunity3 {
  if (drift === "low")      return "strong";
  if (drift === "moderate") return "partial";
  return "weak";
}

function clarityImmunityOf(clarity: ClarityLevel): DimImmunity3 {
  if (clarity === "strong")  return "strong";
  if (clarity === "partial") return "partial";
  return "weak";
}

function loadImmunityOf(load: LoadLevel): DimImmunityM {
  if (load === "low")      return "strong";
  if (load === "moderate") return "moderate";
  return "weak";
}

function pressureImmunityOf(pressure: PressureLevel): DimImmunityM {
  if (pressure === "low")      return "strong";
  if (pressure === "moderate") return "moderate";
  // elevated and high both signal weak pressure-immunity.
  return "weak";
}

// Trajectory — same shape as Cards 71/72.
function buildTrajectory(immunity: Level, direction: Direction): string {
  const immRank  = LEVEL_RANK[immunity];
  const slope    = direction === "improving" ? 1 : direction === "deteriorating" ? -1 : 0;
  const prevRank = Math.max(0, Math.min(4, immRank - slope));
  const projRank = Math.max(0, Math.min(4, immRank + slope));
  const prev = RANK_TO_LEVEL[prevRank];
  const proj = RANK_TO_LEVEL[projRank];
  const moves = prev !== immunity || immunity !== proj;
  const tail = moves ? "(projected)" : "(stable)";
  return `${prev.toLowerCase()} → ${immunity.toLowerCase()} → ${proj.toLowerCase()} ${tail}`;
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
  if (clarity  !== "weak") out.push("maintain clarity focus");
  if (drift    !== "high") out.push("maintain drift suppression");
  if (load     !== "high") out.push("maintain load balance");
  if (pressure !== "high") out.push("maintain pressure control");
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
  driftImmunity:   DimImmunity3,
  clarityImmunity: DimImmunity3,
  shielding:       Shielding,
): string {
  let s1: string;
  if (direction === "improving") {
    if (pressure === "elevated" || pressure === "high") {
      s1 = "Operator immunity is improving but remains vulnerable to elevated pressure.";
    } else {
      s1 = "Operator immunity is improving.";
    }
  } else if (direction === "deteriorating") {
    if (pressure === "high") {
      s1 = "Operator immunity is deteriorating under high pressure.";
    } else if (pressure === "elevated") {
      s1 = "Operator immunity is deteriorating under elevated pressure.";
    } else {
      s1 = "Operator immunity is deteriorating.";
    }
  } else {
    s1 = "Operator immunity is steady.";
  }

  const s2 = `Drift-immunity is ${driftImmunity}, clarity-immunity is ${clarityImmunity}, and shielding is ${shielding}.`;
  return `${s1} ${s2}`;
}

// ----- Entry point -----------------------------------------------------

export function buildOperatorImmunity(
  operatorState:      string,
  operatorDiff:       string,
  operatorStability:  string,
  operatorResilience: string,
): string {
  // Parse state dims.
  const load     = parseLoad(operatorState);
  const drift    = parseDrift(operatorState);
  const clarity  = parseClarity(operatorState);
  const pressure = parsePressure(operatorState);

  // Drivers + inhibitors carry over from Card 69's output.
  const drivers    = parseListSection(operatorState, "Operator Drivers");
  const inhibitors = parseListSection(operatorState, "Operator Inhibitors");

  // Parse Card 71 volatility + Card 72 resilience as upstream signals.
  const volatility = parseVolatility(operatorStability);
  const resilience = parseResilienceLevel(operatorResilience);

  // Parse Card 70 direction.
  const direction = parseDirection(operatorDiff);

  // Derived fields.
  const immunityLevel  = immunityLevelOf(resilience, volatility);
  const resistance     = resistanceOf(direction, resilience);
  const shielding      = shieldingOf(load, drift, clarity, pressure);
  const driftImmunity  = driftImmunityOf(drift);
  const clarityImm     = clarityImmunityOf(clarity);
  const loadImmunity   = loadImmunityOf(load);
  const pressureImm    = pressureImmunityOf(pressure);
  const trajectory     = buildTrajectory(immunityLevel, direction);
  const risks          = collectRisks(load, drift, clarity, pressure);
  const reinforcement  = collectReinforcement(load, drift, clarity, pressure);
  const decay          = collectDecay(drift, clarity, pressure);
  const summary        = buildSummary(direction, pressure, driftImmunity, clarityImm, shielding);

  const blocks: string[] = [];
  blocks.push("=== Operator Immunity ===");
  blocks.push(`[Immunity Level]\n${immunityLevel}`);
  blocks.push(`[Operator Resistance]\n${resistance}`);
  blocks.push(`[Operator Shielding]\n${shielding}`);
  blocks.push(`[Drift-Immunity]\n${driftImmunity}`);
  blocks.push(`[Clarity-Immunity]\n${clarityImm}`);
  blocks.push(`[Load-Immunity]\n${loadImmunity}`);
  blocks.push(`[Pressure-Immunity]\n${pressureImm}`);
  blocks.push(`[Immunity Trajectory]\n${trajectory}`);
  blocks.push(
    drivers.length === 0
      ? `[Immunity Drivers]\n(none)`
      : `[Immunity Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Immunity Inhibitors]\n(none)`
      : `[Immunity Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(
    risks.length === 0
      ? `[Immunity Risks]\n(none)`
      : `[Immunity Risks]\n${risks.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    reinforcement.length === 0
      ? `[Immunity Reinforcement]\n(none)`
      : `[Immunity Reinforcement]\n${reinforcement.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    decay.length === 0
      ? `[Immunity Decay]\n(none)`
      : `[Immunity Decay]\n${decay.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(`[Operator Immunity Summary]\n${summary}`);

  return blocks.join("\n\n");
}
