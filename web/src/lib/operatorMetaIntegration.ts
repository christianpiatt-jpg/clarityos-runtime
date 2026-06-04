// Card 81 — Operator Meta-Integration (Phase-5 AO-5).
//
// First card of the second Operator Advanced Operator cluster (AO-5
// through AO-8, Cards 81-84) — the meta-integration cluster. Same
// weight class as Cards 77-80: a lighter, higher-order interpretive
// layer over the operator meta-stack rather than a new structural
// engine.
//
// Card 81 is the higher-order integration engine that sits above
// operator synthesis (Card 75), system-operator integration (Card 76),
// and the four AO-cluster-1 meta-layers — meta-pattern (77), meta-
// stability (78), meta-resilience (79), and meta-immunity (80). It is
// the first card that folds every meta-operator into a single
// interpretive read. Each "X-Integration" dimension reads the level of
// the corresponding upstream meta-layer and reports how well-integrated
// that facet is:
//
//   [Meta-Integration Level]          LOW … HIGH
//   [Coherence-Integration]           "<word> integration"
//   [Synthesis-Integration]           "<word> integration"
//   [Stability-Integration]           "<word> stability"
//   [Resilience-Integration]          "<word> resilience"
//   [Immunity-Integration]            "<word> immunity"
//   [Pattern-Integration]             "<word> pattern integration"
//   [Meta-Integration Trajectory]     prev → level → projected (state)
//   [Meta-Integration Drivers]
//   [Meta-Integration Inhibitors]
//   [Meta-Integration Risks]
//   [Meta-Integration Reinforcement]
//   [Meta-Integration Decay]
//   [Operator Meta-Integration Summary]
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

// Integration word scale (weak < partial < moderate < strong).
type IntegrationWord = "weak" | "partial" | "moderate" | "strong";

// How the upstream meta-pattern is holding (derived from Card 77 level).
type PatternWord = "stable" | "shifting" | "unstable";

// ----- Section parser (same pattern as Cards 62-80) -------------------

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

// Direction inferred from Card 70's diff summary.
function parseDirection(diffText: string): Direction {
  const summary = parseSection(diffText, "Operator Diff Summary");
  if (summary.includes("improving"))     return "improving";
  if (summary.includes("deteriorating")) return "deteriorating";
  return "stable";
}

// ----- Level → word mappings ------------------------------------------

// Maps an upstream meta-layer level to an integration word. HIGH and
// MEDIUM-HIGH both read "strong" (a well-integrated facet), MEDIUM
// "moderate", LOW-MEDIUM "partial", LOW "weak".
function levelWord(level: Level): IntegrationWord {
  const r = LEVEL_RANK[level];
  if (r >= 3) return "strong";    // HIGH, MEDIUM-HIGH
  if (r === 2) return "moderate"; // MEDIUM
  if (r === 1) return "partial";  // LOW-MEDIUM
  return "weak";                  // LOW
}

// Whether the upstream meta-pattern (Card 77 level) is holding. Reads
// lenient — MEDIUM and up are "stable" (matches Cards 78-80).
function patternWordOf(metaPatternLevel: Level): PatternWord {
  const r = LEVEL_RANK[metaPatternLevel];
  if (r >= 2) return "stable";    // MEDIUM, MEDIUM-HIGH, HIGH
  if (r >= 1) return "shifting";  // LOW-MEDIUM
  return "unstable";              // LOW
}

// ----- Derived level ---------------------------------------------------

// Meta-integration level is the floored average of the six integrated
// meta-layer levels — the unified read can't sit above the mean of the
// facets it integrates. Mirrors Card 76's averaging style.
function metaIntegrationLevelOf(levels: Level[]): Level {
  const sum = levels.reduce((acc, l) => acc + LEVEL_RANK[l], 0);
  const avg = Math.floor(sum / levels.length);
  return RANK_TO_LEVEL[Math.max(0, Math.min(4, avg))];
}

// Trajectory walks prev → level → projected (centered, like Cards
// 72/76/79).
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
  synthesisWord:  IntegrationWord,
  resilienceWord: IntegrationWord,
  patternWord:    PatternWord,
): string[] {
  const out: string[] = [];
  if (synthesisWord === "strong")  out.push("strong synthesis integration");
  if (resilienceWord === "strong") out.push("strong resilience integration");
  if (patternWord === "stable")    out.push("stable pattern integration");
  return out;
}

function collectInhibitors(
  immunityWord:  IntegrationWord,
  stabilityWord: IntegrationWord,
  pressure:      PressureLevel,
): string[] {
  const out: string[] = [];
  if (immunityWord !== "strong")  out.push(`${immunityWord} immunity integration`);
  if (stabilityWord !== "strong") out.push(`${stabilityWord} stability integration`);
  if (pressure === "elevated" || pressure === "high") out.push("elevated pressure");
  return out;
}

function collectRisks(
  pressure: PressureLevel,
  clarity:  ClarityLevel,
  load:     LoadLevel,
): string[] {
  const out: string[] = [];
  if (pressure !== "low")   out.push("pressure-induced fragmentation");
  if (clarity !== "strong") out.push("clarity degradation");
  if (load !== "low")       out.push("load imbalance");
  return out;
}

function collectReinforcement(
  clarity:      ClarityLevel,
  drift:        DriftLevel,
  immunityWord: IntegrationWord,
  load:         LoadLevel,
): string[] {
  const out: string[] = [];
  if (clarity !== "weak") out.push("maintain clarity discipline");
  if (drift !== "high")   out.push("maintain drift control");
  // Immunity verb-shift: strong → maintain, else → strengthen. Always
  // emits so reinforcement stays wide.
  if (immunityWord === "strong") out.push("maintain immunity integration");
  else                           out.push("strengthen immunity integration");
  // Load verb-shift: low → maintain, else → balance.
  if (load === "low") out.push("maintain load balance");
  else                out.push("balance load");
  return out;
}

function collectDecay(
  pressure: PressureLevel,
  drift:    DriftLevel,
  clarity:  ClarityLevel,
): string[] {
  const out: string[] = [];
  if (pressure !== "low")   out.push("pressure may disrupt integration");
  if (drift !== "low")      out.push("drift may re-emerge");
  if (clarity !== "strong") out.push("clarity may weaken");
  return out;
}

// ----- Summary ---------------------------------------------------------

function buildSummary(
  direction:      Direction,
  synthesisWord:  IntegrationWord,
  resilienceWord: IntegrationWord,
  immunityWord:   IntegrationWord,
): string {
  const lead =
    direction === "improving"     ? "strengthening" :
    direction === "deteriorating" ? "weakening" :
    "steady";
  // Collapse the shared adjective when synthesis- and resilience-
  // integration read the same word ("strong synthesis- and resilience-
  // integration"), otherwise name both explicitly.
  const sr = synthesisWord === resilienceWord
    ? `${synthesisWord} synthesis- and resilience-integration`
    : `${synthesisWord} synthesis- and ${resilienceWord} resilience-integration`;
  const s1 = `Operator meta-integration is ${lead}, with ${sr}.`;
  if (immunityWord !== "strong") {
    return `${s1} Immunity-integration remains ${immunityWord} and may disrupt overall integration.`;
  }
  return s1;
}

// ----- Entry point -----------------------------------------------------

export function buildOperatorMetaIntegration(
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
  operatorMetaImmunity:      string,
): string {
  // Reserve upstream layers on the signature — Cards 71/72/73 + 76 stay
  // on the contract so future AOs can read operator stability /
  // resilience / immunity / system-operator integration without
  // changing callers. Card 81 integrates the meta-layer levels
  // directly (coherence 74, synthesis 75, meta-pattern 77, meta-
  // stability 78, meta-resilience 79, meta-immunity 80), which already
  // fold the 71/72/73/76 stack.
  void operatorStability;
  void operatorResilience;
  void operatorImmunity;
  void systemOperatorIntegration;

  // Parse operator-state dims (Card 69) + direction (Card 70).
  const load      = parseLoad(operatorState);
  const drift     = parseDrift(operatorState);
  const clarity   = parseClarity(operatorState);
  const pressure  = parsePressure(operatorState);
  const direction = parseDirection(operatorDiff);

  // Parse the integrated meta-layer levels.
  const coherenceLevel      = parseLayerLevel(operatorCoherence, "Coherence Level");
  const synthesisLevel      = parseLayerLevel(operatorSynthesis, "Synthesis Level");
  const metaPatternLevel    = parseLayerLevel(operatorMetaPattern, "Meta-Pattern Level");
  const metaStabilityLevel  = parseLayerLevel(operatorMetaStability, "Meta-Stability Level");
  const metaResilienceLevel = parseLayerLevel(operatorMetaResilience, "Meta-Resilience Level");
  const metaImmunityLevel   = parseLayerLevel(operatorMetaImmunity, "Meta-Immunity Level");

  // Per-dimension integration words.
  const coherenceWord  = levelWord(coherenceLevel);
  const synthesisWord  = levelWord(synthesisLevel);
  const stabilityWord  = levelWord(metaStabilityLevel);
  const resilienceWord = levelWord(metaResilienceLevel);
  const immunityWord   = levelWord(metaImmunityLevel);
  const patternWord    = patternWordOf(metaPatternLevel);

  // Derived fields.
  const level = metaIntegrationLevelOf([
    coherenceLevel, synthesisLevel, metaStabilityLevel,
    metaResilienceLevel, metaImmunityLevel, metaPatternLevel,
  ]);
  const trajectory    = buildTrajectory(level, direction);
  const drivers       = collectDrivers(synthesisWord, resilienceWord, patternWord);
  const inhibitors    = collectInhibitors(immunityWord, stabilityWord, pressure);
  const risks         = collectRisks(pressure, clarity, load);
  const reinforcement = collectReinforcement(clarity, drift, immunityWord, load);
  const decay         = collectDecay(pressure, drift, clarity);
  const summary       = buildSummary(direction, synthesisWord, resilienceWord, immunityWord);

  const blocks: string[] = [];
  blocks.push("=== Operator Meta-Integration ===");
  blocks.push(`[Meta-Integration Level]\n${level}`);
  blocks.push(`[Coherence-Integration]\n${coherenceWord} integration`);
  blocks.push(`[Synthesis-Integration]\n${synthesisWord} integration`);
  blocks.push(`[Stability-Integration]\n${stabilityWord} stability`);
  blocks.push(`[Resilience-Integration]\n${resilienceWord} resilience`);
  blocks.push(`[Immunity-Integration]\n${immunityWord} immunity`);
  blocks.push(`[Pattern-Integration]\n${patternWord} pattern integration`);
  blocks.push(`[Meta-Integration Trajectory]\n${trajectory}`);
  blocks.push(
    drivers.length === 0
      ? `[Meta-Integration Drivers]\n(none)`
      : `[Meta-Integration Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Meta-Integration Inhibitors]\n(none)`
      : `[Meta-Integration Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(
    risks.length === 0
      ? `[Meta-Integration Risks]\n(none)`
      : `[Meta-Integration Risks]\n${risks.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    reinforcement.length === 0
      ? `[Meta-Integration Reinforcement]\n(none)`
      : `[Meta-Integration Reinforcement]\n${reinforcement.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    decay.length === 0
      ? `[Meta-Integration Decay]\n(none)`
      : `[Meta-Integration Decay]\n${decay.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(`[Operator Meta-Integration Summary]\n${summary}`);

  return blocks.join("\n\n");
}
