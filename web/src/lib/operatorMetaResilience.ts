// Card 79 — Operator Meta-Resilience (Phase-5 AO-3).
//
// Third of the Operator Advanced Operators (AO-1 through AO-14,
// Cards 77-90). Same weight class as Cards 77-78: a lighter,
// higher-order interpretive layer over the operator meta-stack rather
// than a new structural engine.
//
// Card 79 is the higher-order resilience engine that sits above the
// operator-level resilience of Card 72. It evaluates operator
// *meta-resilience* — the operator's capacity to absorb volatility,
// pressure, drift, and load — by fusing the seven operator core
// outputs (Cards 69-75), the system-operator integration (Card 76),
// the operator meta-pattern (Card 77), and the operator meta-stability
// (Card 78) into a single 12-section read:
//
//   [Meta-Resilience Level]           LOW … HIGH
//   [Volatility-Resilience]           "<word> resilience"
//   [Pressure-Resilience]             "<word> resilience"
//   [Drift-Resilience]                "<word> resilience"
//   [Load-Resilience]                 "<word> resilience"
//   [Meta-Resilience Trajectory]      prev → level → projected (state)
//   [Meta-Resilience Drivers]
//   [Meta-Resilience Inhibitors]
//   [Meta-Resilience Risks]
//   [Meta-Resilience Reinforcement]
//   [Meta-Resilience Decay]
//   [Operator Meta-Resilience Summary]
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

// Meta-resilience word scale (weak < partial < moderate < strong).
type ResilienceWord = "weak" | "partial" | "moderate" | "strong";

// How the upstream meta-pattern is holding (derived from Card 77 level).
type MetaWord = "stable" | "shifting" | "unstable";

// ----- Section parser (same pattern as Cards 62-78) -------------------

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

// ----- Per-dimension resilience words ---------------------------------

// drift {low,moderate,high} → strong/partial/weak
function driftResilienceOf(drift: DriftLevel): ResilienceWord {
  if (drift === "low")      return "strong";
  if (drift === "moderate") return "partial";
  return "weak";
}

// load {low,moderate,high} → strong/partial/weak
function loadResilienceOf(load: LoadLevel): ResilienceWord {
  if (load === "low")      return "strong";
  if (load === "moderate") return "partial";
  return "weak";
}

// pressure {low,moderate,elevated,high} → strong/moderate/weak
// (elevated + high both collapse to weak — pressure resilience is the
// first thing to give under sustained load).
function pressureResilienceOf(pressure: PressureLevel): ResilienceWord {
  if (pressure === "low")      return "strong";
  if (pressure === "moderate") return "moderate";
  return "weak";
}

// volatility-resilience reads run-to-run volatility {low,moderate,high}
// → strong/moderate/weak.
function volatilityResilienceOf(volatility: Volatility): ResilienceWord {
  if (volatility === "low")      return "strong";
  if (volatility === "moderate") return "moderate";
  return "weak";
}

// Whether the upstream meta-pattern (Card 77 level) is holding. Reads
// lenient — MEDIUM and up are "stable" (matches Card 78), so a
// pressure-bitten but structurally-intact pattern still reads stable.
function metaPatternWordOf(metaPatternLevel: Level): MetaWord {
  const r = LEVEL_RANK[metaPatternLevel];
  if (r >= 2) return "stable";    // MEDIUM, MEDIUM-HIGH, HIGH
  if (r >= 1) return "shifting";  // LOW-MEDIUM
  return "unstable";              // LOW
}

// ----- Derived level ---------------------------------------------------

// Meta-resilience level floors on the lower of the meta-stability level
// (Card 78) and the operator resilience level (Card 72) — meta-
// resilience can't outrun either the stability it builds on or the
// raw resilience it sits above — then takes single-step penalties for
// weak pressure-resilience, weak load-resilience, and high volatility.
function metaResilienceLevelOf(
  metaStabilityLevel:     Level,
  operatorResilienceLevel: Level,
  pressureRes:            ResilienceWord,
  loadRes:                ResilienceWord,
  volatility:             Volatility,
): Level {
  let rank = Math.min(LEVEL_RANK[metaStabilityLevel], LEVEL_RANK[operatorResilienceLevel]);
  if (pressureRes === "weak") rank -= 1;
  if (loadRes     === "weak") rank -= 1;
  if (volatility  === "high") rank -= 1;
  rank = Math.max(0, Math.min(4, rank));
  return RANK_TO_LEVEL[rank];
}

// Trajectory walks prev → level → projected (centered, like Cards
// 72/76) — resilience reads as a momentum band around the current
// level, not a forward-only projection.
function buildTrajectory(level: Level, direction: Direction): string {
  const cur      = LEVEL_RANK[level];
  const slope    = direction === "improving" ? 1 : direction === "deteriorating" ? -1 : 0;
  const prevRank = Math.max(0, Math.min(4, cur - slope));
  const projRank = Math.max(0, Math.min(4, cur + slope));
  const prev = RANK_TO_LEVEL[prevRank];
  const proj = RANK_TO_LEVEL[projRank];
  const moves = prev !== level || level !== proj;
  const tail  = moves ? "(projected)" : "(stable)";
  return `${prev.toLowerCase()} → ${level.toLowerCase()} → ${proj.toLowerCase()} ${tail}`;
}

// ----- Drivers / Inhibitors / Risks / Reinforcement / Decay -----------

function collectDrivers(
  driftRes:        ResilienceWord,
  direction:       Direction,
  synthesisStrong: boolean,
  metaWord:        MetaWord,
): string[] {
  const out: string[] = [];
  if (driftRes === "strong")     out.push("strong drift resilience");
  if (direction === "improving") out.push("improving synthesis");
  else if (synthesisStrong)      out.push("stable synthesis");
  if (metaWord === "stable")     out.push("stable meta-pattern");
  return out;
}

function collectInhibitors(
  pressureRes: ResilienceWord,
  loadRes:     ResilienceWord,
  volatility:  Volatility,
): string[] {
  const out: string[] = [];
  if (pressureRes === "weak") out.push("weak pressure resilience");
  if (loadRes === "partial" || loadRes === "weak") {
    out.push(`${loadRes} load resilience`);
  }
  if (volatility !== "low") out.push("elevated volatility");
  return out;
}

function collectRisks(
  pressureRes: ResilienceWord,
  loadRes:     ResilienceWord,
  clarity:     ClarityLevel,
): string[] {
  const out: string[] = [];
  if (pressureRes !== "strong") out.push("pressure-induced degradation");
  if (loadRes !== "strong")     out.push("load imbalance");
  if (clarity !== "strong")     out.push("clarity fragmentation");
  return out;
}

function collectReinforcement(
  clarity:     ClarityLevel,
  driftRes:    ResilienceWord,
  pressureRes: ResilienceWord,
  loadRes:     ResilienceWord,
): string[] {
  const out: string[] = [];
  if (clarity !== "weak")  out.push("maintain clarity discipline");
  if (driftRes !== "weak") out.push("maintain drift control");
  // Pressure verb-shift: strong → maintain, else → strengthen. Always
  // emits so reinforcement stays wide.
  if (pressureRes === "strong") out.push("maintain pressure resilience");
  else                          out.push("strengthen pressure resilience");
  // Load verb-shift: strong → maintain, else → balance.
  if (loadRes === "strong") out.push("maintain load balance");
  else                      out.push("balance load");
  return out;
}

function collectDecay(
  pressureRes: ResilienceWord,
  driftRes:    ResilienceWord,
  clarity:     ClarityLevel,
): string[] {
  const out: string[] = [];
  if (pressureRes !== "strong") out.push("pressure may disrupt resilience");
  if (driftRes !== "strong")    out.push("drift may re-emerge");
  if (clarity !== "strong")     out.push("clarity may weaken");
  return out;
}

// ----- Summary ---------------------------------------------------------

function buildSummary(
  direction:   Direction,
  driftRes:    ResilienceWord,
  metaWord:    MetaWord,
  pressureRes: ResilienceWord,
): string {
  const lead =
    direction === "improving"     ? "strengthening" :
    direction === "deteriorating" ? "weakening" :
    "steady";
  const s1 = `Operator meta-resilience is ${lead}, with ${driftRes} drift-resilience and ${metaWord} meta-pattern.`;
  if (pressureRes === "weak") {
    return `${s1} Pressure-resilience remains weak and may disrupt overall resilience.`;
  }
  return s1;
}

// ----- Entry point -----------------------------------------------------

export function buildOperatorMetaResilience(
  operatorState:             string,
  operatorDiff:              string,
  operatorStability:         string,
  operatorResilience:        string,
  operatorImmunity:          string,
  operatorCoherence:         string,
  operatorSynthesis:         string,
  systemOperatorIntegration: string,
  operatorMetaPattern:       string,
  operatorMetaStability:     string,
): string {
  // Reserve upstream layers on the signature — Cards 73/74 + 76 stay
  // on the contract so future AOs can read immunity / coherence /
  // system-operator integration without changing callers. Card 79
  // layers on the Card 78 meta-stability (which already fuses the
  // Card 76/77 stack) plus the Card 72 operator resilience it sits
  // above, so it reads those directly.
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

  // Operator resilience level (Card 72) — the raw resilience this
  // meta-layer sits above.
  const operatorResilienceLevel = parseLayerLevel(operatorResilience, "Resilience Level");

  // Synthesis level (Card 75) → "strong" when MEDIUM-HIGH or better.
  const synthesisStrong = LEVEL_RANK[parseLayerLevel(operatorSynthesis, "Synthesis Level")] >= 3;

  // Meta-pattern level (Card 77) + meta-stability level (Card 78).
  const metaPatternLevel   = parseLayerLevel(operatorMetaPattern, "Meta-Pattern Level");
  const metaStabilityLevel = parseLayerLevel(operatorMetaStability, "Meta-Stability Level");
  const metaWord           = metaPatternWordOf(metaPatternLevel);

  // Per-dimension resilience words.
  const driftRes      = driftResilienceOf(drift);
  const loadRes       = loadResilienceOf(load);
  const pressureRes   = pressureResilienceOf(pressure);
  const volatilityRes = volatilityResilienceOf(volatility);

  // Derived fields.
  const level         = metaResilienceLevelOf(metaStabilityLevel, operatorResilienceLevel, pressureRes, loadRes, volatility);
  const trajectory    = buildTrajectory(level, direction);
  const drivers       = collectDrivers(driftRes, direction, synthesisStrong, metaWord);
  const inhibitors    = collectInhibitors(pressureRes, loadRes, volatility);
  const risks         = collectRisks(pressureRes, loadRes, clarity);
  const reinforcement = collectReinforcement(clarity, driftRes, pressureRes, loadRes);
  const decay         = collectDecay(pressureRes, driftRes, clarity);
  const summary       = buildSummary(direction, driftRes, metaWord, pressureRes);

  const blocks: string[] = [];
  blocks.push("=== Operator Meta-Resilience ===");
  blocks.push(`[Meta-Resilience Level]\n${level}`);
  blocks.push(`[Volatility-Resilience]\n${volatilityRes} resilience`);
  blocks.push(`[Pressure-Resilience]\n${pressureRes} resilience`);
  blocks.push(`[Drift-Resilience]\n${driftRes} resilience`);
  blocks.push(`[Load-Resilience]\n${loadRes} resilience`);
  blocks.push(`[Meta-Resilience Trajectory]\n${trajectory}`);
  blocks.push(
    drivers.length === 0
      ? `[Meta-Resilience Drivers]\n(none)`
      : `[Meta-Resilience Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Meta-Resilience Inhibitors]\n(none)`
      : `[Meta-Resilience Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(
    risks.length === 0
      ? `[Meta-Resilience Risks]\n(none)`
      : `[Meta-Resilience Risks]\n${risks.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    reinforcement.length === 0
      ? `[Meta-Resilience Reinforcement]\n(none)`
      : `[Meta-Resilience Reinforcement]\n${reinforcement.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    decay.length === 0
      ? `[Meta-Resilience Decay]\n(none)`
      : `[Meta-Resilience Decay]\n${decay.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(`[Operator Meta-Resilience Summary]\n${summary}`);

  return blocks.join("\n\n");
}
