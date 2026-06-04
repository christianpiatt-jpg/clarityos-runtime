// Card 78 — Operator Meta-Stability (Phase-5 AO-2).
//
// Second of the Operator Advanced Operators (AO-1 through AO-14,
// Cards 77-90). Same weight class as Card 77: a lighter, higher-order
// interpretive layer over the operator meta-stack rather than a new
// structural engine.
//
// Card 78 evaluates operator *meta-stability* — how stable the
// operator is across transitions, loads, and pressures — by fusing
// the seven operator core outputs (Cards 69-75), the system-operator
// integration (Card 76), and the operator meta-pattern (Card 77) into
// a single 12-section read:
//
//   [Meta-Stability Level]            LOW … HIGH
//   [Transition-Stability]            "<word> stability"
//   [Load-Stability]                  "<word> stability"
//   [Pressure-Stability]              "<word> stability"
//   [Drift-Stability]                 "<word> stability"
//   [Meta-Stability Trajectory]       curr → next → projected (state)
//   [Meta-Stability Drivers]
//   [Meta-Stability Inhibitors]
//   [Meta-Stability Risks]
//   [Meta-Stability Reinforcement]
//   [Meta-Stability Decay]
//   [Operator Meta-Stability Summary]
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

// Meta-stability word scale (weak < partial < moderate < strong).
type StabilityWord = "weak" | "partial" | "moderate" | "strong";

// How the upstream meta-pattern is holding (derived from Card 77 level).
type MetaWord = "stable" | "shifting" | "unstable";

// ----- Section parser (same pattern as Cards 62-77) -------------------

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

// Volatility comes from Card 71's [Operator Volatility] block.
function parseVolatility(text: string): Volatility {
  const body = parseSection(text, "Operator Volatility");
  if (body === "high")     return "high";
  if (body === "moderate") return "moderate";
  return "low";
}

function parseLayerLevel(text: string, header: string): Level {
  const body = parseSection(text, header);
  const m = body.match(/^(LOW-MEDIUM|MEDIUM-HIGH|LOW|MEDIUM|HIGH)/);
  return (m ? m[1] : "HIGH") as Level;
}

// Direction inferred from Card 70's diff summary.
function parseDirection(diffText: string): Direction {
  const summary = parseSection(diffText, "Operator Diff Summary");
  if (summary.includes("improving"))     return "improving";
  if (summary.includes("deteriorating")) return "deteriorating";
  return "stable";
}

// ----- Per-dimension stability words ----------------------------------

// drift {low,moderate,high} → strong/partial/weak
function driftStabilityOf(drift: DriftLevel): StabilityWord {
  if (drift === "low")      return "strong";
  if (drift === "moderate") return "partial";
  return "weak";
}

// load {low,moderate,high} → strong/partial/weak
function loadStabilityOf(load: LoadLevel): StabilityWord {
  if (load === "low")      return "strong";
  if (load === "moderate") return "partial";
  return "weak";
}

// pressure {low,moderate,elevated,high} → strong/moderate/weak
// (elevated + high both collapse to weak — pressure stability is the
// first thing to give under sustained load).
function pressureStabilityOf(pressure: PressureLevel): StabilityWord {
  if (pressure === "low")      return "strong";
  if (pressure === "moderate") return "moderate";
  return "weak";
}

// transition-stability reads run-to-run volatility {low,moderate,high}
// → strong/moderate/weak.
function transitionStabilityOf(volatility: Volatility): StabilityWord {
  if (volatility === "low")      return "strong";
  if (volatility === "moderate") return "moderate";
  return "weak";
}

// Whether the upstream meta-pattern (Card 77 level) is holding. Reads
// lenient — MEDIUM and up are "stable" so a pressure-bitten but
// structurally-intact pattern still reads as stable; the pressure
// concern is surfaced separately in the pressure-stability tail.
function metaPatternWordOf(metaPatternLevel: Level): MetaWord {
  const r = LEVEL_RANK[metaPatternLevel];
  if (r >= 2) return "stable";    // MEDIUM, MEDIUM-HIGH, HIGH
  if (r >= 1) return "shifting";  // LOW-MEDIUM
  return "unstable";              // LOW
}

// ----- Derived level ---------------------------------------------------

// Meta-stability level floors on the meta-pattern level with single-
// step penalties for weak pressure-stability, weak load-stability, and
// high volatility. Mirrors Card 77's metaPatternLevelOf penalty style.
function metaStabilityLevelOf(
  metaPatternLevel: Level,
  pressureStab:     StabilityWord,
  loadStab:         StabilityWord,
  volatility:       Volatility,
): Level {
  let rank = LEVEL_RANK[metaPatternLevel];
  if (pressureStab === "weak") rank -= 1;
  if (loadStab     === "weak") rank -= 1;
  if (volatility   === "high") rank -= 1;
  rank = Math.max(0, Math.min(4, rank));
  return RANK_TO_LEVEL[rank];
}

// Trajectory walks curr → next → projected (forward, like Card 77) —
// meta-stability reads as a projection, not a centered checkpoint.
function buildTrajectory(level: Level, direction: Direction): string {
  const cur   = LEVEL_RANK[level];
  const slope = direction === "improving" ? 1 : direction === "deteriorating" ? -1 : 0;
  const next  = Math.max(0, Math.min(4, cur + slope));
  const proj  = Math.max(0, Math.min(4, cur + 2 * slope));
  const nextL = RANK_TO_LEVEL[next];
  const projL = RANK_TO_LEVEL[proj];
  const moves = level !== nextL || nextL !== projL;
  const tail  = moves ? "(projected)" : "(stable)";
  return `${level.toLowerCase()} → ${nextL.toLowerCase()} → ${projL.toLowerCase()} ${tail}`;
}

// ----- Drivers / Inhibitors / Risks / Reinforcement / Decay -----------

function collectDrivers(
  driftStab:       StabilityWord,
  direction:       Direction,
  synthesisStrong: boolean,
  metaWord:        MetaWord,
): string[] {
  const out: string[] = [];
  if (driftStab === "strong")    out.push("strong drift stability");
  if (direction === "improving") out.push("improving synthesis");
  else if (synthesisStrong)      out.push("stable synthesis");
  if (metaWord === "stable")     out.push("stable meta-pattern");
  return out;
}

function collectInhibitors(
  pressureStab: StabilityWord,
  loadStab:     StabilityWord,
  volatility:   Volatility,
): string[] {
  const out: string[] = [];
  if (pressureStab === "weak") out.push("weak pressure stability");
  if (loadStab === "partial" || loadStab === "weak") {
    out.push(`${loadStab} load stability`);
  }
  if (volatility !== "low") out.push("elevated volatility");
  return out;
}

function collectRisks(
  pressureStab: StabilityWord,
  loadStab:     StabilityWord,
  clarity:      ClarityLevel,
): string[] {
  const out: string[] = [];
  if (pressureStab !== "strong") out.push("pressure-induced instability");
  if (loadStab !== "strong")     out.push("load imbalance");
  if (clarity !== "strong")      out.push("clarity degradation");
  return out;
}

function collectReinforcement(
  clarity:      ClarityLevel,
  driftStab:    StabilityWord,
  pressureStab: StabilityWord,
  loadStab:     StabilityWord,
): string[] {
  const out: string[] = [];
  if (clarity !== "weak")   out.push("maintain clarity discipline");
  if (driftStab !== "weak") out.push("maintain drift control");
  // Pressure verb-shift: strong → maintain, else → strengthen. Always
  // emits so reinforcement stays wide.
  if (pressureStab === "strong") out.push("maintain pressure stability");
  else                           out.push("strengthen pressure stability");
  // Load verb-shift: strong → maintain, else → balance.
  if (loadStab === "strong") out.push("maintain load balance");
  else                       out.push("balance load");
  return out;
}

function collectDecay(
  pressureStab: StabilityWord,
  driftStab:    StabilityWord,
  clarity:      ClarityLevel,
): string[] {
  const out: string[] = [];
  if (pressureStab !== "strong") out.push("pressure may disrupt stability");
  if (driftStab !== "strong")    out.push("drift may re-emerge");
  if (clarity !== "strong")      out.push("clarity may weaken");
  return out;
}

// ----- Summary ---------------------------------------------------------

function buildSummary(
  direction:    Direction,
  driftStab:    StabilityWord,
  metaWord:     MetaWord,
  pressureStab: StabilityWord,
): string {
  const lead =
    direction === "improving"     ? "improving" :
    direction === "deteriorating" ? "weakening" :
    "steady";
  const s1 = `Operator meta-stability is ${lead}, with ${driftStab} drift-stability and ${metaWord} meta-pattern.`;
  if (pressureStab === "weak") {
    return `${s1} Pressure-stability remains weak and may disrupt overall stability.`;
  }
  return s1;
}

// ----- Entry point -----------------------------------------------------

export function buildOperatorMetaStability(
  operatorState:             string,
  operatorDiff:              string,
  operatorStability:         string,
  operatorResilience:        string,
  operatorImmunity:          string,
  operatorCoherence:         string,
  operatorSynthesis:         string,
  systemOperatorIntegration: string,
  operatorMetaPattern:       string,
): string {
  // Reserve upstream layers on the signature — Cards 72-74 + 76 stay
  // on the contract so future AOs can read resilience / immunity /
  // coherence / system-operator integration without changing callers.
  // Card 78 layers on the Card 77 meta-pattern (which already fuses
  // the Card 76 integration), so it reads the meta-pattern directly
  // rather than re-reading integration here.
  void operatorResilience;
  void operatorImmunity;
  void operatorCoherence;
  void systemOperatorIntegration;

  // Parse operator-state dims (Card 69).
  const load     = parseLoad(operatorState);
  const drift    = parseDrift(operatorState);
  const clarity  = parseClarity(operatorState);
  const pressure = parsePressure(operatorState);

  // Direction (Card 70) + volatility (Card 71).
  const direction  = parseDirection(operatorDiff);
  const volatility = parseVolatility(operatorStability);

  // Synthesis level (Card 75) → "strong" when MEDIUM-HIGH or better.
  const synthesisStrong = LEVEL_RANK[parseLayerLevel(operatorSynthesis, "Synthesis Level")] >= 3;

  // Meta-pattern level (Card 77).
  const metaPatternLevel = parseLayerLevel(operatorMetaPattern, "Meta-Pattern Level");
  const metaWord         = metaPatternWordOf(metaPatternLevel);

  // Per-dimension stability words.
  const driftStab      = driftStabilityOf(drift);
  const loadStab       = loadStabilityOf(load);
  const pressureStab   = pressureStabilityOf(pressure);
  const transitionStab = transitionStabilityOf(volatility);

  // Derived fields.
  const level         = metaStabilityLevelOf(metaPatternLevel, pressureStab, loadStab, volatility);
  const trajectory    = buildTrajectory(level, direction);
  const drivers       = collectDrivers(driftStab, direction, synthesisStrong, metaWord);
  const inhibitors    = collectInhibitors(pressureStab, loadStab, volatility);
  const risks         = collectRisks(pressureStab, loadStab, clarity);
  const reinforcement = collectReinforcement(clarity, driftStab, pressureStab, loadStab);
  const decay         = collectDecay(pressureStab, driftStab, clarity);
  const summary       = buildSummary(direction, driftStab, metaWord, pressureStab);

  const blocks: string[] = [];
  blocks.push("=== Operator Meta-Stability ===");
  blocks.push(`[Meta-Stability Level]\n${level}`);
  blocks.push(`[Transition-Stability]\n${transitionStab} stability`);
  blocks.push(`[Load-Stability]\n${loadStab} stability`);
  blocks.push(`[Pressure-Stability]\n${pressureStab} stability`);
  blocks.push(`[Drift-Stability]\n${driftStab} stability`);
  blocks.push(`[Meta-Stability Trajectory]\n${trajectory}`);
  blocks.push(
    drivers.length === 0
      ? `[Meta-Stability Drivers]\n(none)`
      : `[Meta-Stability Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Meta-Stability Inhibitors]\n(none)`
      : `[Meta-Stability Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(
    risks.length === 0
      ? `[Meta-Stability Risks]\n(none)`
      : `[Meta-Stability Risks]\n${risks.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    reinforcement.length === 0
      ? `[Meta-Stability Reinforcement]\n(none)`
      : `[Meta-Stability Reinforcement]\n${reinforcement.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    decay.length === 0
      ? `[Meta-Stability Decay]\n(none)`
      : `[Meta-Stability Decay]\n${decay.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(`[Operator Meta-Stability Summary]\n${summary}`);

  return blocks.join("\n\n");
}
