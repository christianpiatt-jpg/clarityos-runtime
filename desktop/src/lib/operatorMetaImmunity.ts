// Card 80 — Operator Meta-Immunity (Phase-5 AO-4).
//
// Fourth of the Operator Advanced Operators (AO-1 through AO-14,
// Cards 77-90) and the final card of the first AO cluster (77-80).
// Same weight class as Cards 77-79: a lighter, higher-order
// interpretive layer over the operator meta-stack rather than a new
// structural engine.
//
// Card 80 is the higher-order immunity engine that sits above the
// operator-level immunity of Card 73 and the meta-pattern / meta-
// stability / meta-resilience engines (Cards 77-79). It evaluates
// operator *meta-immunity* — the operator's resistance to clarity
// loss, drift, load, pressure, and volatility — by fusing the seven
// operator core outputs (Cards 69-75), the system-operator integration
// (Card 76), the operator meta-pattern (Card 77), the operator meta-
// stability (Card 78), and the operator meta-resilience (Card 79) into
// a single 13-section read:
//
//   [Meta-Immunity Level]             LOW … HIGH
//   [Clarity-Immunity]                "<word> immunity"
//   [Drift-Immunity]                  "<word> immunity"
//   [Load-Immunity]                   "<word> immunity"
//   [Pressure-Immunity]               "<word> immunity"
//   [Volatility-Immunity]             "<word> immunity"
//   [Meta-Immunity Trajectory]        curr → next → projected (state)
//   [Meta-Immunity Drivers]
//   [Meta-Immunity Inhibitors]
//   [Meta-Immunity Risks]
//   [Meta-Immunity Reinforcement]
//   [Meta-Immunity Decay]
//   [Operator Meta-Immunity Summary]
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

// Meta-immunity word scale (weak < partial < moderate < strong).
type ImmunityWord = "weak" | "partial" | "moderate" | "strong";

// How the upstream meta-pattern is holding (derived from Card 77 level).
type MetaWord = "stable" | "shifting" | "unstable";

// ----- Section parser (same pattern as Cards 62-79) -------------------

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

// ----- Per-dimension immunity words -----------------------------------

// clarity {weak,partial,strong} → weak/partial/strong (direct mapping).
function clarityImmunityOf(clarity: ClarityLevel): ImmunityWord {
  if (clarity === "strong")  return "strong";
  if (clarity === "partial") return "partial";
  return "weak";
}

// drift {low,moderate,high} → strong/partial/weak
function driftImmunityOf(drift: DriftLevel): ImmunityWord {
  if (drift === "low")      return "strong";
  if (drift === "moderate") return "partial";
  return "weak";
}

// load {low,moderate,high} → strong/partial/weak
function loadImmunityOf(load: LoadLevel): ImmunityWord {
  if (load === "low")      return "strong";
  if (load === "moderate") return "partial";
  return "weak";
}

// pressure {low,moderate,elevated,high} → strong/moderate/weak
// (elevated + high both collapse to weak — pressure immunity is the
// first thing to give under sustained load).
function pressureImmunityOf(pressure: PressureLevel): ImmunityWord {
  if (pressure === "low")      return "strong";
  if (pressure === "moderate") return "moderate";
  return "weak";
}

// volatility-immunity reads run-to-run volatility {low,moderate,high}
// → strong/moderate/weak.
function volatilityImmunityOf(volatility: Volatility): ImmunityWord {
  if (volatility === "low")      return "strong";
  if (volatility === "moderate") return "moderate";
  return "weak";
}

// Whether the upstream meta-pattern (Card 77 level) is holding. Reads
// lenient — MEDIUM and up are "stable" (matches Cards 78-79).
function metaPatternWordOf(metaPatternLevel: Level): MetaWord {
  const r = LEVEL_RANK[metaPatternLevel];
  if (r >= 2) return "stable";    // MEDIUM, MEDIUM-HIGH, HIGH
  if (r >= 1) return "shifting";  // LOW-MEDIUM
  return "unstable";              // LOW
}

// ----- Derived level ---------------------------------------------------

// Meta-immunity level floors on the lower of the meta-resilience level
// (Card 79) and the operator immunity level (Card 73) — meta-immunity
// can't outrun either the resilience it builds on or the raw immunity
// it sits above — then takes single-step penalties for weak pressure-
// immunity, weak load-immunity, and high volatility.
function metaImmunityLevelOf(
  metaResilienceLevel:   Level,
  operatorImmunityLevel: Level,
  pressureImm:           ImmunityWord,
  loadImm:               ImmunityWord,
  volatility:            Volatility,
): Level {
  let rank = Math.min(LEVEL_RANK[metaResilienceLevel], LEVEL_RANK[operatorImmunityLevel]);
  if (pressureImm === "weak") rank -= 1;
  if (loadImm     === "weak") rank -= 1;
  if (volatility  === "high") rank -= 1;
  rank = Math.max(0, Math.min(4, rank));
  return RANK_TO_LEVEL[rank];
}

// Trajectory walks curr → next → projected (forward, like Card 78) —
// immunity reads as a forward projection of preventive capacity.
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
  clarityImm: ImmunityWord,
  driftImm:   ImmunityWord,
  metaWord:   MetaWord,
): string[] {
  const out: string[] = [];
  if (clarityImm === "strong") out.push("strong clarity immunity");
  if (driftImm === "strong")   out.push("strong drift immunity");
  if (metaWord === "stable")   out.push("stable meta-pattern");
  return out;
}

function collectInhibitors(
  pressureImm: ImmunityWord,
  loadImm:     ImmunityWord,
  volatility:  Volatility,
): string[] {
  const out: string[] = [];
  if (pressureImm === "weak") out.push("weak pressure immunity");
  if (loadImm === "partial" || loadImm === "weak") {
    out.push(`${loadImm} load immunity`);
  }
  if (volatility !== "low") out.push("elevated volatility");
  return out;
}

function collectRisks(
  pressureImm: ImmunityWord,
  loadImm:     ImmunityWord,
  clarity:     ClarityLevel,
): string[] {
  const out: string[] = [];
  if (pressureImm !== "strong") out.push("pressure-induced degradation");
  if (loadImm !== "strong")     out.push("load imbalance");
  if (clarity !== "strong")     out.push("clarity fragmentation");
  return out;
}

function collectReinforcement(
  clarity:     ClarityLevel,
  driftImm:    ImmunityWord,
  pressureImm: ImmunityWord,
  loadImm:     ImmunityWord,
): string[] {
  const out: string[] = [];
  if (clarity !== "weak")  out.push("maintain clarity discipline");
  if (driftImm !== "weak") out.push("maintain drift control");
  // Pressure verb-shift: strong → maintain, else → strengthen. Always
  // emits so reinforcement stays wide.
  if (pressureImm === "strong") out.push("maintain pressure immunity");
  else                          out.push("strengthen pressure immunity");
  // Load verb-shift: strong → maintain, else → balance.
  if (loadImm === "strong") out.push("maintain load balance");
  else                      out.push("balance load");
  return out;
}

function collectDecay(
  pressureImm: ImmunityWord,
  driftImm:    ImmunityWord,
  clarity:     ClarityLevel,
): string[] {
  const out: string[] = [];
  if (pressureImm !== "strong") out.push("pressure may disrupt immunity");
  if (driftImm !== "strong")    out.push("drift may re-emerge");
  if (clarity !== "strong")     out.push("clarity may weaken");
  return out;
}

// ----- Summary ---------------------------------------------------------

function buildSummary(
  direction:   Direction,
  clarityImm:  ImmunityWord,
  driftImm:    ImmunityWord,
  pressureImm: ImmunityWord,
): string {
  const lead =
    direction === "improving"     ? "strengthening" :
    direction === "deteriorating" ? "weakening" :
    "steady";
  // Collapse the shared adjective when clarity- and drift-immunity
  // read the same word ("strong clarity- and drift-immunity"),
  // otherwise name both explicitly.
  const cd = clarityImm === driftImm
    ? `${clarityImm} clarity- and drift-immunity`
    : `${clarityImm} clarity- and ${driftImm} drift-immunity`;
  const s1 = `Operator meta-immunity is ${lead}, with ${cd}.`;
  if (pressureImm === "weak") {
    return `${s1} Pressure-immunity remains weak and may disrupt overall immunity.`;
  }
  return s1;
}

// ----- Entry point -----------------------------------------------------

export function buildOperatorMetaImmunity(
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
  operatorMetaResilience:    string,
): string {
  // Reserve upstream layers on the signature — Cards 72/74/75 + 76 +
  // 78 stay on the contract so future AOs can read resilience /
  // coherence / synthesis / system-operator integration / meta-
  // stability without changing callers. Card 80 layers on the Card 79
  // meta-resilience (which already folds the 76/77/78 stack) plus the
  // Card 73 operator immunity it sits above, so it reads those directly.
  void operatorResilience;
  void operatorCoherence;
  void operatorSynthesis;
  void systemOperatorIntegration;
  void operatorMetaStability;

  // Parse operator-state dims (Card 69).
  const load     = parseLoad(operatorState);
  const drift    = parseDrift(operatorState);
  const clarity  = parseClarity(operatorState);
  const pressure = parsePressure(operatorState);

  // Direction (Card 70) + volatility (Card 71).
  const direction  = parseDirection(operatorDiff);
  const volatility = parseVolatility(operatorStability);

  // Operator immunity level (Card 73) — the raw immunity this meta-
  // layer sits above.
  const operatorImmunityLevel = parseLayerLevel(operatorImmunity, "Immunity Level");

  // Meta-pattern level (Card 77) + meta-resilience level (Card 79).
  const metaPatternLevel    = parseLayerLevel(operatorMetaPattern, "Meta-Pattern Level");
  const metaResilienceLevel = parseLayerLevel(operatorMetaResilience, "Meta-Resilience Level");
  const metaWord            = metaPatternWordOf(metaPatternLevel);

  // Per-dimension immunity words.
  const clarityImm    = clarityImmunityOf(clarity);
  const driftImm      = driftImmunityOf(drift);
  const loadImm       = loadImmunityOf(load);
  const pressureImm   = pressureImmunityOf(pressure);
  const volatilityImm = volatilityImmunityOf(volatility);

  // Derived fields.
  const level         = metaImmunityLevelOf(metaResilienceLevel, operatorImmunityLevel, pressureImm, loadImm, volatility);
  const trajectory    = buildTrajectory(level, direction);
  const drivers       = collectDrivers(clarityImm, driftImm, metaWord);
  const inhibitors    = collectInhibitors(pressureImm, loadImm, volatility);
  const risks         = collectRisks(pressureImm, loadImm, clarity);
  const reinforcement = collectReinforcement(clarity, driftImm, pressureImm, loadImm);
  const decay         = collectDecay(pressureImm, driftImm, clarity);
  const summary       = buildSummary(direction, clarityImm, driftImm, pressureImm);

  const blocks: string[] = [];
  blocks.push("=== Operator Meta-Immunity ===");
  blocks.push(`[Meta-Immunity Level]\n${level}`);
  blocks.push(`[Clarity-Immunity]\n${clarityImm} immunity`);
  blocks.push(`[Drift-Immunity]\n${driftImm} immunity`);
  blocks.push(`[Load-Immunity]\n${loadImm} immunity`);
  blocks.push(`[Pressure-Immunity]\n${pressureImm} immunity`);
  blocks.push(`[Volatility-Immunity]\n${volatilityImm} immunity`);
  blocks.push(`[Meta-Immunity Trajectory]\n${trajectory}`);
  blocks.push(
    drivers.length === 0
      ? `[Meta-Immunity Drivers]\n(none)`
      : `[Meta-Immunity Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Meta-Immunity Inhibitors]\n(none)`
      : `[Meta-Immunity Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(
    risks.length === 0
      ? `[Meta-Immunity Risks]\n(none)`
      : `[Meta-Immunity Risks]\n${risks.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    reinforcement.length === 0
      ? `[Meta-Immunity Reinforcement]\n(none)`
      : `[Meta-Immunity Reinforcement]\n${reinforcement.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    decay.length === 0
      ? `[Meta-Immunity Decay]\n(none)`
      : `[Meta-Immunity Decay]\n${decay.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(`[Operator Meta-Immunity Summary]\n${summary}`);

  return blocks.join("\n\n");
}
