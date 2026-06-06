// Card 88 — Operator Meta-Extraction (Phase-5 AO-12).
//
// Fourth card of the final Operator Advanced Operator cluster (AO-9
// through AO-14, Cards 85-90) — the meta-consolidation cluster. If
// reduction (87) isolates the irreducible core, extraction (88)
// isolates the actionable core — the part of the structure that can
// actually move. Same weight class as Cards 77-87.
//
// Card 88 extracts the actionable core from all eleven meta-operators —
// meta-pattern (77), meta-stability (78), meta-resilience (79), meta-
// immunity (80), meta-integration (81), meta-alignment (82), meta-
// coherence (83), meta-synthesis (84), meta-consolidation (85), meta-
// compression (86), and meta-reduction (87). Each "X-Extraction"
// dimension reads the level of the corresponding meta-layer:
//
//   [Meta-Extraction Level]           LOW … HIGH
//   [Pattern-Extraction]              "<word> extraction"
//   [Stability-Extraction]            "<word> extraction"
//   [Resilience-Extraction]           "<word> extraction"
//   [Immunity-Extraction]             "<word> extraction"
//   [Integration-Extraction]          "<word> integration extraction"
//   [Alignment-Extraction]            "<word> alignment extraction"
//   [Coherence-Extraction]            "<word> coherence extraction"
//   [Synthesis-Extraction]            "<word> synthesis extraction"
//   [Consolidation-Extraction]        "<word> consolidation extraction"
//   [Compression-Extraction]          "<word> compression extraction"
//   [Reduction-Extraction]            "<word> reduction extraction"
//   [Meta-Extraction Trajectory]      curr → next → projected (state)
//   [Meta-Extraction Drivers]
//   [Meta-Extraction Inhibitors]
//   [Meta-Extraction Risks]
//   [Meta-Extraction Reinforcement]
//   [Meta-Extraction Decay]
//   [Operator Meta-Extraction Summary]
//
// Like the other capstone cards, its projected trajectory can reach a
// VERY-HIGH band beyond HIGH.
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

// Extraction word scale (weak < partial < moderate < strong).
type ExtractionWord = "weak" | "partial" | "moderate" | "strong";

// ----- Section parser (same pattern as Cards 62-87) -------------------

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

// Maps a meta-layer level to an extraction word. HIGH (and above) and
// MEDIUM-HIGH read "strong", MEDIUM "moderate", LOW-MEDIUM "partial",
// LOW "weak".
function levelWord(level: Level): ExtractionWord {
  const r = LEVEL_RANK[level];
  if (r >= 3) return "strong";    // HIGH / VERY-HIGH / MEDIUM-HIGH
  if (r === 2) return "moderate"; // MEDIUM
  if (r === 1) return "partial";  // LOW-MEDIUM
  return "weak";                  // LOW
}

// ----- Derived level ---------------------------------------------------

// Meta-extraction level is the floored average of the eleven extracted
// facet levels, capped at HIGH (the level itself never reads VERY-HIGH
// — only the projected trajectory can reach that band).
function metaExtractionLevelOf(levels: Level[]): Level {
  const sum = levels.reduce((acc, l) => acc + LEVEL_RANK[l], 0);
  const avg = Math.floor(sum / levels.length);
  return RANK_TO_LEVEL[Math.max(0, Math.min(4, avg))];
}

// Trajectory walks curr → next → projected (forward, like Cards
// 78/80/82/85/86/87). Clamps to [0, 5] so an improving projection can
// reach the capstone VERY-HIGH band.
function buildTrajectory(level: Level, direction: Direction): string {
  const cur   = LEVEL_RANK[level];
  const slope = direction === "improving" ? 1 : direction === "deteriorating" ? -1 : 0;
  const next  = Math.max(0, Math.min(5, cur + slope));
  const proj  = Math.max(0, Math.min(5, cur + 2 * slope));
  const nextL = RANK_TO_LEVEL[next];
  const projL = RANK_TO_LEVEL[proj];
  const moves = level !== nextL || nextL !== projL;
  const tail  = moves ? "(projected)" : "(stable)";
  return `${level.toLowerCase()} → ${nextL.toLowerCase()} → ${projL.toLowerCase()} ${tail}`;
}

// ----- Drivers / Inhibitors / Risks / Reinforcement / Decay -----------

function collectDrivers(
  patternWord:    ExtractionWord,
  resilienceWord: ExtractionWord,
  synthesisWord:  ExtractionWord,
): string[] {
  const out: string[] = [];
  if (patternWord === "strong")    out.push("strong pattern extraction");
  if (resilienceWord === "strong") out.push("strong resilience extraction");
  if (synthesisWord === "strong")  out.push("strong synthesis extraction");
  return out;
}

function collectInhibitors(
  immunityWord:  ExtractionWord,
  stabilityWord: ExtractionWord,
  pressure:      PressureLevel,
): string[] {
  const out: string[] = [];
  if (immunityWord !== "strong")  out.push(`${immunityWord} immunity extraction`);
  if (stabilityWord !== "strong") out.push(`${stabilityWord} stability extraction`);
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
  immunityWord: ExtractionWord,
  load:         LoadLevel,
): string[] {
  const out: string[] = [];
  if (clarity !== "weak") out.push("maintain clarity discipline");
  if (drift !== "high")   out.push("maintain drift control");
  // Immunity verb-shift: strong → maintain, else → strengthen. Always
  // emits so reinforcement stays wide.
  if (immunityWord === "strong") out.push("maintain immunity extraction");
  else                           out.push("strengthen immunity extraction");
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
  if (pressure !== "low")   out.push("pressure may disrupt extraction");
  if (drift !== "low")      out.push("drift may re-emerge");
  if (clarity !== "strong") out.push("clarity may weaken");
  return out;
}

// ----- Summary ---------------------------------------------------------

function buildSummary(
  direction:      Direction,
  patternWord:    ExtractionWord,
  resilienceWord: ExtractionWord,
  synthesisWord:  ExtractionWord,
  immunityWord:   ExtractionWord,
): string {
  const lead =
    direction === "improving"     ? "strengthening" :
    direction === "deteriorating" ? "weakening" :
    "steady";
  // Collapse the shared adjective when pattern-, resilience-, and
  // synthesis-extraction all read the same word, otherwise name each.
  const allSame = patternWord === resilienceWord && resilienceWord === synthesisWord;
  const prs = allSame
    ? `${patternWord} pattern-, resilience-, and synthesis-extraction`
    : `${patternWord} pattern-, ${resilienceWord} resilience-, and ${synthesisWord} synthesis-extraction`;
  const s1 = `Operator meta-extraction is ${lead}, with ${prs}.`;
  if (immunityWord !== "strong") {
    return `${s1} Immunity-extraction remains ${immunityWord} and may disrupt overall extraction.`;
  }
  return s1;
}

// ----- Entry point -----------------------------------------------------

export function buildOperatorMetaExtraction(
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
  operatorMetaSynthesis:     string,
  operatorMetaConsolidation: string,
  operatorMetaCompression:   string,
  operatorMetaReduction:     string,
): string {
  // Reserve the operator-core layers on the signature — Cards 71-76
  // stay on the contract so future AOs can read them without changing
  // callers. Card 88 extracts from the eleven meta-layers (77-87),
  // which already fold the operator core + system-operator integration
  // stack.
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

  // Parse the eleven extracted meta-layer levels.
  const metaPatternLevel       = parseLayerLevel(operatorMetaPattern, "Meta-Pattern Level");
  const metaStabilityLevel     = parseLayerLevel(operatorMetaStability, "Meta-Stability Level");
  const metaResilienceLevel    = parseLayerLevel(operatorMetaResilience, "Meta-Resilience Level");
  const metaImmunityLevel      = parseLayerLevel(operatorMetaImmunity, "Meta-Immunity Level");
  const metaIntegrationLevel   = parseLayerLevel(operatorMetaIntegration, "Meta-Integration Level");
  const metaAlignmentLevel     = parseLayerLevel(operatorMetaAlignment, "Meta-Alignment Level");
  const metaCoherenceLevel     = parseLayerLevel(operatorMetaCoherence, "Meta-Coherence Level");
  const metaSynthesisLevel     = parseLayerLevel(operatorMetaSynthesis, "Meta-Synthesis Level");
  const metaConsolidationLevel = parseLayerLevel(operatorMetaConsolidation, "Meta-Consolidation Level");
  const metaCompressionLevel   = parseLayerLevel(operatorMetaCompression, "Meta-Compression Level");
  const metaReductionLevel     = parseLayerLevel(operatorMetaReduction, "Meta-Reduction Level");

  // Per-dimension extraction words.
  const patternWord       = levelWord(metaPatternLevel);
  const stabilityWord     = levelWord(metaStabilityLevel);
  const resilienceWord    = levelWord(metaResilienceLevel);
  const immunityWord      = levelWord(metaImmunityLevel);
  const integrationWord   = levelWord(metaIntegrationLevel);
  const alignmentWord     = levelWord(metaAlignmentLevel);
  const coherenceWord     = levelWord(metaCoherenceLevel);
  const synthesisWord     = levelWord(metaSynthesisLevel);
  const consolidationWord = levelWord(metaConsolidationLevel);
  const compressionWord   = levelWord(metaCompressionLevel);
  const reductionWord     = levelWord(metaReductionLevel);

  // Derived fields.
  const level = metaExtractionLevelOf([
    metaPatternLevel, metaStabilityLevel, metaResilienceLevel, metaImmunityLevel,
    metaIntegrationLevel, metaAlignmentLevel, metaCoherenceLevel, metaSynthesisLevel,
    metaConsolidationLevel, metaCompressionLevel, metaReductionLevel,
  ]);
  const trajectory    = buildTrajectory(level, direction);
  const drivers       = collectDrivers(patternWord, resilienceWord, synthesisWord);
  const inhibitors    = collectInhibitors(immunityWord, stabilityWord, pressure);
  const risks         = collectRisks(pressure, clarity, load);
  const reinforcement = collectReinforcement(clarity, drift, immunityWord, load);
  const decay         = collectDecay(pressure, drift, clarity);
  const summary       = buildSummary(direction, patternWord, resilienceWord, synthesisWord, immunityWord);

  const blocks: string[] = [];
  blocks.push("=== Operator Meta-Extraction ===");
  blocks.push(`[Meta-Extraction Level]\n${level}`);
  blocks.push(`[Pattern-Extraction]\n${patternWord} extraction`);
  blocks.push(`[Stability-Extraction]\n${stabilityWord} extraction`);
  blocks.push(`[Resilience-Extraction]\n${resilienceWord} extraction`);
  blocks.push(`[Immunity-Extraction]\n${immunityWord} extraction`);
  blocks.push(`[Integration-Extraction]\n${integrationWord} integration extraction`);
  blocks.push(`[Alignment-Extraction]\n${alignmentWord} alignment extraction`);
  blocks.push(`[Coherence-Extraction]\n${coherenceWord} coherence extraction`);
  blocks.push(`[Synthesis-Extraction]\n${synthesisWord} synthesis extraction`);
  blocks.push(`[Consolidation-Extraction]\n${consolidationWord} consolidation extraction`);
  blocks.push(`[Compression-Extraction]\n${compressionWord} compression extraction`);
  blocks.push(`[Reduction-Extraction]\n${reductionWord} reduction extraction`);
  blocks.push(`[Meta-Extraction Trajectory]\n${trajectory}`);
  blocks.push(
    drivers.length === 0
      ? `[Meta-Extraction Drivers]\n(none)`
      : `[Meta-Extraction Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Meta-Extraction Inhibitors]\n(none)`
      : `[Meta-Extraction Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(
    risks.length === 0
      ? `[Meta-Extraction Risks]\n(none)`
      : `[Meta-Extraction Risks]\n${risks.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    reinforcement.length === 0
      ? `[Meta-Extraction Reinforcement]\n(none)`
      : `[Meta-Extraction Reinforcement]\n${reinforcement.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    decay.length === 0
      ? `[Meta-Extraction Decay]\n(none)`
      : `[Meta-Extraction Decay]\n${decay.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(`[Operator Meta-Extraction Summary]\n${summary}`);

  return blocks.join("\n\n");
}
