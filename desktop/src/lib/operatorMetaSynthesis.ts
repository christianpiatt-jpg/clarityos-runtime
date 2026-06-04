// Card 84 — Operator Meta-Synthesis (Phase-5 AO-8).
//
// Final card of the meta-integration cluster (AO-5 through AO-8, Cards
// 81-84) and the capstone of AO Cluster #2. Same weight class as Cards
// 77-83: a lighter, higher-order interpretive layer over the operator
// meta-stack.
//
// Card 84 is the highest-order synthesis engine in the operator
// architecture — the final unification operator. Where Card 75
// synthesised the operator's own dimensions, meta-synthesis unifies
// every meta-layer beneath it: meta-pattern (77), meta-stability (78),
// meta-resilience (79), meta-immunity (80), meta-integration (81),
// meta-alignment (82), and meta-coherence (83). Each "X-Synthesis"
// dimension reads the level of the corresponding meta-layer:
//
//   [Meta-Synthesis Level]            LOW … HIGH
//   [Coherence-Synthesis]             "<word> synthesis"
//   [Stability-Synthesis]             "<word> synthesis"
//   [Resilience-Synthesis]            "<word> synthesis"
//   [Immunity-Synthesis]              "<word> synthesis"
//   [Integration-Synthesis]           "<word> integration synthesis"
//   [Alignment-Synthesis]             "<word> alignment synthesis"
//   [Pattern-Synthesis]               "<word> pattern synthesis"
//   [Meta-Synthesis Trajectory]       prev → level → projected (state)
//   [Meta-Synthesis Drivers]
//   [Meta-Synthesis Inhibitors]
//   [Meta-Synthesis Risks]
//   [Meta-Synthesis Reinforcement]
//   [Meta-Synthesis Decay]
//   [Operator Meta-Synthesis Summary]
//
// As the capstone, its projected trajectory can reach a VERY-HIGH band
// beyond HIGH — the only operator card that projects past HIGH.
//
// Pure deterministic string IO — no backend, no styling, no new
// dependencies.

type Level = "LOW" | "LOW-MEDIUM" | "MEDIUM" | "MEDIUM-HIGH" | "HIGH" | "VERY-HIGH";

const LEVEL_RANK: Record<Level, number> = {
  LOW: 0, "LOW-MEDIUM": 1, MEDIUM: 2, "MEDIUM-HIGH": 3, HIGH: 4, "VERY-HIGH": 5,
};
const RANK_TO_LEVEL: Record<number, Level> = {
  0: "LOW", 1: "LOW-MEDIUM", 2: "MEDIUM", 3: "MEDIUM-HIGH", 4: "HIGH", 5: "VERY-HIGH",
};

type LoadLevel     = "low" | "moderate" | "high";
type DriftLevel    = "low" | "moderate" | "high";
type ClarityLevel  = "weak" | "partial" | "strong";
type PressureLevel = "low" | "moderate" | "elevated" | "high";
type Direction     = "improving" | "stable" | "deteriorating";

// Synthesis word scale (weak < partial < moderate < strong).
type SynthesisWord = "weak" | "partial" | "moderate" | "strong";

// How the upstream meta-pattern is holding (derived from Card 77 level).
type PatternWord = "stable" | "shifting" | "unstable";

// ----- Section parser (same pattern as Cards 62-83) -------------------

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

// Parses a meta-layer level. Matches VERY-HIGH first so it is not
// truncated to HIGH by the shorter alternative.
function parseLayerLevel(text: string, header: string): Level {
  const body = parseSection(text, header);
  const m = body.match(/^(VERY-HIGH|LOW-MEDIUM|MEDIUM-HIGH|LOW|MEDIUM|HIGH)/);
  return (m ? m[1] : "HIGH") as Level;
}

// Direction inferred from Card 70's diff summary.
function parseDirection(diffText: string): Direction {
  const summary = parseSection(diffText, "Operator Diff Summary");
  if (summary.includes("improving"))     return "improving";
  if (summary.includes("deteriorating")) return "deteriorating";
  return "stable";
}

// ----- Level → word mapping -------------------------------------------

// Maps a meta-layer level to a synthesis word. HIGH (and above) and
// MEDIUM-HIGH read "strong", MEDIUM "moderate", LOW-MEDIUM "partial",
// LOW "weak".
function levelWord(level: Level): SynthesisWord {
  const r = LEVEL_RANK[level];
  if (r >= 3) return "strong";    // HIGH / VERY-HIGH / MEDIUM-HIGH
  if (r === 2) return "moderate"; // MEDIUM
  if (r === 1) return "partial";  // LOW-MEDIUM
  return "weak";                  // LOW
}

// Whether the upstream meta-pattern (Card 77 level) is holding. Reads
// lenient — MEDIUM and up are "stable" (matches Cards 78-83).
function patternWordOf(metaPatternLevel: Level): PatternWord {
  const r = LEVEL_RANK[metaPatternLevel];
  if (r >= 2) return "stable";    // MEDIUM and up
  if (r >= 1) return "shifting";  // LOW-MEDIUM
  return "unstable";              // LOW
}

// ----- Derived level ---------------------------------------------------

// Meta-synthesis level is the floored average of the seven unified
// facet levels, capped at HIGH (the level itself never reads VERY-
// HIGH — only the projected trajectory can reach that band).
function metaSynthesisLevelOf(levels: Level[]): Level {
  const sum = levels.reduce((acc, l) => acc + LEVEL_RANK[l], 0);
  const avg = Math.floor(sum / levels.length);
  return RANK_TO_LEVEL[Math.max(0, Math.min(4, avg))];
}

// Trajectory walks prev → level → projected (centered, like Cards
// 72/76/79/81/83). Clamps to [0, 5] so an improving projection from
// HIGH can reach the capstone VERY-HIGH band.
function buildTrajectory(level: Level, direction: Direction): string {
  const cur      = LEVEL_RANK[level];
  const slope    = direction === "improving" ? 1 : direction === "deteriorating" ? -1 : 0;
  const prevRank = Math.max(0, Math.min(5, cur - slope));
  const projRank = Math.max(0, Math.min(5, cur + slope));
  const prev = RANK_TO_LEVEL[prevRank];
  const proj = RANK_TO_LEVEL[projRank];
  const moves = prev !== level || level !== proj;
  const tail  = moves ? "(projected)" : "(stable)";
  return `${prev.toLowerCase()} → ${level.toLowerCase()} → ${proj.toLowerCase()} ${tail}`;
}

// ----- Drivers / Inhibitors / Risks / Reinforcement / Decay -----------

function collectDrivers(
  coherenceWord:   SynthesisWord,
  resilienceWord:  SynthesisWord,
  integrationWord: SynthesisWord,
): string[] {
  const out: string[] = [];
  if (coherenceWord === "strong")   out.push("strong coherence synthesis");
  if (resilienceWord === "strong")  out.push("strong resilience synthesis");
  if (integrationWord === "strong") out.push("strong integration synthesis");
  return out;
}

function collectInhibitors(
  immunityWord:  SynthesisWord,
  stabilityWord: SynthesisWord,
  pressure:      PressureLevel,
): string[] {
  const out: string[] = [];
  if (immunityWord !== "strong")  out.push(`${immunityWord} immunity synthesis`);
  if (stabilityWord !== "strong") out.push(`${stabilityWord} stability synthesis`);
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
  immunityWord: SynthesisWord,
  load:         LoadLevel,
): string[] {
  const out: string[] = [];
  if (clarity !== "weak") out.push("maintain clarity discipline");
  if (drift !== "high")   out.push("maintain drift control");
  // Immunity verb-shift: strong → maintain, else → strengthen. Always
  // emits so reinforcement stays wide.
  if (immunityWord === "strong") out.push("maintain immunity synthesis");
  else                           out.push("strengthen immunity synthesis");
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
  if (pressure !== "low")   out.push("pressure may disrupt synthesis");
  if (drift !== "low")      out.push("drift may re-emerge");
  if (clarity !== "strong") out.push("clarity may weaken");
  return out;
}

// ----- Summary ---------------------------------------------------------

// As the capstone, the summary leads with the meta-synthesis strength
// (a level word) rather than a direction verb, and describes its three
// primary facets (coherence / resilience / integration) by their shared
// level band.
function buildSummary(
  level:            Level,
  coherenceLevel:   Level,
  resilienceLevel:  Level,
  integrationLevel: Level,
  immunityWord:     SynthesisWord,
): string {
  const lead = levelWord(level);
  const allSame = coherenceLevel === resilienceLevel && resilienceLevel === integrationLevel;
  const cri = allSame
    ? `${coherenceLevel.toLowerCase()} coherence-, resilience-, and integration-synthesis`
    : `${coherenceLevel.toLowerCase()} coherence-, ${resilienceLevel.toLowerCase()} resilience-, and ${integrationLevel.toLowerCase()} integration-synthesis`;
  const s1 = `Operator meta-synthesis is ${lead}, with ${cri}.`;
  if (immunityWord !== "strong") {
    return `${s1} Immunity-synthesis remains ${immunityWord} and may disrupt overall synthesis.`;
  }
  return s1;
}

// ----- Entry point -----------------------------------------------------

export function buildOperatorMetaSynthesis(
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
  operatorMetaIntegration:   string,
  operatorMetaAlignment:     string,
  operatorMetaCoherence:     string,
): string {
  // Reserve upstream layers on the signature — Cards 71/72/73 +
  // operator coherence (74) + operator synthesis (75) + system-operator
  // integration (76) stay on the contract so future AOs can read them
  // without changing callers. Card 84 unifies the seven meta-layers
  // (77-83), which already fold the operator core + 76 stack.
  void operatorStability;
  void operatorResilience;
  void operatorImmunity;
  void operatorCoherence;
  void operatorSynthesis;
  void systemOperatorIntegration;

  // Parse operator-state dims (Card 69) + direction (Card 70).
  const load      = parseLoad(operatorState);
  const drift     = parseDrift(operatorState);
  const clarity   = parseClarity(operatorState);
  const pressure  = parsePressure(operatorState);
  const direction = parseDirection(operatorDiff);

  // Parse the seven unified meta-layer levels.
  const metaPatternLevel     = parseLayerLevel(operatorMetaPattern, "Meta-Pattern Level");
  const metaStabilityLevel   = parseLayerLevel(operatorMetaStability, "Meta-Stability Level");
  const metaResilienceLevel  = parseLayerLevel(operatorMetaResilience, "Meta-Resilience Level");
  const metaImmunityLevel    = parseLayerLevel(operatorMetaImmunity, "Meta-Immunity Level");
  const metaIntegrationLevel = parseLayerLevel(operatorMetaIntegration, "Meta-Integration Level");
  const metaAlignmentLevel   = parseLayerLevel(operatorMetaAlignment, "Meta-Alignment Level");
  const metaCoherenceLevel   = parseLayerLevel(operatorMetaCoherence, "Meta-Coherence Level");

  // Per-dimension synthesis words.
  const coherenceWord   = levelWord(metaCoherenceLevel);
  const stabilityWord   = levelWord(metaStabilityLevel);
  const resilienceWord  = levelWord(metaResilienceLevel);
  const immunityWord    = levelWord(metaImmunityLevel);
  const integrationWord = levelWord(metaIntegrationLevel);
  const alignmentWord   = levelWord(metaAlignmentLevel);
  const patternWord     = patternWordOf(metaPatternLevel);

  // Derived fields.
  const level = metaSynthesisLevelOf([
    metaCoherenceLevel, metaStabilityLevel, metaResilienceLevel,
    metaImmunityLevel, metaIntegrationLevel, metaAlignmentLevel, metaPatternLevel,
  ]);
  const trajectory    = buildTrajectory(level, direction);
  const drivers       = collectDrivers(coherenceWord, resilienceWord, integrationWord);
  const inhibitors    = collectInhibitors(immunityWord, stabilityWord, pressure);
  const risks         = collectRisks(pressure, clarity, load);
  const reinforcement = collectReinforcement(clarity, drift, immunityWord, load);
  const decay         = collectDecay(pressure, drift, clarity);
  const summary       = buildSummary(level, metaCoherenceLevel, metaResilienceLevel, metaIntegrationLevel, immunityWord);

  const blocks: string[] = [];
  blocks.push("=== Operator Meta-Synthesis ===");
  blocks.push(`[Meta-Synthesis Level]\n${level}`);
  blocks.push(`[Coherence-Synthesis]\n${coherenceWord} synthesis`);
  blocks.push(`[Stability-Synthesis]\n${stabilityWord} synthesis`);
  blocks.push(`[Resilience-Synthesis]\n${resilienceWord} synthesis`);
  blocks.push(`[Immunity-Synthesis]\n${immunityWord} synthesis`);
  blocks.push(`[Integration-Synthesis]\n${integrationWord} integration synthesis`);
  blocks.push(`[Alignment-Synthesis]\n${alignmentWord} alignment synthesis`);
  blocks.push(`[Pattern-Synthesis]\n${patternWord} pattern synthesis`);
  blocks.push(`[Meta-Synthesis Trajectory]\n${trajectory}`);
  blocks.push(
    drivers.length === 0
      ? `[Meta-Synthesis Drivers]\n(none)`
      : `[Meta-Synthesis Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Meta-Synthesis Inhibitors]\n(none)`
      : `[Meta-Synthesis Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(
    risks.length === 0
      ? `[Meta-Synthesis Risks]\n(none)`
      : `[Meta-Synthesis Risks]\n${risks.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    reinforcement.length === 0
      ? `[Meta-Synthesis Reinforcement]\n(none)`
      : `[Meta-Synthesis Reinforcement]\n${reinforcement.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    decay.length === 0
      ? `[Meta-Synthesis Decay]\n(none)`
      : `[Meta-Synthesis Decay]\n${decay.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(`[Operator Meta-Synthesis Summary]\n${summary}`);

  return blocks.join("\n\n");
}
